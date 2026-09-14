'use strict';
// Isolated browser API/crypto fixtures only. No Edge, installed native host or vendor request.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
const {worker,bundle,challenge,signed,until}=require('./check-ascend-native.js');
const root=require('node:path').join(__dirname,'../extensions/ascend-x1');
const build={extension_version:'0.6.3',controller_revision:3,native_protocol:1,content_protocol:3};
const id=()=>webcrypto.randomUUID().replaceAll('-','');
const event=()=>{const listeners=[];return {addListener:fn=>listeners.push(fn),emit:(...args)=>listeners.forEach(fn=>fn(...args))};};
function tabsFixture(items){
  const ports=[],reloads=[];
  const tabs={onRemoved:event(),onUpdated:event(),async query(){return items.filter(t=>t.url.startsWith('https://ascendtms.com/'));},
    async reload(number){reloads.push(number);const t=items.find(t=>t.id===number);if(t.blockRefresh)throw Error('PRIVATE_BROWSER_ERROR');t.version='0.6.3';t.missing=false;t.status='complete';},
    async get(number){const t=items.find(t=>t.id===number);if(!t)throw Error('missing');return t;},connect(number){
      const item=items.find(t=>t.id===number),port={onMessage:event(),onDisconnect:event(),disconnect(){port.closed=true;},
        postMessage(message){assert.equal(message.kind,'X1_RUNTIME_DISPATCH_V2');
          queueMicrotask(()=>port.onMessage.emit({kind:'X1_RESULT_V2',document_id:item.documentId,document_generation:1,error_code:null,evidence:
            message.command.operation==='ASCEND_GET_SESSION_STATE'?{authenticated_app:!!item.authenticated,login_form_present:!item.authenticated,nav_markers:[]}: {fixture:true}}));}};
      const path=new URL(item.url).pathname;
      ports.push(port);if(item.missing){queueMicrotask(()=>port.onDisconnect.emit());return port;}queueMicrotask(()=>port.onMessage.emit({kind:'X1_DOCUMENT_READY',...(item.traceOld?{}:{trace_revision:1}),...(item.mappingOld?{}:{mapping_reader_revision:item.mappingRevision??2}),build:{...build,controller_revision:item.protocol||build.controller_revision,extension_version:item.version||build.extension_version},document_generation:1,document_id:item.documentId||(item.documentId=id()),path:['/','/loads','/login.html'].includes(path)?path:'OTHER'}));return port;
    }};
  return {tabs,ports,reloads,items,close(number){items.splice(items.findIndex(t=>t.id===number),1);tabs.onRemoved.emit(number);}};
}
async function enrollmentChecks(){
  const store={},tabs=tabsFixture([]).tabs,w=worker(tabs,{storage:store});
  assert.equal(w.alarmDefinitions[0].name,'x1-runtime-wake');assert.equal(w.alarmDefinitions[0].periodInMinutes,1);
  await until(()=>w.state()==='NOT_ENROLLED');assert.equal(w.ports.length,0);
  const b={...bundle(),purpose:'X1_ENROLLMENT'},c=challenge(b);
  await w.send({action:'PAIR_LOCAL',bundle:b});const p=w.ports[0];assert.equal(p.sent[0].kind,'ENROLL_HELLO');
  p.emit({kind:'CHALLENGE',protocol:1,challenge:c});await until(()=>p.sent.length===2);assert.equal(p.sent[1].kind,'ENROLL_PAIR');
  const ack={protocol:1,state:'PAIRED',tenant_id:b.tenant_id,actor:b.actor,installation_id:b.installation_id,
    generation:b.generation,read_dispatch_enabled:false,enrollment:true,enrollment_handle:'f'.repeat(32),session_expires_at:Math.floor(Date.now()/1000)+600};
  p.emit({kind:'AUTHENTICATED',protocol:1,envelope:signed(w.sandbox.FreightDeskPairing,b,c,ack)});
  await until(()=>w.state()==='PAIRED');assert.deepEqual(store,{x1Enrollment:'f'.repeat(32)});
  const pending=()=>p.sent.find(m=>m.envelope?.body.kind==='RUNTIME_WAKE');await until(pending);
  const disabled={...ack,kind:'RUNTIME_STATUS',status:{state:'READ_ACCESS_DISABLED',read_access:'DISABLED',session:'UNKNOWN',control_revision:0}};
  p.emit({kind:'AUTHENTICATED',protocol:1,envelope:signed(w.sandbox.FreightDeskPairing,b,c,disabled,2)});
  await until(()=>w.timeouts.size===0);assert.equal(w.ports.length,1);
  const beforeAlarm=p.sent.length;w.alarm();await until(()=>p.sent.length>beforeAlarm);
  assert.equal(p.sent.at(-1).envelope.body.kind,'RUNTIME_WAKE');
  p.emit({kind:'AUTHENTICATED',protocol:1,envelope:signed(w.sandbox.FreightDeskPairing,b,c,disabled,3)});
  await until(()=>w.timeouts.size===0);
  // Popup/worker/Edge/Windows restart abstractions all discard keys and retain the opaque handle only.
  for(const restart of ['worker','edge','windows']){
    const fresh=worker(tabs,{storage:store});await until(()=>fresh.ports.length===1);const connection=fresh.ports[0];
    assert.equal(connection.sent[0].kind,'RESUME');assert.deepEqual(Object.keys(store),['x1Enrollment']);
    const rb={...b,key:'1'.repeat(64)},rc={...c,session_id:id(),enrollment_handle:store.x1Enrollment};delete rc.generation;
    connection.emit({kind:'RESUME_CHALLENGE',protocol:1,session_key:rb.key,challenge:rc});
    await until(()=>connection.sent.length===2);assert.equal(connection.sent[1].kind,'RESUME_PROOF',restart);
    connection.emit({kind:'AUTHENTICATED',protocol:1,envelope:signed(fresh.sandbox.FreightDeskPairing,rb,rc,ack)});
    await until(()=>fresh.state()==='PAIRED');connection.crash('fixture host restart');assert.equal(fresh.state(),'HOST_UNAVAILABLE');
    // Bounded reconnect performs RESUME, never ENROLL_HELLO or a bootstrap import.
    for(const fn of [...fresh.timeouts.values()])fn();await until(()=>fresh.ports.length>=2);
    assert.equal(fresh.ports.at(-1).sent[0].kind,'RESUME');
  }
  const stale=worker(tabs,{storage:store});await until(()=>stale.ports.length===1);
  stale.ports[0].emit({kind:'ERROR',protocol:1,error_code:'enrollment_stale'});await until(()=>stale.state()==='PAIRING_STALE');
  stale.alarm();assert.equal(stale.ports.length,1);assert.deepEqual(Object.keys(store),['x1Enrollment']);
  const s={crypto:webcrypto,Uint8Array,Date};vm.createContext(s);
  vm.runInContext(fs.readFileSync(root+'/enrollment.js','utf8'),s);
  await assert.rejects(()=>s.FreightDeskEnrollment.resume({kind:'RESUME_CHALLENGE',protocol:1,session_key:'a'.repeat(64),challenge:{}},store.x1Enrollment,'a'.repeat(32)),/PAIRING_BINDING_MISMATCH/);
}
async function routingChecks(){
  async function setup(items,enabled=true,hint=null,initialError=null){
    const fixture=tabsFixture(items),s={URL,crypto:webcrypto,setTimeout,clearTimeout,TextEncoder,chrome:{scripting:{async executeScript(options){
      assert.deepEqual(Array.from(options.target.frameIds),[0]);assert.equal(options.world,'ISOLATED');assert.equal('func' in options,false);
      assert.equal(options.files.join(','),'build.js,contract.js,read-errors.js,load-board-view.js,detail-scope.js,webbridge.js,mapping-scope.js,workspace.js,stops-metadata.js,reader.js,content.js');
      const item=fixture.items.find(t=>t.id===options.target.tabId);if(item.blockRefresh)throw Error('PRIVATE');
      fixture.reloads.push(item.id);item.version=build.extension_version;item.missing=false;item.traceOld=false;item.mappingOld=false;item.mappingRevision=2;
    }}}};vm.createContext(s);
    for(const file of ['build.js','contract.js','read-errors.js','tab-router.js','runtime.js'])vm.runInContext(fs.readFileSync(root+'/'+file,'utf8'),s);
    const messages=[];let stage=0,waiting=null,due=0,api,lastState=initialError?'CONTENT_SCRIPT_STALE':'READ_ONLY_READY';
    const status=(session='UNKNOWN')=>({kind:'RUNTIME_STATUS',binding_hint:hint,status:{state:lastState,error_code:initialError,read_access:enabled?'ENABLED':'DISABLED',session,next_due_at:due,control_revision:0}});
    async function send(m){messages.push(m);
      if(m.kind==='RUNTIME_WAKE'){
        if(!m.route){if(m.routing_state){lastState=m.routing_state;hint=null;}return queueMicrotask(()=>api.accept(status()));}
        lastState='READ_ONLY_READY';initialError=null;
        waiting=m;
        const operation=m.probe_only?'ASCEND_GET_SESSION_STATE':['ASCEND_GET_SESSION_STATE','ASCEND_NAVIGATE_ACTIVE_LOADS','ASCEND_GET_ACTIVE_LOADS'][stage++%3];
        queueMicrotask(()=>api.accept({kind:'RUNTIME_DISPATCH',route:m.route,deadline:Date.now()/1000+10,lease_generation:'x',command:{version:1,
          request_id:id(),operation,load_id:null,expected_revision:null,tenant_id:'booking-logistics',actor:'FreightDesk/Avery'}}));
      }else{
        assert.equal(m.kind,'RUNTIME_RESULT');const session=m.evidence?.authenticated_app?'AUTHENTICATED':'ASCEND_REAUTH_REQUIRED';
        if(!waiting.probe_only&&stage===3)due=Date.now()/1000+300;
        queueMicrotask(()=>api.accept(status(waiting.probe_only?session:'AUTHENTICATED')));
      }
    }
    api=s.FreightDeskRuntime.create(fixture.tabs,()=>true,send);return {api,fixture,messages,sandbox:s,enable(){enabled=true;},clearDue(){due=0;stage=0;}};
  }
  const lifecycle=await setup([{id:9,url:'https://ascendtms.com/loads',authenticated:true}]);
  const direct=lifecycle.sandbox.FreightDeskTabRouter.create(lifecycle.fixture.tabs,()=>true,()=>{},true,async()=>true);
  let bound=await direct.select(9);
  lifecycle.fixture.ports.at(-1).onDisconnect.emit();
  await assert.rejects(()=>direct.current(),/CONTENT_SCRIPT_PORT_STALE/);
  bound=await direct.select(9);
  lifecycle.fixture.tabs.onUpdated.emit(9,{status:'loading'});
  await assert.rejects(()=>direct.current(),/DOCUMENT_CHANGED/);
  lifecycle.fixture.items[0].documentId=id();bound=await direct.select(9);
  assert.equal(direct.handshake().document_id,bound.document_id);
  lifecycle.fixture.items[0].documentId=id();
  await assert.rejects(()=>direct.execute({route:bound,deadline:Date.now()/1000+10,command:{version:1,request_id:id(),operation:'ASCEND_GET_SESSION_STATE',load_id:null,expected_revision:null,tenant_id:'booking-logistics',actor:'FreightDesk/Avery'}}),/DOCUMENT_CHANGED/);
  const protocol=await setup([{id:1,url:'https://ascendtms.com/loads',authenticated:true,protocol:1}]);
  assert.equal((await protocol.api.wake()).state,'TAB_DISCOVERY_FAILED');
  assert.ok(protocol.messages.some(m=>m.routing_error==='PROTOCOL_VERSION_MISMATCH'));
  assert.equal(protocol.fixture.reloads.length,0);
  const none=await setup([]);assert.equal((await none.api.wake()).state,'WAITING_FOR_ASCEND');
  const disabled=await setup([{id:1,url:'https://ascendtms.com/loads',authenticated:true}],false);
  await disabled.api.wake();assert.equal(disabled.fixture.ports.length,0);assert.equal(disabled.messages.length,1);
  disabled.enable();await disabled.api.wake();assert.equal(disabled.api.status().bound_tab,'ACTIVE'); // Alarm wake after CLI enabled lease.
  for(const prior of [{version:'0.3.0'},{missing:true},{traceOld:true},{mappingOld:true},{mappingRevision:1}]){
    const old=await setup([{id:1,url:'https://ascendtms.com/loads',authenticated:true,...prior}]);
    assert.equal((await old.api.wake()).bound_tab,'ACTIVE');assert.deepEqual(old.fixture.reloads,[1]);
  }
  for(const item of [
    {url:'https://ascendtms.com/loads',blockRefresh:true},
    {url:'https://ascendtms.com/loads?PRIVATE',blockRefresh:true},
  ]){
    const blocked=await setup([{id:1,authenticated:true,version:'0.3.0',...item}]);
    assert.equal((await blocked.api.wake()).state,'CONTENT_SCRIPT_STALE');
    assert.ok(blocked.messages.some(m=>m.routing_state==='CONTENT_SCRIPT_STALE'&&m.eligible_tab_count===1));
    assert.ok(!JSON.stringify(blocked.messages).includes('PRIVATE'));
    assert.equal(blocked.fixture.reloads.length,0);
  }
  const staleDisabled=await setup([{id:1,url:'https://ascendtms.com/loads',authenticated:true,version:'0.3.0'}],false);
  await staleDisabled.api.wake();assert.equal(staleDisabled.fixture.reloads.length,0);
  const recoveredLatch=await setup([{id:1,url:'https://ascendtms.com/loads',authenticated:true}],true,null,'REFRESH_ASCEND_TAB');
  assert.equal((await recoveredLatch.api.wake()).bound_tab,'ACTIVE'); // A stored failure cannot suppress fresh handshake.
  const one=await setup([{id:1,url:'https://ascendtms.com/loads',authenticated:true}]);await one.api.wake();
  assert.equal(one.api.status().bound_tab,'ACTIVE');assert.equal(one.messages.filter(m=>m.kind==='RUNTIME_WAKE'&&m.probe_only).length,1);
  const before=one.messages.length;await one.api.wake();assert.equal(one.messages.length,before+1); // Host cadence owns idle no-op.
  one.fixture.close(1);one.fixture.items.push({id:2,url:'https://ascendtms.com/loads',authenticated:true});one.clearDue();
  await one.api.wake();assert.equal(one.api.status().bound_tab,'ACTIVE');assert.ok(one.messages.some(m=>m.route?.tab_id===2));
  const logged=await setup([{id:1,url:'https://ascendtms.com/login.html',authenticated:false}]);
  assert.equal((await logged.api.wake()).state,'ASCEND_REAUTH_REQUIRED');
  logged.fixture.items[0].url='https://ascendtms.com/loads';logged.fixture.items[0].authenticated=true;
  assert.equal((await logged.api.wake()).bound_tab,'ACTIVE');
  const many=await setup([{id:1,url:'https://ascendtms.com/loads',authenticated:true},{id:2,url:'https://ascendtms.com/loads',authenticated:true}]);
  assert.equal((await many.api.wake()).state,'TAB_SELECTION_REQUIRED');
  assert.equal(many.messages.filter(m=>m.kind==='RUNTIME_WAKE'&&!m.probe_only&&m.route).length,0);
  await many.api.handle({action:'RUNTIME_SELECT',tab_id:2});assert.equal((await many.api.wake()).bound_tab,'ACTIVE');
  await assert.rejects(()=>many.api.handle({action:'SAVE'}),/COMMAND_NOT_ALLOWED/);
  const candidates=await setup([{id:1,url:'https://ascendtms.com/login.html',authenticated:false},{id:2,url:'https://ascendtms.com/loads',authenticated:true}]);
  assert.equal((await candidates.api.wake()).bound_tab,'ACTIVE');
  const binding={tab_id:2,document_id:'a'.repeat(32)};
  const restarted=await setup([{id:1,url:'https://ascendtms.com/loads',authenticated:true},
    {id:2,url:'https://ascendtms.com/loads',authenticated:true,documentId:binding.document_id}],true,binding);
  assert.equal((await restarted.api.wake()).bound_tab,'ACTIVE');
  assert.equal(restarted.messages.filter(m=>m.probe_only).length,1);
  const stale=await setup([{id:1,url:'https://ascendtms.com/loads',authenticated:true},
    {id:2,url:'https://ascendtms.com/loads',authenticated:true,documentId:'b'.repeat(32)}],true,binding);
  assert.equal((await stale.api.wake()).state,'TAB_SELECTION_REQUIRED');
  assert.ok(stale.messages.some(m=>m.routing_state==='TAB_SELECTION_REQUIRED'));
  const other=await setup([{id:1,url:'https://ascendtms.com/private-route?PRIVATE',authenticated:true}]);
  assert.equal((await other.api.wake()).bound_tab,'ACTIVE');
  assert.ok(other.messages.some(m=>m.route?.path==='OTHER'));assert.ok(!JSON.stringify(other.messages).includes('PRIVATE'));
}
async function popupChecks(){
  const elements=Object.fromEntries(['runtime-state','runtime-action','runtime-health','runtime-rebind','runtime-list','runtime-select','runtime-tab']
    .map(key=>[key,{textContent:'',replaceChildren(...children){this.children=children;}}]));
  const s={Date,Number,Set,Object,setInterval(){},document:{getElementById:id=>elements[id],createElement:()=>({textContent:''})},
    chrome:{runtime:{async sendMessage(){return {state:'STOPPED',last_board_sync:1789148000,bound_tab:'UNBOUND',error_code:'BOARD_SCHEMA_INVALID',schema_predicate:'ROW_CELL_COUNT_MISMATCH'};}}}};
  vm.createContext(s);vm.runInContext(fs.readFileSync(root+'/runtime-popup.js','utf8'),s);
  await until(()=>elements['runtime-health'].children?.length);
  const output=elements['runtime-health'].children.map(e=>e.textContent);
  assert.ok(output.includes(new Date(1789148000000).toISOString()));assert.ok(output.includes('UNBOUND'));
  assert.ok(output.includes('BOARD_SCHEMA_INVALID'));assert.ok(output.includes('ROW_CELL_COUNT_MISMATCH'));
}
(async()=>{await enrollmentChecks();await routingChecks();await popupChecks();console.log('Persistent X1 enrollment restart, reconnect, lease-gated tab routing, reauth and bounded runtime fixtures passed.');})()
  .catch(error=>{console.error(error);process.exitCode=1;});
