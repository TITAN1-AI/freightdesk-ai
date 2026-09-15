importScripts('build.js','contract.js','pairing.js','enrollment.js','diagnostics.js','read-errors.js','tab-router.js','read-controller.js','runtime.js');
const PRODUCTION_CONNECTION_ENABLED=false;
const NATIVE_HOST='com.freightdesk.ascend_x1';
const D=FreightDeskPairingDiagnostics;
let state='OFFLINE_PROTOTYPE',resultCode='PAIRING_FILE_NOT_SELECTED';
let port=null,pairing=null,timer=null,deadline=null,epoch=0;
let sending=Promise.resolve();
let enrollmentHandle=null,reconnectFailures=0,reconnectTimer=null;
const WORKER_UI_STATES=Object.freeze(['OFFLINE_PROTOTYPE','NOT_ENROLLED','HOST_NOT_REGISTERED','HOST_UNAVAILABLE','PAIRING_STALE','PAIRING_REQUIRED','ERROR']);
const reads=FreightDeskReadController.create(chrome.tabs,()=>state==='PAIRED'&&!!pairing&&!!port,sendSigned);
const runtime=FreightDeskRuntime.create(chrome.tabs,()=>state==='PAIRED'&&!!pairing&&!!port,sendSigned,()=>queueMicrotask(()=>runtime.wake()));
async function platform(){
  if(!chrome.runtime.getPlatformInfo)return null;
  try{
    const info=await chrome.runtime.getPlatformInfo();
    return info&&typeof info.os==='string'?info.os:null;
  }catch{return null;}
}
function sendSigned(body){
  const current=port,bound=pairing;
  const next=sending.then(async()=>{
    if(!current||!bound||port!==current||pairing!==bound||state!=='PAIRED')throw Error('PAIRING_LOST');
    const envelope=await FreightDeskPairing.sign(bound,body);
    if(port!==current||pairing!==bound)throw Error('PAIRING_LOST');
    current.postMessage({kind:'AUTHENTICATED',protocol:1,envelope});
  });
  sending=next.catch(()=>{});return next;
}
const requestId=()=>crypto.randomUUID().replaceAll('-','');
const view=()=>({...D.result(state,resultCode),extension_version:FreightDeskBuild.extension_version,
  native_host_name:NATIVE_HOST,native_host_windows_only:true,production_connection_enabled:PRODUCTION_CONNECTION_ENABLED});
