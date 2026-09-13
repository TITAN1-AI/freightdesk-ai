'use strict';
// Real worker orchestration, synthetic tab/host: no browser or networking.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
async function run(foreground=true){
 const route={tab_id:1,document_id:'a'.repeat(32),eligible_tab_count:1,origin:'https://ascendtms.com',path:'/loads'};
 let worker,connected=false,revision=1,queued=false,session='UNKNOWN',proofs=0,captures=0,dispatch,progress;
 const sent=[],events={addListener(){}};
 const context={URL,Date,crypto:webcrypto,setTimeout,clearTimeout,TextEncoder,
  FreightDeskTabRouter:{create(...args){progress=args[6];return {
   cancel(){connected=false;},async ownerPresence(){return foreground;},handshake(){return null;},async current(){if(!connected)throw Error('TAB_STATE_CHANGED');return route;},
   async select(){connected=true;return route;},async execute(d){assert(connected);dispatch=d.command.operation;
    if(dispatch==='ASCEND_MAP_WORKSPACE'){progress({capture_ack:true});captures++;}
    return {evidence:{fixture:true},error_code:null};}}}}};
 vm.createContext(context);for(const f of ['build.js','contract.js','read-errors.js','runtime.js'])vm.runInContext(fs.readFileSync('extensions/ascend-x1/'+f,'utf8'),context);
 const state=()=>({kind:'RUNTIME_STATUS',status:{build:context.FreightDeskBuild,control_revision:revision,state:'MAPPING_READY',read_access:'ENABLED',session,paused:false,error_code:null,
   lease_expires_at:Date.now()/1000+60,mapping_orchestrated:true,mapping_scope:'NORMAL_OWNER_PRESENT',mapping_operation_mode:'OBSERVE',mapping_capture_requested:queued,next_due_at:queued?0:Date.now()/1000+60}});
 const respond=x=>queueMicrotask(()=>worker.accept(x));
 async function send(body){sent.push(body);
  if(body.kind==='RUNTIME_CAUSAL_TRACE')return respond({kind:'RUNTIME_CAUSAL_TRACE_ACK'});
  if(body.kind==='RUNTIME_CAPTURE_ACK')return respond({kind:'RUNTIME_MAPPING_PROGRESS_ACK'});
  if(body.kind==='RUNTIME_RESULT'){
   if(dispatch==='ASCEND_GET_SESSION_STATE'){
    proofs++;session='AUTHENTICATED';
    if(proofs===1){revision++;queued=true;session='UNKNOWN';} // Real probe -> mapping lease replacement.
   }else queued=false;
   return respond(state());
  }
  assert.equal(body.kind,'RUNTIME_WAKE');
  if(!body.route)return respond(state());
  const op=session!=='AUTHENTICATED'||body.probe_only?'ASCEND_GET_SESSION_STATE':queued?'ASCEND_MAP_WORKSPACE':null;
  if(!op)return respond(state());
  respond({kind:'RUNTIME_DISPATCH',route,deadline:Date.now()/1000+12,command:{version:1,request_id:webcrypto.randomUUID().replaceAll('-',''),operation:op,
   tenant_id:'booking-logistics',actor:'FreightDesk/Avery',load_id:null,expected_revision:null,
   ...(op==='ASCEND_MAP_WORKSPACE'?{approved_load_ids:['1763'],capture_load_id:'1763',capture_section:'Load Basics',owner_present:true,lease_expires_at:Date.now()/1000+60}:{})}});
 }
 worker=context.FreightDeskRuntime.create({onUpdated:events,onCreated:events,onRemoved:events,onActivated:events,async query(){return foreground?[{id:1,url:'https://ascendtms.com/loads'}]:[];}},()=>true,send);
 await worker.wake();
 if(foreground){assert.equal(captures,1);assert.equal(proofs,2);assert(sent.some(m=>m.kind==='RUNTIME_CAPTURE_ACK'));assert(!sent.some(m=>m.mapping_hint));}
 else{assert.equal(captures,0);assert(sent.some(m=>m.routing_state==='WAITING_FOR_OWNER_WORKSPACE'&&!m.routing_error));}
}
(async()=>{await run();await run(false);process.stdout.write('Immediate current-load handoff and foreground fixtures passed.\n');})().catch(e=>{console.error(e);process.exitCode=1;});
