(() => {
  'use strict';
  const uuid=()=>crypto.randomUUID().replaceAll('-','');
  function create(tabs,paired,send,onWake=()=>{}){
    let pending=null,busy=false,last={state:'NOT_ENROLLED',read_access:'DISABLED',session:'UNKNOWN'},bound=null,choice=null;
    let controlRevision=null,bindingHint=null,ignoreHint=false,needsRoute=true;
    let knownTabs=new Set(),mappingHint=false,mappingHintSequence=0,activeMapping=null,progressChain=Promise.resolve(),traceChain=Promise.resolve(),wakePending=false,notificationSequence=0;
    const workerInstance=uuid();
    function causalTrace(event,reason=null,binding=null){
      if(!paired())return;
      const trace={trace_revision:1,event,worker_instance:workerInstance,...(reason?{reason}:{})};
      for(const key of ['tab_id','document_id','document_generation','content_trace_revision','mapping_reader_revision'])if(binding?.[key]!==undefined)trace[key]=binding[key];
      traceChain=traceChain.then(()=>send({kind:'RUNTIME_CAUSAL_TRACE',request_id:uuid(),trace})).catch(()=>{});
    }
    const mappingPresent=()=>last.mapping_scope==='NORMAL_OWNER_PRESENT'||last.mapping_orchestrated;
    const signalWake=(change=false)=>{needsRoute=true;if(change&&mappingPresent()){mappingHint=true;mappingHintSequence++;}if(busy)wakePending=true;else onWake();};
    const eligibleURL=url=>{try{return new URL(url).origin===FreightDeskX1Contract.origin;}catch{return false;}};
    const router=FreightDeskTabRouter.create(tabs,paired,code=>{
      bound=null;if(code!=='TAB_SELECTION_REQUIRED'){
        needsRoute=true;
        if(['DOCUMENT_CHANGED','CONTENT_SCRIPT_PORT_STALE'].includes(code))signalWake(true);
        else if(!busy)onWake();
      }
    },true,async()=>enabled(await wakeRequest(null)),()=>{
      if(mappingPresent())signalWake(true);
    },diagnostic=>{
      if(!activeMapping||!paired())return;
      const dispatch=activeMapping;
      progressChain=progressChain.then(()=>send({kind:diagnostic?.capture_ack===true?'RUNTIME_CAPTURE_ACK':'RUNTIME_MAPPING_PROGRESS',request_id:uuid(),command_request_id:dispatch.command.request_id,route:dispatch.route,...(diagnostic?.capture_ack===true?{}:{diagnostic})})).catch(()=>reset());
    },trace=>{if(last.mapping_orchestrated)causalTrace(trace.event,trace.reason,trace);});
    // Lifecycle events are wake hints only. The host lease, cadence and session proof still gate every DOM read.
    tabs?.onUpdated.addListener((id,change)=>{
      if((knownTabs.has(id)||eligibleURL(change.url))&&(change.status==='complete'||change.url))signalWake(true);
    });
    tabs?.onCreated?.addListener(tab=>{if(eligibleURL(tab.url))signalWake(true);});
    tabs?.onRemoved.addListener(id=>{if(knownTabs.has(id))signalWake(true);});
    tabs?.onActivated?.addListener(()=>{if(mappingPresent())signalWake(true);});
    globalThis.chrome?.windows?.onFocusChanged?.addListener(()=>{if(mappingPresent())signalWake();});
    function reset(){
      router.cancel('PAIRING_LOST');bound=null;choice=null;bindingHint=null;wakePending=false;mappingHint=false;notificationSequence=0;
      if(pending){const p=pending;pending=null;clearTimeout(p.timer);p.reject(Error('PAIRING_LOST'));}
    }
    function status(){return {...last,bound_tab:bound?'ACTIVE':'UNBOUND',...(!bound?{session:'UNKNOWN',view:'UNKNOWN',board_evidence_status:last.last_board_sync?'LAST_KNOWN_BOARD_EVIDENCE':'NO_BOARD_EVIDENCE'}:{})};}
    async function rpc(body){
      if(!paired())throw Error('PAIRING_LOST');if(pending)throw Error('READ_SEQUENCE_INVALID');
      await traceChain;
      return new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>{if(pending){pending=null;router.cancel();reject(Error('READ_TIMEOUT'));}},15000);
        pending={resolve,reject,timer,body};send(body).catch(()=>reset());
      });
    }
    async function accept(body){
      if(body.kind==='RUNTIME_JOB_WAKE_NOTIFICATION'){
        const keys='actor,kind,notification_sequence,production_writes,protocol,read_dispatch_enabled,state,tenant_id';
        if(!paired()||Object.keys(body).sort().join()!==keys||body.protocol!==1||body.tenant_id!=='booking-logistics'||body.actor!=='FreightDesk/Avery'||
          body.production_writes!==false||body.state!=='PAIRED'||body.read_dispatch_enabled!==false||!Number.isSafeInteger(body.notification_sequence)||body.notification_sequence<1)
          throw Error('PAIRING_ACK_INVALID');
        if(body.notification_sequence>notificationSequence){notificationSequence=body.notification_sequence;causalTrace('WORKER_WAKE_RECEIVED');signalWake();}
        return; // Signed notification only wakes policy evaluation; it cannot dispatch a browser operation.
      }
      if(body.kind==='RUNTIME_MAPPING_PROGRESS_ACK'&&paired())return;
      if(body.kind==='RUNTIME_CAUSAL_TRACE_ACK'&&paired())return;
      if(!pending||!paired())throw Error('PAIRING_ACK_INVALID');
      if(body.kind==='RUNTIME_DISPATCH'){
        const p=pending;
        if(p.body.kind!=='RUNTIME_WAKE'||!body.route||!p.body.route||
          Object.keys(body.route).length!==Object.keys(p.body.route).length||
          Object.keys(body.route).some(k=>body.route[k]!==p.body.route[k]))throw Error('PAIRING_ACK_INVALID');
        FreightDeskX1Contract.validateRuntime(body.command);
        if(p.body.probe_only&&body.command.operation!=='ASCEND_GET_SESSION_STATE')throw Error('PAIRING_ACK_INVALID');
        if(p.body.owner_present===false)throw Error('PAIRING_ACK_INVALID');
        p.body={kind:'AWAITING_RUNTIME_RESULT'};
        (async()=>{
          let result;activeMapping=body.command.operation==='ASCEND_MAP_WORKSPACE'?body:null;
          try{result=await router.execute(body);}catch(error){result={evidence:null,error_code:FreightDeskReadErrors.safe(error)};}
          await progressChain;activeMapping=null;
          await traceChain;
          if(pending!==p||!paired())return;
          await send({kind:'RUNTIME_RESULT',build:FreightDeskBuild,request_id:uuid(),command_request_id:body.command.request_id,route:body.route,...result});
        })().catch(()=>reset());return;
      }
      if(body.kind!=='RUNTIME_STATUS'||!body.status||typeof body.status!=='object')throw Error('PAIRING_ACK_INVALID');
      if(body.status.build&&Object.keys(FreightDeskBuild).some(k=>body.status.build[k]!==FreightDeskBuild[k])){
        body={...body,status:{...body.status,state:'PROTOCOL_VERSION_MISMATCH',error_code:'PROTOCOL_VERSION_MISMATCH'}};
      }
      last=body.status;
      const hint=body.binding_hint;
      bindingHint=hint&&Object.keys(hint).sort().join()==='document_id,tab_id'&&Number.isInteger(hint.tab_id)&&
        typeof hint.document_id==='string'&&/^[a-f0-9]{32}$/.test(hint.document_id)?hint:null;
      if(controlRevision!==null&&last.control_revision!==controlRevision){router.cancel('TAB_STATE_CHANGED','LEASE_GENERATION_CHANGED');bound=null;choice=null;}
      controlRevision=last.control_revision;
      const p=pending;pending=null;clearTimeout(p.timer);p.resolve({...last});
    }
    const wakeRequest=async(route,probe=false)=>{
      const ownerPresent=route&&mappingPresent()?await router.ownerPresence(last.lease_expires_at):null;
      const hint=!!route&&!probe&&mappingHint&&ownerPresent!==false;
      const hintSequence=mappingHintSequence;
      const result=await rpc({kind:'RUNTIME_WAKE',request_id:uuid(),build:FreightDeskBuild,handshake:route?router.handshake():null,route,...(probe?{probe_only:true}:{}),
        ...(mappingPresent()&&route?{owner_present:ownerPresent===true}:{}),...(hint?{mapping_hint:true}:{})});
      if(hint&&mappingHintSequence===hintSequence)mappingHint=false; // Preserve newer changes received while this request was in flight.
      return result;
    };
    const reportRoute=(routing_state,eligible_tab_count,routing_error=null)=>rpc({kind:'RUNTIME_WAKE',request_id:uuid(),build:FreightDeskBuild,route:null,routing_state,eligible_tab_count,routing_error});
    const enabled=s=>s.read_access==='ENABLED'&&!s.paused&&s.state!=='STOPPED'&&(!s.error_code||
      ['REFRESH_ASCEND_TAB','CONTENT_SCRIPT_MISSING','CONTENT_SCRIPT_OLD_VERSION','CONTENT_SCRIPT_PORT_STALE','DOCUMENT_CHANGED','ASCEND_REAUTH_REQUIRED','SESSION_UNVERIFIED','NAVIGATION_STARTED','TAB_STATE_CHANGED','NO_ELIGIBLE_TAB','TAB_SELECTION_REQUIRED','WAITING_FOR_OWNER_WORKSPACE'].includes(s.error_code));
    async function probe(tabId){
      const route=await router.select(tabId),s=await wakeRequest(route,true);
      if(s.state==='WAITING_FOR_OWNER_WORKSPACE'||s.mapping_orchestrated&&s.owner_present===false)return null;
      if(s.mapping_capture_requested&&enabled(s)){
        // Probe -> mapping authority invalidates the old port. Rebind in this same wake;
        // the host still requires fresh session proof before MAP can be dispatched.
        return router.current().catch(()=>router.select(tabId));
      }
      return s.session==='AUTHENTICATED'?route:null;
    }
    async function resolve(){
      if(last.mapping_scope==='NORMAL_OWNER_PRESENT'||last.mapping_orchestrated){
        const active=await tabs.query({active:true,lastFocusedWindow:true});
        if(active.length!==1||!eligibleURL(active[0].url)){
          // Leave an existing document observer armed; an eligible owner focus event can resume proof.
          if(last.mapping_orchestrated)await reportRoute('WAITING_FOR_OWNER_WORKSPACE',0);
          return null;
        }
        if(active[0].status==='loading'){
          if(last.mapping_orchestrated)await reportRoute('WAITING_FOR_OWNER_WORKSPACE',1);
          return null; // Navigation completion supplies the wake; never probe or inject an unfinished document.
        }
        if(last.mapping_orchestrated)causalTrace('TAB_CANDIDATE_FOUND',null,{tab_id:active[0].id});
        // Owner navigation is the scope: never probe or choose a background load tab.
        knownTabs=new Set([active[0].id]);
        return probe(active[0].id);
      }
      const available=await router.list();
      knownTabs=new Set(available.map(tab=>tab.tab_id));
      if(!available.length){router.cancel();await reportRoute('WAITING_FOR_ASCEND',0);return null;}
      if(available.length>10){router.cancel();await reportRoute('TAB_SELECTION_REQUIRED',available.length);return null;}
      const skipped=new Set();
      if(bound){
        try{const route=await router.current(),s=await wakeRequest(route,true);if(s.session==='AUTHENTICATED')return route;}
        catch{ /* A fresh provider session proof is required after every lifecycle change. */ }
        if(bound)skipped.add(bound.tab_id);
        bound=null;
      }
      if(!ignoreHint&&bindingHint&&!skipped.has(bindingHint.tab_id)&&available.some(tab=>tab.tab_id===bindingHint.tab_id)){
        const hint=bindingHint;
        try{
          const route=await router.select(hint.tab_id);
          if(route.document_id===hint.document_id){
            const s=await wakeRequest(route,true);if(s.session==='AUTHENTICATED')return route;skipped.add(route.tab_id);
          }
        }catch{ /* A stale lifecycle hint is never authenticated provider identity. */ }
        router.cancel();bindingHint=null;
      }
      if(choice!==null){
        const candidate=available.find(t=>t.tab_id===choice);choice=null;
        if(candidate){const route=await probe(candidate.tab_id);if(route)return route;}
      }
      const authenticated=[];let failure=null;
      for(const tab of available.filter(tab=>!skipped.has(tab.tab_id))){
        if(!enabled(last))return null;
        try{const route=await probe(tab.tab_id);if(route)authenticated.push(route);}catch(error){failure=error.message;router.cancel();}
      }
      if(failure){await reportRoute(failure.startsWith('CONTENT_SCRIPT_')||failure==='REFRESH_ASCEND_TAB'?'CONTENT_SCRIPT_STALE':'TAB_DISCOVERY_FAILED',available.length,FreightDeskReadErrors.safe(failure));return null;}
      if(authenticated.length===0){router.cancel();await reportRoute('ASCEND_REAUTH_REQUIRED',available.length);return null;}
      if(authenticated.length!==1){router.cancel();await reportRoute('TAB_SELECTION_REQUIRED',available.length);return null;}
      // Reuse the proved port when possible; the next host step verifies session anew.
      const current=await router.current().catch(()=>null);
      return current?.tab_id===authenticated[0].tab_id?current:router.select(authenticated[0].tab_id);
    }
    async function wake(){
      if(busy||!paired())return status();busy=true;
      try{
        if(globalThis.chrome?.runtime?.getManifest&&chrome.runtime.getManifest().version!==FreightDeskBuild.extension_version){
          last={...last,state:'PROTOCOL_VERSION_MISMATCH',error_code:'PROTOCOL_VERSION_MISMATCH'};return status();
        }
        const initial=await wakeRequest(null);
        if(!enabled(initial)){router.cancel();bound=null;return status();}
        if(!needsRoute&&!initial.mapping_capture_requested&&initial.next_due_at&&initial.next_due_at>Date.now()/1000)return status();
        const route=await resolve();if(!route){needsRoute=false;return status();}bound=route;ignoreHint=false;needsRoute=false;
        // The host supplies each exact step and cadence. A wake has a fixed work budget.
        for(let step=0;step<(last.mapping_operation_mode==='AUTO_MAP'?12:5);step++){
          const result=await wakeRequest(await router.current());
          if(!enabled(result)||!result.mapping_capture_requested&&result.next_due_at&&result.next_due_at>Date.now()/1000)break;
        }
        return status();
      }catch(error){
        router.cancel();bound=null;last={...last,state:'TAB_DISCOVERY_FAILED',error_code:FreightDeskReadErrors.safe(error),bound_tab:'NONE'};
        try{await reportRoute('TAB_DISCOVERY_FAILED',knownTabs.size,FreightDeskReadErrors.safe(error));}catch{/* Host unavailable: local state only. */}return status();
      }finally{busy=false;if(wakePending){wakePending=false;needsRoute=true;onWake();}}
    }
    async function handle(message){
      if(message.action==='RUNTIME_MAPPING_CAPTURE'&&Object.keys(message).length===1){
        if(busy)return {...status(),error_code:'MAPPING_CAPTURE_PENDING'};
        busy=true;
        try{await rpc({kind:'RUNTIME_MAPPING_CAPTURE',request_id:uuid()});needsRoute=true;
          if(last.mapping_operation_mode==='AUTO_MAP')await new Promise(resolve=>setTimeout(resolve,300));}
        finally{busy=false;}
        return wake();
      }
      if(message.action==='RUNTIME_STATUS'&&Object.keys(message).length===1)return status();
      if(message.action==='RUNTIME_TABS'&&Object.keys(message).length===1)return {tabs:await router.list()};
      if(message.action==='RUNTIME_REBIND'&&Object.keys(message).length===1){router.cancel('TAB_STATE_CHANGED','ROUTER_REBOUND');choice=null;bound=null;ignoreHint=true;onWake();return status();}
      if(message.action==='RUNTIME_SELECT'&&Object.keys(message).sort().join()==='action,tab_id'&&Number.isInteger(message.tab_id)){
        router.cancel('TAB_STATE_CHANGED','TAB_SELECTION_CHANGED');choice=message.tab_id;bound=null;ignoreHint=true;onWake();return status();
      }
      throw Error('COMMAND_NOT_ALLOWED');
    }
    return Object.freeze({accept,wake,handle,reset,status});
  }
  globalThis.FreightDeskRuntime=Object.freeze({create});
})();
