(() => {
  'use strict';
  const origin='https://ascendtms.com',paths=['/','/loads','/login.html'];
  const eligible=tab=>{try{const u=new URL(tab.url);return Number.isInteger(tab.id)&&u.origin===origin&&!u.username&&!u.password;}catch{return false;}};
  const safeTab=tab=>({tab_id:tab.id,path:paths.includes(new URL(tab.url).pathname)?new URL(tab.url).pathname:'UNKNOWN'});
  function create(tabs,paired,onInvalid=()=>{},runtime=false,recoveryAllowed=async()=>false,onMappingHint=()=>{},onMappingProgress=()=>{},onCausalTrace=()=>{}){
    let handshake=null;
    let selected=null,channel=null,pending=null,route=null,generation=0,baseUrl=null,lastInvalid='TAB_SELECTION_REQUIRED';
    const trace=(event,reason=null,binding=null)=>{
      const source=binding||handshake||route||{tab_id:selected};
      onCausalTrace({event,...(reason?{reason}:{}),...(Number.isInteger(source.tab_id)?{tab_id:source.tab_id}:{}),
        ...(source.document_id?{document_id:source.document_id}:{}),...(source.document_generation?{document_generation:source.document_generation}:{}),
        ...(source.content_trace_revision===1?{content_trace_revision:1}:{}),
        ...([1,2].includes(source.mapping_reader_revision)?{mapping_reader_revision:source.mapping_reader_revision}:{})});
    };
    function cancel(code='TAB_STATE_CHANGED',reason=null,binding=null){
      if(route||handshake||channel)trace('SESSION_PROOF_INVALIDATED',reason,binding);
      generation++;selected=null;route=null;handshake=null;baseUrl=null;lastInvalid=code;
      const old=channel;channel=null;if(old)old.disconnect();
      if(pending){const p=pending;pending=null;clearTimeout(p.timer);p.reject(Error(code));}
      onInvalid(code);
    }
    tabs?.onRemoved.addListener(id=>{if(id===selected)cancel();});
    tabs?.onUpdated.addListener((id,change)=>{
      if(change.status==='loading')recovered.delete(id);
      if(id===selected&&(change.status==='loading'||change.url&&change.url.split('#')[0]!==baseUrl))cancel(runtime?'DOCUMENT_CHANGED':'TAB_STATE_CHANGED',change.status==='loading'?'DOCUMENT_LOADING':'ROUTING_PATH_CHANGED');
    });
    async function list(){
      if(!paired())throw Error('PAIRING_LOST');
      const found=(await tabs.query({url:origin+'/*'})).filter(eligible);
      if(found.length>100)throw Error('TAB_STATE_CHANGED');
      return found.map(tab=>{const safe=safeTab(tab);return runtime&&safe.path==='UNKNOWN'?{...safe,path:'OTHER'}:safe;});
    }
    async function connectDocument(id){
      cancel('TAB_SELECTION_REQUIRED','ROUTER_REBOUND');
      if(!Number.isInteger(id))throw Error('TAB_SELECTION_REQUIRED');
      const available=await list();
      if(!available.length)throw Error('NO_ELIGIBLE_TAB');
      const match=available.find(t=>t.tab_id===id);
      if(!match)throw Error('TAB_SELECTION_REQUIRED');
      if(!paths.includes(match.path)&&!(runtime&&match.path==='OTHER'))throw Error('TAB_STATE_CHANGED');
      const tab=await tabs.get(id);if(!eligible(tab)||safeTab(tab).path!==(match.path==='OTHER'?'UNKNOWN':match.path))throw Error('TAB_STATE_CHANGED');
      selected=id;baseUrl=tab.url.split('#')[0];const currentGeneration=generation;
      let port;try{port=tabs.connect(id,{name:'freightdesk-x1-identity',frameId:0});}catch{cancel(runtime?'CONTENT_SCRIPT_MISSING':'TAB_STATE_CHANGED');throw Error(lastInvalid);}channel=port;
      return new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>{if(channel===port)cancel(runtime?(lastInvalid==='CONTENT_SCRIPT_OLD_VERSION'?lastInvalid:'CONTENT_SCRIPT_MISSING'):'TAB_STATE_CHANGED');},3000);
        pending={resolve,reject,timer,kind:'READY'};
        port.onDisconnect.addListener(()=>{
          // Read lastError solely to acknowledge Chrome's error; never log its message.
          void globalThis.chrome?.runtime?.lastError;
          if(channel===port)cancel(runtime?(pending?.kind==='READY'?'CONTENT_SCRIPT_MISSING':'CONTENT_SCRIPT_PORT_STALE'):'TAB_STATE_CHANGED','CONTENT_PORT_DISCONNECTED');
        });
        port.onMessage.addListener(message=>{
          if(runtime&&channel===port&&generation===currentGeneration&&paired()&&message?.kind==='X1_CAUSAL_TRACE'){
            const allowedReasons=['DOCUMENT_ID_CHANGED','DOCUMENT_GENERATION_CHANGED','CONTENT_PATH_CHANGED','CONTENT_PORT_REPLACED','CONTENT_PORT_DISCONNECTED','FOCUS_LOST','FOREGROUND_LOST','CONTENT_READY_MISMATCH','READINESS_BINDING_CHANGED'];
            if(Object.keys(message).sort().join()==='document_generation,document_id,kind,reason'&&message.document_id===handshake?.document_id&&
              message.document_generation===handshake?.document_generation&&allowedReasons.includes(message.reason))trace('SESSION_PROOF_INVALIDATED',message.reason);
            return;
          }
          if(runtime&&channel===port&&generation===currentGeneration&&paired()&&message?.kind==='X1_MAPPING_CHANGED_V1'){
            if(Object.keys(message).sort().join()==='document_generation,document_id,kind'&&message.document_id===handshake?.document_id&&message.document_generation===handshake?.document_generation)onMappingHint();
            return;
          }
          if(runtime&&channel===port&&generation===currentGeneration&&paired()&&message?.kind==='X1_OWNER_READINESS_CHANGED'){
            if(Object.keys(message).sort().join()==='document_generation,document_id,kind'&&message.document_id===handshake?.document_id&&message.document_generation===handshake?.document_generation)onMappingHint();
            return;
          }
          if(channel!==port||generation!==currentGeneration||!pending)return;
          if(runtime&&pending.kind==='RESULT'&&['X1_MAPPING_PROGRESS','X1_CAPTURE_ACK'].includes(message?.kind)){
            if(paired()&&message.document_id===handshake?.document_id&&message.document_generation===handshake?.document_generation)
              onMappingProgress(message.kind==='X1_CAPTURE_ACK'?{capture_ack:true}:message.diagnostic);
            return;
          }
          if(!paired()){cancel('PAIRING_LOST');return;}
          if(pending.kind==='OWNER_READINESS'){
            if(!message||Object.keys(message).sort().join()!=='document_generation,document_id,kind,owner_present,request_id'||message.kind!=='X1_OWNER_READINESS_ACK'||
              message.document_id!==handshake?.document_id||message.document_generation!==handshake?.document_generation||message.request_id!==pending.requestId||typeof message.owner_present!=='boolean'){
              cancel('PROTOCOL_VERSION_MISMATCH','READINESS_BINDING_CHANGED');return;
            }
            const p=pending;pending=null;clearTimeout(p.timer);p.resolve(message.owner_present);return;
          }
          if(pending.kind==='READY'){
            if(runtime){
              if(message?.kind==='DOCUMENT_READY'){lastInvalid='CONTENT_SCRIPT_OLD_VERSION';return;}
              if(!message||message.kind!=='X1_DOCUMENT_READY'){cancel('PROTOCOL_VERSION_MISMATCH');return;}
              if(message.trace_revision!==1||message.mapping_reader_revision!==2){cancel('CONTENT_SCRIPT_OLD_VERSION','CONTENT_READY_MISMATCH');return;}
              const B=FreightDeskBuild;
              if(message.build?.extension_version!==B.extension_version){cancel('CONTENT_SCRIPT_OLD_VERSION');return;}
              if(Object.keys(B).some(k=>message.build?.[k]!==B[k])){cancel('PROTOCOL_VERSION_MISMATCH');return;}
              if(!Number.isInteger(message.document_generation)||message.document_generation<1){cancel('DOCUMENT_CHANGED','DOCUMENT_GENERATION_CHANGED');return;}
              if(typeof message.document_id!=='string'||!/^[a-f0-9]{32}$/.test(message.document_id)){cancel('DOCUMENT_CHANGED','DOCUMENT_ID_CHANGED');return;}
              if(message.path!==match.path){cancel('DOCUMENT_CHANGED','CONTENT_READY_MISMATCH',{tab_id:id,document_id:message.document_id,document_generation:message.document_generation});return;}
              handshake={...B,service_worker_version:B.extension_version,content_script_version:message.build.extension_version,
                document_generation:message.document_generation,tab_id:id,document_id:message.document_id};
            }else if(!message||!['document_id,kind,path','document_id,kind,path,reader_version'].includes(Object.keys(message).sort().join())||
              message.kind!=='DOCUMENT_READY'||typeof message.document_id!=='string'||!/^[a-f0-9]{32}$/.test(message.document_id)||message.path!==match.path){cancel();return;}
            route={...match,document_id:message.document_id,eligible_tab_count:available.length,origin};
            if(runtime){trace('TAB_BOUND');trace('CONTENT_PORT_PRESENT',null,{...handshake,content_trace_revision:message.trace_revision,mapping_reader_revision:message.mapping_reader_revision});}
            const p=pending;pending=null;clearTimeout(p.timer);p.resolve({...route});return;
          }
          if(runtime){
            if(message?.kind==='IDENTITY_RESULT')return; // Old packaged listeners cannot execute the V2 kind.
            if(message?.kind!=='X1_RESULT_V2'){cancel('PROTOCOL_VERSION_MISMATCH');return;}
            if(message.document_id!==handshake?.document_id){cancel('DOCUMENT_CHANGED','DOCUMENT_ID_CHANGED');return;}
            if(message.document_generation!==handshake?.document_generation){cancel('DOCUMENT_CHANGED','DOCUMENT_GENERATION_CHANGED');return;}
          }else if(!message||Object.keys(message).sort().join()!=='error_code,evidence,kind'||message.kind!=='IDENTITY_RESULT'){cancel();return;}
          const p=pending;pending=null;clearTimeout(p.timer);p.resolve({evidence:message.evidence,error_code:message.error_code});
        });
      });
    }
    const recovered=new Set();
    const packagedFiles=Object.freeze(['build.js','contract.js','read-errors.js','load-board-view.js','detail-scope.js','webbridge.js','mapping-scope.js','workspace.js','reader.js','content.js']);
    async function select(id){
      // A routine proof refresh must preserve the document's passive observer and private port.
      if(runtime&&selected===id&&route&&channel){
        try{return await current();}catch{/* Actual lifecycle invalidation requires a new handshake. */}
      }
      try{return await connectDocument(id);}catch(error){
        if(!runtime||!['CONTENT_SCRIPT_MISSING','CONTENT_SCRIPT_OLD_VERSION','CONTENT_SCRIPT_PORT_STALE'].includes(error.message))throw error;
        if(!await recoveryAllowed())throw Error('READ_POLICY_BLOCKED');
        const tab=await tabs.get(id).catch(()=>null);
        if(!paired()||!tab||!eligible(tab))throw Error('DOCUMENT_CHANGED');
        if(tab.status==='loading')throw Error('DOCUMENT_CHANGED');
        if(recovered.has(id))throw Error('CONTENT_SCRIPT_RECOVERY_FAILED');
        if(!globalThis.chrome?.scripting?.executeScript)throw Error('CONTENT_SCRIPT_INJECTION_BLOCKED');
        recovered.add(id);
        try{
          // Fixed package list and top frame only; never accept code, file names or URLs from a command.
          await chrome.scripting.executeScript({target:{tabId:id,frameIds:[0]},world:'ISOLATED',files:[...packagedFiles]});
        }catch{throw Error('CONTENT_SCRIPT_INJECTION_BLOCKED');}
        const after=await tabs.get(id);
        if(!eligible(after)||after.url!==tab.url||after.status==='loading')throw Error('DOCUMENT_CHANGED');
        try{return await connectDocument(id);}catch(error){
          if(['PROTOCOL_VERSION_MISMATCH','DOCUMENT_CHANGED'].includes(error.message))throw error;
          throw Error('CONTENT_SCRIPT_RECOVERY_FAILED');
        }
      }
    }
    async function current(){
      if(!paired())throw Error('PAIRING_LOST');
      if(!route||!channel)throw Error(lastInvalid);
      const g=generation,id=selected;let tab;
      try{tab=await tabs.get(id);}catch{cancel();throw Error('TAB_STATE_CHANGED');}
      const available=await list();
      if(g!==generation){cancel('TAB_STATE_CHANGED','ROUTER_REBOUND');throw Error('TAB_STATE_CHANGED');}
      if(!eligible(tab)||tab.url.split('#')[0]!==baseUrl){cancel('TAB_STATE_CHANGED','ROUTING_PATH_CHANGED');throw Error('TAB_STATE_CHANGED');}
      if(tab.status==='loading'){cancel('TAB_STATE_CHANGED','DOCUMENT_LOADING');throw Error('TAB_STATE_CHANGED');}
      if(!available.some(t=>t.tab_id===id)){cancel('TAB_STATE_CHANGED','TAB_SELECTION_CHANGED');throw Error('TAB_STATE_CHANGED');}
      route={...route,eligible_tab_count:available.length};
      return {...route};
    }
    async function execute(dispatch){
      if(['ASCEND_MAP_WORKSPACE','ASCEND_MAP_NAVIGATE_SECTION'].includes(dispatch.command.operation)&&dispatch.command.owner_present){
        const active=await tabs.query({active:true,lastFocusedWindow:true});
        if(active.length!==1||active[0].id!==dispatch.route.tab_id)throw Error('MAPPING_OWNER_NOT_PRESENT');
      }
      const bound=await current();
      if(JSON.stringify(bound)!==JSON.stringify(dispatch.route)){
        // Compare explicit fields independent of host JSON key order.
        if(Object.keys(bound).length!==Object.keys(dispatch.route||{}).length||Object.keys(bound).some(k=>bound[k]!==dispatch.route[k]))throw Error('TAB_STATE_CHANGED');
      }
      (runtime?FreightDeskX1Contract.validateRuntime:FreightDeskX1Contract.validate)(dispatch.command);
      if(!(runtime?FreightDeskX1Contract.runtimeOperations:FreightDeskX1Contract.operations.slice(0,4)).includes(dispatch.command.operation))throw Error('COMMAND_NOT_ALLOWED');
      if(pending||typeof dispatch.deadline!=='number'||dispatch.deadline<=Date.now()/1000||dispatch.deadline>Date.now()/1000+13)throw Error('READ_TIMEOUT');
      const g=generation;
      const result=await new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>cancel('READ_TIMEOUT'),Math.max(1,(dispatch.deadline-Date.now()/1000)*1000));
        pending={resolve,reject,timer,kind:'RESULT'};
        channel.postMessage({kind:runtime?'X1_RUNTIME_DISPATCH_V2':'IDENTITY_DISPATCH',command:dispatch.command,document_id:bound.document_id,deadline:dispatch.deadline,...(runtime?{document_generation:handshake.document_generation}:{})});
      });
      if(g!==generation)throw Error('TAB_STATE_CHANGED');
      const finalRoute=await current();
      if(['ASCEND_MAP_WORKSPACE','ASCEND_MAP_NAVIGATE_SECTION'].includes(dispatch.command.operation)&&dispatch.command.owner_present){
        const active=await tabs.query({active:true,lastFocusedWindow:true});
        if(active.length!==1||active[0].id!==dispatch.route.tab_id)throw Error('MAPPING_OWNER_NOT_PRESENT');
      }
      if(Object.keys(bound).some(k=>bound[k]!==finalRoute[k]))throw Error('TAB_STATE_CHANGED');
      return result;
    }
    async function ownerPresence(leaseExpiresAt){
      if(!runtime||pending||typeof leaseExpiresAt!=='number'||!Number.isFinite(leaseExpiresAt)||leaseExpiresAt<=Date.now()/1000)return false;
      const bound=await current(),g=generation;
      const active=await tabs.query({active:true,lastFocusedWindow:true});
      if(active.length!==1||active[0].id!==bound.tab_id){trace('SESSION_PROOF_INVALIDATED','FOREGROUND_LOST');return false;}
      trace('OWNER_READINESS_REQUESTED');
      const requestId=crypto.randomUUID().replaceAll('-','');
      const present=await new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>cancel('READ_TIMEOUT'),3000);
        pending={resolve,reject,timer,kind:'OWNER_READINESS',requestId};
        channel.postMessage({kind:'X1_OWNER_READINESS',request_id:requestId,document_id:bound.document_id,
          document_generation:handshake.document_generation,lease_expires_at:leaseExpiresAt});
      });
      if(g!==generation){trace('SESSION_PROOF_INVALIDATED','READINESS_BINDING_CHANGED');return false;}
      const after=await current(),finalActive=await tabs.query({active:true,lastFocusedWindow:true});
      if(after.document_id!==bound.document_id){trace('SESSION_PROOF_INVALIDATED','DOCUMENT_ID_CHANGED');return false;}
      if(finalActive.length!==1||finalActive[0].id!==bound.tab_id){trace('SESSION_PROOF_INVALIDATED','FOREGROUND_LOST');return false;}
      if(present)trace('OWNER_READINESS_PROVED');
      return present;
    }
    return Object.freeze({list,select,current,execute,cancel,ownerPresence,handshake:()=>handshake?{...handshake}:null});
  }
  globalThis.FreightDeskTabRouter=Object.freeze({create});
})();
