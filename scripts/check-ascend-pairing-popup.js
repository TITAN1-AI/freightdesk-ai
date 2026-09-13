'use strict';
// Tests the real popup JS with synthetic file objects and Chrome ports. No browser/host launch.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {worker,bundle,challenge,paired,signed,until,pause}=require('./check-ascend-native.js');
const root=path.join(__dirname,'../extensions/ascend-x1');
function popup(w){
  let active=true;const elements={},polls=[];
  for(const id of ['state','result','remediation','bundle','import','check','disconnect'])elements[id]={textContent:'',files:[]};
  let selected='';Object.defineProperty(elements.bundle,'value',{get:()=>selected,set:v=>{selected=v;if(v==='')elements.bundle.files=[];}});
  const sandbox={document:{getElementById:id=>elements[id]},chrome:{runtime:{sendMessage:async message=>{
    if(!active)throw Error('popup_context_gone');
    const result=await w.send(message);if(!active)throw Error('popup_context_gone');return result;
  }}},setInterval:fn=>polls.push(fn)};
  vm.createContext(sandbox);
  for(const name of ['diagnostics.js','popup.js'])vm.runInContext(fs.readFileSync(path.join(root,name),'utf8'),sandbox);
  return {elements,polls,close(){active=false;},result:()=>elements.result.textContent,state:()=>elements.state.textContent,
    choose(file,change=true){elements.bundle.files=file?[file]:[];selected=file?'chosen-local-file':'';if(change)elements.bundle.onchange();},
    import:()=>elements.import.onclick(),poll:()=>polls[0]()};
}
const file=value=>({size:1000,text:async()=>JSON.stringify(value)});
async function acknowledge(w,b,defect=null){
  const p=w.ports.findLast(p=>p.sent[0]?.kind==='HELLO'),c=challenge(b),api=w.sandbox.FreightDeskPairing;
  if(defect){p.emit({kind:'ERROR',protocol:1,result_code:defect});return;}
  p.emit({kind:'CHALLENGE',protocol:1,challenge:c});await until(()=>p.sent.length===2);
  const body={state:'PAIRED',protocol:1,tenant_id:b.tenant_id,actor:b.actor,installation_id:b.installation_id,
    generation:b.generation,read_dispatch_enabled:false};
  p.emit({kind:'AUTHENTICATED',protocol:1,envelope:signed(api,b,c,body)});
  await until(()=>w.state()==='PAIRED');
}
async function main(){
  // Same path twice; second attempt is not skipped by a stale input value.
  const w=worker(),ui=popup(w),b=bundle(),chosen=file(b);
  await ui.poll();ui.choose(chosen);assert.equal(ui.result(),'PAIRING_FILE_SELECTED');
  await ui.import();assert.equal(ui.state(),'PAIRING_REQUIRED');assert.equal(ui.elements.bundle.value,'');
  await acknowledge(w,b);await ui.poll();assert.equal(ui.result(),'PAIRING_SUCCESS');
  ui.choose(chosen);await ui.import();await acknowledge(w,b,'PAIRING_ALREADY_CONSUMED');
  await until(()=>w.state()==='PAIRING_REQUIRED');await ui.poll();assert.equal(ui.result(),'PAIRING_ALREADY_CONSUMED');
  assert.equal(ui.elements.bundle.value,'');

  // Real file in .files with no change callback: explicit Import remains functional.
  const noChange=worker(),panel=popup(noChange),b2=bundle();panel.choose(file(b2),false);
  await panel.import();await acknowledge(noChange,b2);await panel.poll();assert.equal(panel.result(),'PAIRING_SUCCESS');
  // No change event and no file cannot be confused with a handshake attempt.
  const absent=popup(worker());await absent.import();assert.equal(absent.result(),'PAIRING_FILE_NOT_SELECTED');
  await absent.poll();assert.equal(absent.result(),'PAIRING_FILE_NOT_SELECTED');

  const cases=[
    [{size:100,text:async()=>'{PRIVATE_RAW_JSON'},'PAIRING_SCHEMA_INVALID'],
    [{size:100,text:async()=>{throw Error('PRIVATE_FILE_ERROR');}},'PAIRING_FILE_READ_FAILED'],
    [{size:5000,text:async()=>''},'PAIRING_SCHEMA_INVALID'],
    [file({...bundle(),key:'PRIVATE_SECRET'}),'PAIRING_SCHEMA_INVALID'],
    [file({...bundle(),expires_at:1}),'PAIRING_EXPIRED'],
    [file({...bundle(),extension_id:'b'.repeat(32)}),'EXTENSION_ID_MISMATCH']
  ];
  for(const [selected,expected] of cases){
    const x=worker(),p=popup(x);p.choose(selected);await p.import();await p.poll();
    assert.equal(p.result(),expected);assert.equal(p.elements.bundle.value,'');
    assert.equal(p.state(),'PAIRING_REQUIRED');
    assert.ok(!JSON.stringify(x.ports.flatMap(port=>port.sent)).includes('PRIVATE'));
    for(const element of Object.values(p.elements))assert.ok(!element.textContent.includes('PRIVATE'));
    assert.ok(x.ports.flatMap(port=>port.sent).every(m=>m.kind==='PAIRING_DIAGNOSTIC'));
  }
  const cancel=popup(worker());await cancel.elements.bundle.oncancel();assert.equal(cancel.result(),'PAIRING_FILE_NOT_SELECTED');

  // Popup closure after sending does not stop an in-flight worker handshake or lose its result.
  const lives=worker(),first=popup(lives),b3=bundle();first.choose(file(b3));await first.import();first.close();
  await acknowledge(lives,b3);const reopened=popup(lives);await reopened.poll();assert.equal(reopened.result(),'PAIRING_SUCCESS');
  // A worker restart never restores a key or trusts the previous popup state.
  const restarted=worker(),fresh=popup(restarted);await fresh.poll();assert.notEqual(fresh.state(),'PAIRED');
  assert.equal(restarted.ports.length,0);
  // Restart while HELLO is pending: replacement worker has no key and cannot finish the old handshake.
  const unfinished=worker();await unfinished.send({action:'PAIR_LOCAL',bundle:bundle()});
  unfinished.ports[0].crash('Worker context terminated.');
  const replacement=worker();await replacement.send({action:'CHECK_HOST'});
  replacement.ports[0].emit({kind:'CHALLENGE',protocol:1,challenge:challenge(bundle())});
  await until(()=>replacement.ports[0].closed);assert.equal(replacement.state(),'PAIRING_REQUIRED');
  assert.equal(replacement.ports[0].sent.length,1); // No proof replay from the dead worker.
  // Picker/read outlives the popup: no file or pairing is silently retained for the next popup.
  const closingWorker=worker(),closing=popup(closingWorker);let finishRead;
  closing.choose({size:1000,text:()=>new Promise(resolve=>{finishRead=resolve;})});
  const importing=closing.import();closing.close();finishRead(JSON.stringify(bundle()));await importing;
  assert.equal(closingWorker.ports.length,0);
  const afterClose=popup(closingWorker);await afterClose.import();assert.equal(afterClose.result(),'PAIRING_FILE_NOT_SELECTED');
  // Lost popup/worker messaging surfaces a specific interruption rather than silent PAIRING_REQUIRED.
  const interrupted=popup({send:async()=>{throw Error('PRIVATE_CONTEXT');}});
  interrupted.choose(file(bundle()));await interrupted.import();assert.equal(interrupted.result(),'PAIRING_INTERRUPTED');
  // A stale STATUS request must never overwrite a local parse error (the 0.1.1 regression).
  const race=popup({send:async()=>({state:'PAIRING_REQUIRED',error_code:'PAIRING_REQUIRED'})});
  race.choose({size:20,text:async()=>'{'});await race.import();await race.poll();assert.equal(race.result(),'PAIRING_SCHEMA_INVALID');
  // Pairing status cannot claim READ_ONLY_READY. The separate read controller owns that state.
  const unsafe=popup({send:async()=>({state:'READ_ONLY_READY',error_code:'PAIRING_SUCCESS',remediation:'PRIVATE'})});
  await unsafe.poll();assert.equal(unsafe.state(),'PAIRING_REQUIRED');assert.ok(!unsafe.elements.remediation.textContent.includes('PRIVATE'));
  // Signed acknowledgement with a missing installation binding cannot promote PAIRED.
  const pending=worker(),b4=bundle();await pending.send({action:'PAIR_LOCAL',bundle:b4});
  const port=pending.ports[0],c=challenge(b4);port.emit({kind:'CHALLENGE',protocol:1,challenge:c});await until(()=>port.sent.length===2);
  port.emit({kind:'AUTHENTICATED',protocol:1,envelope:signed(pending.sandbox.FreightDeskPairing,b4,c,
    {state:'PAIRED',protocol:1,tenant_id:b4.tenant_id,actor:b4.actor,read_dispatch_enabled:false})});
  await until(()=>pending.ports.length===2);
  assert.equal((await pending.send({action:'STATUS'})).error_code,'PAIRING_ACK_INVALID');
  // Log acknowledgement failure is surfaced, with no reconnect loop.
  const logging=worker();await logging.send({action:'PAIR_DIAGNOSTIC',diagnostic:{handshake_stage:'FILE_INPUT',result_code:'PAIRING_FILE_NOT_SELECTED'}});
  await pause();assert.equal(logging.ports.length,1);
  const rejected=worker();await rejected.send({action:'CHECK_HOST'});
  rejected.ports[0].emit({kind:'ERROR',protocol:1,result_code:'PAIRING_PERSIST_FAILED'});
  await until(()=>rejected.ports[0].closed);assert.equal((await rejected.send({action:'STATUS'})).error_code,'PAIRING_PERSIST_FAILED');
  // A synchronous connectNative exception must not be hidden by connect() advancing the epoch.
  const launchError=worker();launchError.sandbox.chrome.runtime.connectNative=()=>{throw Error('PRIVATE_START_ERROR');};
  await launchError.send({action:'PAIR_LOCAL',bundle:bundle()});
  assert.equal((await launchError.send({action:'STATUS'})).error_code,'HOST_HANDSHAKE_FAILED');
  assert.equal(launchError.state(),'HOST_UNAVAILABLE');
  // Protocol's seven read commands and pairing-only switch remain independent.
  const {w:bound}=await paired();assert.equal((await bound.send({action:'ASCEND_READ_LOAD'})).error_code,'command_not_allowed');
  console.log('Ascend popup import, same-file/no-change, safe results, acknowledgement and restart fixtures passed.');
}
if(require.main===module)main().catch(error=>{
  const location=String(error.stack||'').split('\n').find(line=>/check-ascend-pairing-popup.js:\d+/.test(line));
  console.error('Offline popup fixture failed; '+(location?.match(/check-ascend-pairing-popup.js:\d+/)?.[0]||'location unavailable'));
  process.exitCode=1;
});
