'use strict';
// Worker orchestration with a fake router/native host; no browser or network calls.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
const root='extensions/ascend-x1/';
async function check(mode){
  const route={tab_id:7,document_id:'a'.repeat(32),eligible_tab_count:1,origin:'https://ascendtms.com',path:'/loads'};
  let api,hint,progress,queued=false,due=0,session='UNKNOWN',dispatch=null,active=true,captures=0,wakes=0;
  const sent=[],executed=[],events={addListener(){}};
  const tabs={onUpdated:events,onCreated:events,onRemoved:events,onActivated:events,async query(q){assert.equal(q.active,true);assert.equal(q.lastFocusedWindow,true);return active?[{id:7,url:'https://ascendtms.com/loads'}]:[{id:8,url:'https://example.invalid/'}];}};
  const sandbox={URL,crypto:webcrypto,setTimeout,clearTimeout,Date,TextEncoder,
    FreightDeskTabRouter:{create(...args){hint=args[5];progress=args[6];return {
      async list(){return [route]},async select(id){assert.equal(id,7);return route},async current(){return route},async ownerPresence(){return active},cancel(){},handshake(){return null},
      async execute(d){executed.push(d.command);if(d.command.operation==='ASCEND_MAP_WORKSPACE')progress({stage:'SESSION_VERIFIED',candidate_workspace_count:0,identity_signal_count:0,section_control_count:0,elapsed_ms:1});return {evidence:{authenticated_app:true},error_code:null}}
    }}}
  };
  vm.createContext(sandbox);
  for(const file of ['build.js','contract.js','read-errors.js','runtime.js'])vm.runInContext(fs.readFileSync(root+file,'utf8'),sandbox);
  const status=()=>({kind:'RUNTIME_STATUS',status:{state:'MAPPING_READY',mapping_mode:true,mapping_scope:mode,build:sandbox.FreightDeskBuild,
    read_access:'ENABLED',lease_expires_at:Date.now()/1000+600,session,error_code:null,next_due_at:due,control_revision:0}});
  const respond=value=>queueMicrotask(()=>api.accept(value));
  async function send(m){
    sent.push(m);
    if(m.kind==='RUNTIME_MAPPING_PROGRESS')return respond({kind:'RUNTIME_MAPPING_PROGRESS_ACK'});
    if(m.kind==='RUNTIME_MAPPING_CAPTURE'){queued=true;due=0;return respond(status());}
    if(m.kind==='RUNTIME_RESULT'){
      if(dispatch==='ASCEND_GET_SESSION_STATE')session='AUTHENTICATED';
      else {captures++;due=Date.now()/1000+60;queued=false;}
      return respond(status());
    }
    assert.equal(m.kind,'RUNTIME_WAKE');
    if(!m.route)return respond(status());
    if(m.mapping_hint&&mode==='NORMAL_OWNER_PRESENT')due=0;
    const op=m.probe_only?'ASCEND_GET_SESSION_STATE':queued||mode==='NORMAL_OWNER_PRESENT'&&due===0?'ASCEND_MAP_WORKSPACE':null;
    if(!op){due=Date.now()/1000+60;return respond(status());}
    dispatch=op;
    respond({kind:'RUNTIME_DISPATCH',route,deadline:Date.now()/1000+10,lease_generation:'a'.repeat(32),command:{
      version:1,request_id:webcrypto.randomUUID().replaceAll('-',''),operation:op,tenant_id:'booking-logistics',actor:'FreightDesk/Avery',load_id:null,expected_revision:null,
      ...(op==='ASCEND_MAP_WORKSPACE'?{approved_load_ids:mode==='FIRST_VALIDATION'?['1755','900001','900002']:null,owner_present:mode==='NORMAL_OWNER_PRESENT',lease_expires_at:Date.now()/1000+600}:{})
    }});
  }
  api=sandbox.FreightDeskRuntime.create(tabs,()=>true,send,()=>wakes++);
  await api.wake();
  assert.equal(captures,mode==='FIRST_VALIDATION'?0:1);
  if(mode==='NORMAL_OWNER_PRESENT'){
    hint();assert.ok(wakes>0);await api.wake();assert.equal(captures,2);
    assert.ok(sent.some(m=>m.mapping_hint===true));
    active=false;hint();await api.wake();assert.equal(captures,2); // Never follow a background Ascend tab.
    active=true;
  }
  await api.handle({action:'RUNTIME_MAPPING_CAPTURE'});
  assert.equal(captures,mode==='FIRST_VALIDATION'?1:3);
  await assert.rejects(()=>api.handle({action:'RUNTIME_MAPPING_CAPTURE',load_id:'1755'}),/COMMAND_NOT_ALLOWED/);
  assert.ok(sent.some(m=>m.kind==='RUNTIME_MAPPING_PROGRESS'));
  assert.ok(executed.every(c=>['ASCEND_GET_SESSION_STATE','ASCEND_MAP_WORKSPACE'].includes(c.operation)));
  assert.ok(executed.filter(c=>c.operation==='ASCEND_MAP_WORKSPACE').every(c=>c.owner_present===(mode==='NORMAL_OWNER_PRESENT')));
}
(async()=>{await check('FIRST_VALIDATION');await check('NORMAL_OWNER_PRESENT');process.stdout.write('Mapping worker scope and owner-navigation fixtures passed.\n');})().catch(e=>{console.error(e);process.exitCode=1});
