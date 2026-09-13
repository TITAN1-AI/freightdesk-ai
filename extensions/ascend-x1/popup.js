'use strict';
const D=FreightDeskPairingDiagnostics;
const states=new Set(['OFFLINE_PROTOTYPE','HOST_NOT_REGISTERED','PAIRING_REQUIRED','PAIRED','HOST_UNAVAILABLE','ERROR','NOT_ENROLLED','PAIRING_STALE']);
const input=document.getElementById('bundle');
let busy=false,localResult=null,uiEpoch=0;
function render(result){
  const valid=states.has(result?.state)&&!(result?.error_code==='PAIRING_SUCCESS'&&result.state!=='PAIRED');
  const safe=D.result(valid?result.state:'PAIRING_REQUIRED',valid?result.error_code:'PAIRING_ACK_INVALID');
  document.getElementById('state').textContent=safe.state;
  document.getElementById('result').textContent=safe.error_code;
  document.getElementById('remediation').textContent=safe.remediation;
}
async function diagnostic(code,stage){
  const current=++uiEpoch;
  localResult=D.result('PAIRING_REQUIRED',code);render(localResult);
  try{
    const result=await chrome.runtime.sendMessage({action:'PAIR_DIAGNOSTIC',diagnostic:D.metadata(stage,code)});
    if(current===uiEpoch&&result?.error_code==='PAIRING_PERSIST_FAILED'){localResult=result;render(result);}
  }catch{ /* Retain the safe local result; a disconnected host cannot persist an audit. */ }
}
async function send(message){
  try{
    const result=await chrome.runtime.sendMessage(message);
    if(localResult&&result?.error_code==='PAIRING_PERSIST_FAILED')localResult=result;
    if(!busy)render(localResult||result);return result;
  }
  catch{if(!localResult)render(D.result('PAIRING_REQUIRED','PAIRING_INTERRUPTED'));return null;}
}
document.getElementById('check').onclick=async()=>{
  localResult=null;++uiEpoch;await send({action:'CHECK_HOST'});
};
document.getElementById('disconnect').onclick=async()=>{
  localResult=null;++uiEpoch;await send({action:'DISCONNECT'});
};
// Explicit import reads .files directly even if the browser does not deliver change.
// The persistent extension panel survives focus loss while a native file picker is open.
input.onchange=()=>{
  localResult=D.result('PAIRING_REQUIRED',input.files?.[0]?'PAIRING_FILE_SELECTED':'PAIRING_FILE_NOT_SELECTED');
  ++uiEpoch;render(localResult);
};
input.oncancel=()=>diagnostic('PAIRING_FILE_NOT_SELECTED','FILE_INPUT');
document.getElementById('import').onclick=async()=>{
  if(busy)return;
  busy=true;const current=++uiEpoch;localResult=null;
  render(D.result('PAIRING_REQUIRED','PAIRING_VALIDATING'));
  let stage='FILE_INPUT';
  try{
    const file=input.files?.[0];
    if(!file)throw Error('PAIRING_FILE_NOT_SELECTED');
    if(file.size>4096)throw Error('PAIRING_SCHEMA_INVALID');
    stage='FILE_READ';let text;
    try{text=await file.text();}catch{throw Error('PAIRING_FILE_READ_FAILED');}
    stage='JSON_PARSE';let bundle;
    try{bundle=JSON.parse(text);}catch{throw Error('PAIRING_SCHEMA_INVALID');}
    text=null;
    if(current!==uiEpoch)return;
    stage='SCHEMA_VALIDATION';
    const result=await chrome.runtime.sendMessage({action:'PAIR_LOCAL',bundle});
    if(current===uiEpoch)render(result);
  }catch(error){
    if(current===uiEpoch)await diagnostic(D.safe(error?.message)==='HOST_HANDSHAKE_FAILED'?'PAIRING_INTERRUPTED':error.message,stage);
  }finally{
    // Also reset after parse/read/host failures so the same file path can fire change again.
    input.value='';busy=false;
  }
};
send({action:'STATUS'});
setInterval(()=>send({action:'STATUS'}),1000);
