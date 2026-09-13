'use strict';
// Offline VM and crypto fixtures only. No browser, host process, storage API or vendor networking.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto,createHmac}=require('node:crypto');
const root=require('node:path').join(__dirname,'../extensions/ascend-x1');
const id='a'.repeat(32),origin=`chrome-extension://${id}/`;
function worker(tabs,options={}){
  let listener;const ports=[],intervals=new Map(),timeouts=new Map();let tid=0;
  const runtime={id,getURL:file=>origin+file,lastError:null,onMessage:{addListener(fn){listener=fn;}},
    connectNative(name){
      assert.equal(name,'com.freightdesk.ascend_x1');
      let message,disconnect;
      const port={sent:[],closed:false,onMessage:{addListener(fn){message=fn;}},onDisconnect:{addListener(fn){disconnect=fn;}},
        postMessage(m){
          assert.ok(!this.closed);this.sent.push(m);
          if(m.kind==='PAIRING_DIAGNOSTIC')queueMicrotask(()=>message({kind:'DIAGNOSTIC_SAVED',protocol:1}));
        },disconnect(){this.closed=true;},
        emit(m){message(m);},crash(reason){runtime.lastError={message:reason};disconnect();runtime.lastError=null;}};
      ports.push(port);return port;
    }};
  const alarms=[],alarmDefinitions=[],storage=options.storage;
  const sandbox={URL,TextEncoder,Uint8Array,crypto:webcrypto,queueMicrotask,chrome:{runtime,tabs,
      ...(storage?{storage:{local:{async get(key){return {[key]:storage[key]};},async set(value){Object.assign(storage,value);}}},
        alarms:{create(name,options){alarmDefinitions.push({name,...options});},onAlarm:{addListener(fn){alarms.push(fn);}}}}:{})},
    setInterval(fn){intervals.set(++tid,fn);return tid;},clearInterval(t){intervals.delete(t);},
    setTimeout(fn){timeouts.set(++tid,fn);return tid;},clearTimeout(t){timeouts.delete(t);}};
  vm.createContext(sandbox);
  sandbox.importScripts=(...names)=>names.forEach(n=>vm.runInContext(fs.readFileSync(root+'/'+n,'utf8'),sandbox));
  sandbox.importScripts('background.js');
  const sender={id,url:origin+'popup.html'};
  return {sandbox,ports,intervals,timeouts,alarmDefinitions,alarm(){for(const fn of alarms)fn({name:'x1-runtime-wake'});},
    send:m=>new Promise(resolve=>listener(m,sender,resolve)),
    untrusted(m){let called=false;listener(m,{id,tab:{id:1},url:'https://ascendtms.com/loads'},()=>{called=true;});return called;},
    state(){let value;listener({action:'STATUS'},sender,r=>{value=r.state;});return value;}};
}
const bundle=()=>({extension_id:id,installation_id:'b'.repeat(32),generation:'c'.repeat(32),protocol:1,
  tenant_id:'booking-logistics',actor:'FreightDesk/Avery',key:'d'.repeat(64),expires_at:Math.floor(Date.now()/1000)+600});
const challenge=b=>({session_id:'e'.repeat(32),extension_origin:origin,tenant_id:b.tenant_id,actor:b.actor,
  protocol:1,installation_id:b.installation_id,generation:b.generation});
