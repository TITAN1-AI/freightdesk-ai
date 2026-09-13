'use strict';
// Actual packaged background + enrollment/MAC/runtime, synthetic native pipe and disabled read state.
const assert=require('node:assert/strict'),fs=require('node:fs');
const {worker,bundle,challenge,signed,until,pause}=require('./check-ascend-native.js');
async function run(ackBody,missingBinding=false){
  const handle='f'.repeat(32),events={addListener(){}},tabs={onUpdated:events,onRemoved:events,onCreated:events,onActivated:events,
    async query(){throw Error('No tab or provider access is authorized by this fixture.');}};
  const w=worker(tabs,{storage:{x1Enrollment:handle}}),b=bundle(),c={...challenge(b),enrollment_handle:handle};
  delete c.generation;
  await until(()=>w.ports.length===1);
  const port=w.ports[0],api=w.sandbox.FreightDeskPairing;
  assert.equal(port.sent[0].kind,'RESUME');
  port.emit({kind:'RESUME_CHALLENGE',protocol:1,session_key:b.key,challenge:c});
  await until(()=>port.sent.length===2);
  assert.equal(port.sent[1].kind,'RESUME_PROOF');
  const base={protocol:1,tenant_id:'booking-logistics',actor:'FreightDesk/Avery',state:'PAIRED',read_dispatch_enabled:false};
  const respond=(body,sequence)=>port.emit({kind:'AUTHENTICATED',protocol:1,envelope:signed(api,b,c,body,sequence)});
  respond({...base,enrollment:true,enrollment_handle:handle,installation_id:b.installation_id,generation:b.generation,
    session_expires_at:Math.floor(Date.now()/1000)+600},1);
  await until(()=>w.state()==='PAIRED'&&port.sent.length===3);
  const disabled={...base,kind:'RUNTIME_STATUS',status:{state:'STOPPED',read_access:'REVOKED',session:'UNKNOWN',control_revision:1}};
  respond(disabled,2);
  await until(()=>w.timeouts.size===0);
  // A prior job's durable wake can arrive immediately after RESUME, while its lease is revoked.
  respond({...base,kind:'RUNTIME_JOB_WAKE_NOTIFICATION',notification_sequence:1,production_writes:false},3);
  await until(()=>port.sent.some(message=>message.envelope?.body.kind==='RUNTIME_CAUSAL_TRACE'));
  const trace=port.sent.find(message=>message.envelope?.body.kind==='RUNTIME_CAUSAL_TRACE');
  const receipt={...ackBody,request_id:trace.envelope.body.request_id};
  if(missingBinding)for(const key of ['protocol','tenant_id','actor','state'])delete receipt[key];
  respond(receipt,4);
  if(missingBinding){
    await until(()=>w.state()==='PAIRING_STALE');
    assert.equal((await w.send({action:'STATUS'})).error_code,'PAIRING_ACK_INVALID');
    return;
  }
  await until(()=>port.sent.filter(message=>message.envelope?.body.kind==='RUNTIME_WAKE').length===2);
  respond(disabled,5);
  await until(()=>w.timeouts.size===0);
  await pause();
  assert.equal(w.state(),'PAIRED');
  assert.equal(port.closed,false);
  assert.equal(receipt.accepted,false);
  assert.deepEqual(port.sent.map(message=>message.envelope?.body.kind||message.kind),
    ['RESUME','RESUME_PROOF','RUNTIME_WAKE','RUNTIME_CAUSAL_TRACE','RUNTIME_WAKE']);
  assert.equal((await w.send({action:'RUNTIME_STATUS'})).read_access,'REVOKED');
}
(async()=>{
  const ack=JSON.parse(fs.readFileSync(0,'utf8'));
  await run(ack,true);
  await run(ack,false);
  process.stdout.write('Bound trace ACK after resume and revoked-job wake preserves pairing; incomplete binding rejected.\n');
})().catch(error=>{process.stderr.write(String(error.stack)+'\n');process.exitCode=1;});