function stop(next,code){
  epoch++;state=next;resultCode=D.safe(code);pairing=null;
  reads.reset();
  runtime.reset();
  clearInterval(timer);clearTimeout(deadline);timer=null;deadline=null;
  const old=port;port=null;if(old)old.disconnect();
  if(enrollmentHandle&&next==='HOST_UNAVAILABLE')scheduleReconnect();
}
function scheduleReconnect(){
  clearTimeout(reconnectTimer);
  if(!enrollmentHandle||reconnectFailures>=5)return;
  const delay=[1000,2000,4000,8000,16000][reconnectFailures++];
  reconnectTimer=setTimeout(()=>{reconnectTimer=null;resumeEnrolled();},delay);
}
async function resumeEnrolled(){
  if(port&&pairing?.enrollment&&pairing.expires*1000-Date.now()<60000){stop('HOST_UNAVAILABLE','PAIRING_INTERRUPTED');return;}
  if(port||['PAIRING_STALE','ERROR'].includes(state))return;
  if(!enrollmentHandle&&chrome.storage?.local)enrollmentHandle=await FreightDeskEnrollment.load(chrome.storage.local);
  if(!enrollmentHandle){
    const os=await platform();
    if(os&&os!=='win'){state='HOST_NOT_REGISTERED';resultCode='NATIVE_HOST_WINDOWS_ONLY';return;}
    state='NOT_ENROLLED';return;
  }
  try{connect(null,null,enrollmentHandle);}catch{stop('HOST_UNAVAILABLE','HOST_HANDSHAKE_FAILED');}
}
function connect(localPairing,diagnostic=null,resumeHandle=null){
  stop('PAIRING_REQUIRED',diagnostic?.result_code||'PAIRING_HANDSHAKE_PENDING');pairing=localPairing;
  const current=chrome.runtime.connectNative(NATIVE_HOST);port=current;
  let verified=false,queue=Promise.resolve();
  deadline=setTimeout(()=>{if(port===current)stop('HOST_UNAVAILABLE',diagnostic?'PAIRING_PERSIST_FAILED':'HOST_HANDSHAKE_FAILED');},10000);
  current.onMessage.addListener(message=>{
    queue=queue.then(async()=>{
      if(port!==current)return;
      if(!message||new TextEncoder().encode(JSON.stringify(message)).length>65536||message.protocol!==1)
        throw Error('PAIRING_ACK_INVALID');
      if(message.kind==='ERROR'){
        const legacy={stale_pairing:'PAIRING_EXPIRED',pairing_expired:'PAIRING_EXPIRED',pairing_already_used:'PAIRING_ALREADY_CONSUMED',
          native_pairing_proof_invalid:'PAIRING_PROOF_REJECTED',extension_id_mismatch:'EXTENSION_ID_MISMATCH',
          pairing_protection_failed:'PAIRING_DPAPI_FAILED',local_configuration_or_pairing_missing:'PAIRING_REQUIRED'};
        const persistent=resumeHandle||pairing?.enrollment;
        if(persistent&&['stale_pairing','pairing_expired','native_session_expired','native_read_timeout'].includes(message.error_code)){
          stop('HOST_UNAVAILABLE','PAIRING_INTERRUPTED');return;
        }
        stop(persistent?'PAIRING_STALE':'PAIRING_REQUIRED',message.result_code||legacy[message.error_code]||'HOST_HANDSHAKE_FAILED');return;
      }
      if(message.kind==='DIAGNOSTIC_SAVED'){
        if(diagnostic)stop('PAIRING_REQUIRED',diagnostic.result_code);
        return;
      }
      if(diagnostic)throw Error('HOST_HANDSHAKE_FAILED');
      if(message.kind==='RESUME_CHALLENGE'){
        if(!resumeHandle||verified)throw Error('PAIRING_ACK_INVALID');
        pairing=await FreightDeskEnrollment.resume(message,resumeHandle,chrome.runtime.id);
        const proof=await FreightDeskPairing.proof(pairing,message.challenge);
        if(port===current)current.postMessage({kind:'RESUME_PROOF',protocol:1,request_id:requestId(),proof});return;
      }
      if(message.kind==='CHALLENGE'){
        if(!pairing){stop('PAIRING_REQUIRED','HOST_REACHABLE');return;}
        let proof;
        try{proof=await FreightDeskPairing.proof(pairing,message.challenge);}catch{throw Error('PAIRING_BINDING_MISMATCH');}
        if(port!==current)return;
        current.postMessage({kind:pairing.enrollment?'ENROLL_PAIR':'PAIR',protocol:1,request_id:requestId(),proof});return;
      }
      if(message.kind!=='AUTHENTICATED'||!pairing)throw Error('PAIRING_ACK_INVALID');
      let body;
      try{body=await FreightDeskPairing.verify(pairing,message.envelope);}catch{throw Error('PAIRING_ACK_INVALID');}
      if(port!==current)return;
      if(body.protocol!==1||body.tenant_id!=='booking-logistics'||body.actor!=='FreightDesk/Avery'||body.state!=='PAIRED'||
        body.read_dispatch_enabled!==false)throw Error('PAIRING_ACK_INVALID');
      if(!verified&&(body.installation_id!==pairing.installation||!resumeHandle&&body.generation!==pairing.generation))throw Error('PAIRING_ACK_INVALID');
      if(body.kind){
        if(!verified)throw Error('PAIRING_ACK_INVALID');
        if(body.kind.startsWith('RUNTIME_')){await runtime.accept(body);return;}
        await reads.accept(body);return;
      }
      clearTimeout(deadline);deadline=null;
      if(!verified&&pairing.enrollment){
        if(body.enrollment!==true||!FreightDeskEnrollment.validHandle(body.enrollment_handle)||
          resumeHandle&&body.enrollment_handle!==resumeHandle||!Number.isInteger(body.session_expires_at)||
          body.session_expires_at<=Date.now()/1000||body.session_expires_at>Date.now()/1000+601)throw Error('PAIRING_ACK_INVALID');
        await FreightDeskEnrollment.save(chrome.storage.local,body.enrollment_handle);
        enrollmentHandle=body.enrollment_handle;pairing.expires=body.session_expires_at;reconnectFailures=0;
      }
      if(!verified&&!pairing.enrollment){
        current.postMessage({kind:'PAIRING_DIAGNOSTIC',protocol:1,request_id:requestId(),diagnostic:
          D.metadata('ACK_VERIFICATION','PAIRING_SUCCESS',{extension_id_match:true,bootstrap_expired:false,bootstrap_consumed:true})});
      }
      verified=true;state='PAIRED';resultCode='PAIRING_SUCCESS'; // Read readiness belongs to the separately gated controller.
      if(pairing.enrollment)queueMicrotask(()=>runtime.wake());
      if(!timer)timer=setInterval(()=>{
        if(!pairing||port!==current)return;
        if(pairing.enrollment&&pairing.expires*1000-Date.now()<60000){stop('HOST_UNAVAILABLE','PAIRING_INTERRUPTED');return;}
        sendSigned({kind:'STATUS',request_id:requestId()}).then(()=>{
          if(port===current){
            deadline=setTimeout(()=>{if(port===current)stop('HOST_UNAVAILABLE','HOST_HANDSHAKE_FAILED');},10000);
          }
        }).catch(()=>{if(port===current)stop('PAIRING_REQUIRED','PAIRING_EXPIRED');});
      },20000);
    }).catch(error=>{
      if(port===current){
        if(diagnostic)stop('PAIRING_REQUIRED','PAIRING_PERSIST_FAILED');
        else if(resumeHandle||pairing?.enrollment)stop('PAIRING_STALE',D.safe(error?.message));
        else diagnose(D.metadata('ACK_VERIFICATION',D.safe(error?.message)));
      }
    });
  });
  current.onDisconnect.addListener(()=>{
    const error=chrome.runtime.lastError;
    if(port!==current)return;
    const missing=error&&/not found|not registered/i.test(error.message||'');
    stop(missing?'HOST_NOT_REGISTERED':'HOST_UNAVAILABLE',
      diagnostic?'PAIRING_PERSIST_FAILED':missing?'HOST_NOT_REGISTERED':'HOST_HANDSHAKE_FAILED');
  });
  if(diagnostic)current.postMessage({kind:'PAIRING_DIAGNOSTIC',protocol:1,request_id:requestId(),diagnostic});
  else if(resumeHandle)current.postMessage({kind:'RESUME',protocol:1,request_id:requestId(),enrollment_handle:resumeHandle});
  else current.postMessage({kind:localPairing?.enrollment?'ENROLL_HELLO':'HELLO',protocol:1,request_id:requestId()});
}
function diagnose(metadata){
  // Same native pipe, safe metadata only; no pairing redemption or secret is sent on this path.
  try{connect(null,metadata);}catch{stop('PAIRING_REQUIRED','PAIRING_PERSIST_FAILED');}
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  // Both the toolbar popup and its persistent packaged tab have this exact trusted URL.
  if(sender.id!==chrome.runtime.id||sender.url!==chrome.runtime.getURL('popup.html')||
    (sender.frameId!==undefined&&sender.frameId!==0))return false;
  if(!message||typeof message!=='object')return false;
  if(['RUNTIME_MAPPING_CAPTURE','RUNTIME_STATUS','RUNTIME_TABS','RUNTIME_REBIND','RUNTIME_SELECT'].includes(message.action)){
    runtime.handle(message).then(result=>reply(message.action==='RUNTIME_STATUS'?{...result,
      ...(state!=='PAIRED'?{state:WORKER_UI_STATES.includes(state)?state:'NOT_ENROLLED'}:{}),
      extension:'CONNECTED',native_host:port&&state==='PAIRED'?'CONNECTED':'DISCONNECTED',pairing:state==='PAIRED'?'VALID':'UNKNOWN',
      native_host_name:NATIVE_HOST,native_host_windows_only:true,production_connection_enabled:PRODUCTION_CONNECTION_ENABLED}:result))
      .catch(()=>reply({state:'ERROR',error_code:'COMMAND_NOT_ALLOWED'}));return true;
  }
  if(['READ_STATUS','LIST_ASCEND_TABS','SELECT_ASCEND_TAB','LOAD_READ_PLAN','READ_NEXT'].includes(message.action)){
    reads.handle(message).then(reply).catch(error=>reply({state:'STOPPED',error_code:FreightDeskReadErrors.safe(error),
      remediation:'Stop. Review the safe receipt locally; no automatic retry or operational extraction.'}));return true;
  }
  if(message.action==='STATUS'&&Object.keys(message).length===1){reply(view());return false;}
  if(message.action==='DISCONNECT'&&Object.keys(message).length===1){stop('PAIRING_REQUIRED','PAIRING_INTERRUPTED');reply(view());return false;}
  if(message.action==='CHECK_HOST'&&Object.keys(message).length===1){
    (async()=>{
      const os=await platform();
      if(os&&os!=='win'){state='HOST_NOT_REGISTERED';resultCode='NATIVE_HOST_WINDOWS_ONLY';}
      else if(!port)try{connect(null);}catch{stop('HOST_UNAVAILABLE','HOST_HANDSHAKE_FAILED');}
      reply(view());
    })();
    return true;
  }
  if(message.action==='PAIR_DIAGNOSTIC'&&Object.keys(message).sort().join()==='action,diagnostic'){
    const m=message.diagnostic;
    const keys=['handshake_stage','result_code','extension_id_match','bootstrap_expired','bootstrap_consumed'];
    if(!m||Object.keys(m).some(k=>!keys.includes(k))||!D.stages.includes(m.handshake_stage)||!Object.hasOwn(D.results,m.result_code)||
      Object.keys(m).some(k=>keys.slice(2).includes(k)&&typeof m[k]!=='boolean')){
      reply(D.result('PAIRING_REQUIRED','COMMAND_NOT_ALLOWED'));return false;
    }
    diagnose(D.metadata(m.handshake_stage,m.result_code,m));reply(view());return false;
  }
  if(message.action==='PAIR_LOCAL'&&Object.keys(message).sort().join()==='action,bundle'){
    stop('PAIRING_REQUIRED','PAIRING_VALIDATING');const requestedEpoch=epoch;
    const importer=message.bundle?.purpose==='X1_ENROLLMENT'?FreightDeskEnrollment.importEnrollment:FreightDeskPairing.importBundle;
    importer(message.bundle,chrome.runtime.id).then(p=>{
      if(epoch===requestedEpoch){
        // connect() advances epoch before connectNative; catch here so its exception is not mistaken
        // for an obsolete async import and silently left at PAIRING_REQUIRED.
        try{connect(p);}catch{stop('HOST_UNAVAILABLE','HOST_HANDSHAKE_FAILED');}
      }
      reply(view());
    }).catch(error=>{
      if(epoch===requestedEpoch){
        const code=D.safe(error?.message),flags={};
        if(code==='EXTENSION_ID_MISMATCH')flags.extension_id_match=false;
        if(code==='PAIRING_EXPIRED'){flags.extension_id_match=true;flags.bootstrap_expired=true;}
        const stage=code==='PAIRING_EXPIRED'?'EXPIRY_VALIDATION':code==='EXTENSION_ID_MISMATCH'?'EXTENSION_ID_VALIDATION':'SCHEMA_VALIDATION';
        diagnose(D.metadata(stage,code,flags));
      }
      reply(view());
    });return true;
  }
  reply({state:'ERROR',error_code:'command_not_allowed',remediation:D.results.COMMAND_NOT_ALLOWED});return false;
});
// Alarms survive MV3 worker sleep. They wake the host; the durable host lease and cadence decide all reads.
if(chrome.storage?.local&&chrome.alarms){
  chrome.alarms.create('x1-runtime-wake',{periodInMinutes:1});
  const wake=()=>resumeEnrolled().then(()=>{if(state==='PAIRED')return runtime.wake();}).catch(()=>stop('HOST_UNAVAILABLE','HOST_HANDSHAKE_FAILED'));
  chrome.alarms.onAlarm.addListener(alarm=>{if(alarm.name==='x1-runtime-wake')wake();});
  chrome.runtime.onStartup?.addListener(wake);
  wake();
}
