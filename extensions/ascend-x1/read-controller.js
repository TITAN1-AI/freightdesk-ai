(() => {
  'use strict';
  function create(tabs,paired,send){
    let plan=null,index=0,last=null,pending=null,revision=null,busy=false,state='PAIRED';
    const router=FreightDeskTabRouter.create(tabs,paired,code=>{
      if(busy&&state!=='IDENTITY_VERIFIED_READS_BLOCKED'&&code!=='TAB_SELECTION_REQUIRED')state='STOPPED';
    });
    const id=()=>crypto.randomUUID().replaceAll('-','');
    function reset(){
      router.cancel('PAIRING_LOST');plan=null;state='PAIRING_REQUIRED';busy=false;
      if(pending){const p=pending;pending=null;clearTimeout(p.timer);p.reject(Error('PAIRING_LOST'));}
    }
    async function rpc(body){
      if(!paired())throw Error('PAIRING_LOST');
      if(pending)throw Error('READ_SEQUENCE_INVALID');
      return new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>{reset();reject(Error('READ_TIMEOUT'));},15000);
        pending={resolve,reject,timer,body};
        send(body).catch(()=>reset());
      });
    }
    async function accept(body){
      if(!pending||!paired())throw Error('PAIRING_ACK_INVALID');
      if(body.kind==='READ_DISPATCH'){
        if(pending.body.kind!=='READ_REQUEST'||JSON.stringify(body.command)!==JSON.stringify(pending.body.command)){
          if(pending.body.kind!=='READ_REQUEST'||Object.keys(pending.body.command).some(k=>body.command?.[k]!==pending.body.command[k])||
            Object.keys(body.command||{}).length!==Object.keys(pending.body.command).length)throw Error('PAIRING_ACK_INVALID');
        }
        if(body.attempt_id!==plan?.attempt_id)throw Error('PAIRING_ACK_INVALID');
        const active=pending;
        pending.body={kind:'AWAITING_RECEIPT'};
        // Do not block native heartbeat verification while the DOM command stabilizes.
        (async()=>{
          let result;
          try{result=await router.execute(body);}catch(error){result={evidence:null,error_code:FreightDeskReadErrors.safe(error)};}
          if(!paired()||pending!==active)return;
          await send({kind:'READ_RESULT',request_id:id(),command_request_id:body.command.request_id,route:body.route,...result});
        })().catch(()=>reset());return;
      }
      if(!['READ_PLAN','READ_RECEIPT','READ_ERROR'].includes(body.kind))throw Error('PAIRING_ACK_INVALID');
      if(body.kind==='READ_PLAN'&&pending.body.kind!=='READ_PLAN'||body.kind==='READ_RECEIPT'&&pending.body.kind!=='AWAITING_RECEIPT'&&pending.body.kind!=='READ_REQUEST')throw Error('PAIRING_ACK_INVALID');
      const p=pending;pending=null;clearTimeout(p.timer);p.resolve(body);
    }
    async function handle(message){
      if(message.action==='READ_STATUS'&&Object.keys(message).length===1)return {
        state:paired()?(state==='PAIRING_REQUIRED'?'PAIRED':state):'PAIRING_REQUIRED',receipt:last,index};
      if(!paired())throw Error('PAIRING_LOST');
      if(message.action==='LIST_ASCEND_TABS'&&Object.keys(message).length===1)return {tabs:await router.list()};
      if(message.action==='SELECT_ASCEND_TAB'&&Object.keys(message).sort().join()==='action,tab_id'){
        if(busy||index!==0)throw Error('READ_SEQUENCE_INVALID');
        return {selected_tab:await router.select(message.tab_id)};
      }
      if(message.action==='LOAD_READ_PLAN'&&Object.keys(message).length===1){
        if(busy||index!==0)throw Error('READ_SEQUENCE_INVALID');
        const response=await rpc({kind:'READ_PLAN',request_id:id()});
        if(response.kind!=='READ_PLAN')throw Error(FreightDeskReadErrors.safe(response.error_code));
        plan=response.plan;state='READ_ONLY_READY';return {state,plan};
      }
      if(message.action==='READ_NEXT'&&Object.keys(message).length===1){
        if(busy||state!=='READ_ONLY_READY'||!plan||index>=4)throw Error('READ_SEQUENCE_INVALID');
        busy=true;
        try{
          const route=await router.current(),command={version:1,request_id:id(),operation:FreightDeskX1Contract.operations[index],
            load_id:index>=2?plan.load_id:null,tenant_id:'booking-logistics',actor:'FreightDesk/Avery',expected_revision:index>=2?revision:null};
          const response=await rpc({kind:'READ_REQUEST',command,route});
          if(response.kind!=='READ_RECEIPT')throw Error(FreightDeskReadErrors.safe(response.error_code));
          last=response.receipt;
          if(last.state==='STOPPED'){state='STOPPED';router.cancel();return {state,receipt:last};}
          if(last.request_id!==command.request_id||last.operation!==command.operation)throw Error('RECEIPT_INVALID');
          if(index===1)revision=last.board_hash;
          index++;state=index===4?'IDENTITY_VERIFIED_READS_BLOCKED':'READ_ONLY_READY';
          if(index===4)router.cancel();
          return {state,receipt:last,index};
        }catch(error){state='STOPPED';router.cancel();throw error;}finally{busy=false;}
      }
      throw Error('COMMAND_NOT_ALLOWED');
    }
    return Object.freeze({handle,accept,reset});
  }
  globalThis.FreightDeskReadController=Object.freeze({create});
})();