const pause=()=>new Promise(resolve=>setTimeout(resolve,2));
async function until(test){for(let i=0;i<300;i++){if(test())return;await pause();}throw Error('fixture_timeout');}
function signed(api,b,c,body,sequence=1){
  const value={session_id:c.session_id,sequence,body,direction:'host_to_extension'};
  return {...value,mac:createHmac('sha256',Buffer.from(b.key,'hex')).update(api.canonical(value)).digest('hex')};
}
async function paired(tabs){
  const w=worker(tabs),b=bundle(),c=challenge(b),api=w.sandbox.FreightDeskPairing;
  await w.send({action:'PAIR_LOCAL',bundle:b});const p=w.ports[0];
  p.emit({kind:'CHALLENGE',protocol:1,challenge:c});await until(()=>p.sent.length===2);
  const base={session_id:c.session_id,extension_origin:origin,tenant_id:b.tenant_id,actor:b.actor};
  assert.equal(p.sent[1].proof,createHmac('sha256',Buffer.from(b.key,'hex')).update(api.canonical(base)).digest('hex'));
  const body={state:'PAIRED',protocol:1,tenant_id:b.tenant_id,actor:b.actor,installation_id:b.installation_id,
    generation:b.generation,read_dispatch_enabled:false};
  p.emit({kind:'AUTHENTICATED',protocol:1,envelope:signed(api,b,c,body)});
  await until(()=>w.state()==='PAIRED');return {w,b,c,p,body};
}
async function main(){
  const w=worker();assert.equal(w.state(),'OFFLINE_PROTOTYPE');assert.equal(w.ports.length,0);
  assert.equal(w.untrusted({action:'CHECK_HOST'}),false);assert.equal(w.ports.length,0);
  for(const action of ['execute_js','eval','run_script','shell','ASCEND_SAVE_LOAD','ASCEND_OPEN_LOAD_READONLY']){
    assert.equal((await w.send({action})).error_code,'command_not_allowed');
  }
  assert.equal((await w.send({action:'CHECK_HOST',url:'PRIVATE'})).error_code,'command_not_allowed');
  await w.send({action:'CHECK_HOST'});w.ports[0].crash('Specified native messaging host not found.');
  assert.equal(w.state(),'HOST_NOT_REGISTERED');assert.equal(w.ports.length,1);
  await w.send({action:'CHECK_HOST'});w.ports[1].crash('Native host has exited. PRIVATE');
  assert.equal(w.state(),'HOST_UNAVAILABLE');assert.equal(w.ports.length,2);
  await w.send({action:'CHECK_HOST'});for(const fn of [...w.timeouts.values()])fn();
  assert.equal(w.state(),'HOST_UNAVAILABLE');
  await w.send({action:'CHECK_HOST'});w.ports[3].emit({kind:'ERROR',protocol:1,state:'PAIRING_REQUIRED'});
  await until(()=>w.ports[3].closed);assert.equal(w.state(),'PAIRING_REQUIRED');

  for(const mutation of [{extension_id:'b'.repeat(32)},{tenant_id:'other'},{actor:'other'},{protocol:2},
    {expires_at:1},{key:'private'},{url:'PRIVATE'},{generation:'wrong'}]){
    const x=worker();await x.send({action:'PAIR_LOCAL',bundle:{...bundle(),...mutation}});
    assert.equal(x.state(),'PAIRING_REQUIRED');assert.equal(x.ports.length,1);
    assert.ok(x.ports[0].sent.every(m=>m.kind==='PAIRING_DIAGNOSTIC'));
  }
  const {w:ready,b,c,p,body}=await paired();assert.equal(ready.intervals.size,1);
  assert.equal(ready.timeouts.size,0);assert.equal(p.sent[0].kind,'HELLO');
  // Heartbeat has authenticated status only. No read dispatch or automatic reconnect.
  [...ready.intervals.values()][0]();await until(()=>p.sent.length===4);
  assert.equal(p.sent[3].envelope.body.kind,'STATUS');
  for(const fn of [...ready.timeouts.values()])fn();assert.equal(ready.state(),'HOST_UNAVAILABLE');
  assert.equal(ready.ports.length,1);
  // A new worker/reload/browser restart retains no pairing key and does not connect.
  for(let i=0;i<3;i++){
    const restarted=worker();assert.equal(restarted.state(),'OFFLINE_PROTOTYPE');assert.equal(restarted.ports.length,0);
    await restarted.send({action:'CHECK_HOST'});restarted.ports[0].emit({kind:'CHALLENGE',protocol:1,challenge:c});
    await until(()=>restarted.ports[0].closed);assert.equal(restarted.state(),'PAIRING_REQUIRED');
    assert.equal(restarted.ports[0].sent.length,1);
  }
  for(const defect of ['duplicate','bad_mac','oversize','protocol','binding','malformed','ready_claim']){
    const pair=await paired(),api=pair.w.sandbox.FreightDeskPairing;
    let envelope=signed(api,pair.b,pair.c,pair.body,defect==='duplicate'?1:2);
    if(defect==='bad_mac')envelope.mac='0'.repeat(64);
    if(defect==='binding')envelope=signed(api,pair.b,pair.c,{...pair.body,actor:'other'},2);
    if(defect==='ready_claim')envelope=signed(api,pair.b,pair.c,{...pair.body,read_dispatch_enabled:true},2);
    const message={kind:'AUTHENTICATED',protocol:defect==='protocol'?2:1,envelope};
    if(defect==='oversize')message.extra='x'.repeat(65536);
    if(defect==='malformed')message.envelope=null;
    pair.p.emit(message);
    await until(()=>pair.w.state()==='PAIRING_REQUIRED');
  }
  // Explicit disconnect invalidates an in-flight asynchronous import.
  const race=worker(),pending=race.send({action:'PAIR_LOCAL',bundle:bundle()});
  await race.send({action:'DISCONNECT'});await pending;assert.equal(race.ports.length,0);
  const api=worker().sandbox.FreightDeskPairing;
  const imported=await api.importBundle(b,id);assert.equal(imported.key.extractable,false);
  await api.proof(imported,c);imported.expires=1;
  await assert.rejects(()=>api.sign(imported,{kind:'STATUS'}));
  await assert.rejects(()=>api.verify(imported,signed(api,b,c,body)));

  // Optional vectors generated by Python ensure actual cross-language canonical/HMAC agreement.
  if(process.argv.includes('--python-vectors')){
    const v=JSON.parse(fs.readFileSync(0,'utf8'));
    const pair=await api.importBundle(v.bundle,id);
    assert.equal(await api.proof(pair,v.challenge),v.proof);
    assert.equal(JSON.stringify(await api.verify(pair,v.host_envelope)),JSON.stringify(v.host_envelope.body));
    assert.equal((await api.sign(pair,v.client_body)).mac,v.client_mac);
  }
  console.log('Ascend native offline worker lifecycle, pairing, protocol and fail-closed checks passed.');
}
module.exports={worker,bundle,challenge,paired,signed,until,pause};
if(require.main===module)main().catch(()=>{console.error('Ascend native offline fixture check failed; fixture values omitted.');process.exitCode=1;});
