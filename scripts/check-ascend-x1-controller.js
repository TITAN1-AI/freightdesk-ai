'use strict';
// Browser API/DOM transport mocks only. No actual Edge, Native Messaging process or vendor access.
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),{webcrypto}=require('node:crypto');
const {paired,signed,until}=require('./check-ascend-native.js');
const dir=require('node:path').join(__dirname,'../extensions/ascend-x1');
const doc='f'.repeat(32),origin='https://ascendtms.com';
function tabsFixture(initial=[{id:1,url:origin+'/loads?PRIVATE',status:'complete'}]){
  let update,remove;const ports=[],items=initial;
  const tabs={onUpdated:{addListener(fn){update=fn;}},onRemoved:{addListener(fn){remove=fn;}},
    async query(query){assert.equal(JSON.stringify(query),JSON.stringify({url:origin+'/*'}));return items;},
    async get(id){const t=items.find(t=>t.id===id);if(!t)throw Error('PRIVATE');return t;},
    connect(id,options){
      assert.equal(options.frameId,0);assert.equal(options.name,'freightdesk-x1-identity');
      let message,disconnect;
      const p={sent:[],closed:false,onMessage:{addListener(fn){message=fn;}},onDisconnect:{addListener(fn){disconnect=fn;}},
        disconnect(){p.closed=true;},postMessage(m){p.sent.push(m);},emit(m){message(m);},crash(){disconnect();}};
      ports.push(p);queueMicrotask(()=>p.emit({kind:'DOCUMENT_READY',document_id:doc,path:new URL(items.find(t=>t.id===id).url).pathname}));return p;
    }};
  return {tabs,ports,items,close(id=1){items.splice(items.findIndex(t=>t.id===id),1);remove(id);},
    navigate(id=1){update(id,{status:'loading'});}};
}
function routerApi(){
  const s={URL,crypto:webcrypto,setTimeout,clearTimeout,TextEncoder};vm.createContext(s);
  for(const file of ['contract.js','read-errors.js','tab-router.js'])vm.runInContext(fs.readFileSync(dir+'/'+file,'utf8'),s);
  return s;
}
const command=()=>({version:1,request_id:webcrypto.randomUUID().replaceAll('-',''),operation:'ASCEND_GET_SESSION_STATE',
  load_id:null,tenant_id:'booking-logistics',actor:'FreightDesk/Avery',expected_revision:null});
async function contentChecks(){
  let connect,reads=0,wait,failure=null;
  const s={URL,crypto:webcrypto,setTimeout,clearTimeout,location:{origin,pathname:'/loads'},document:{},addEventListener(){},removeEventListener(){},
    chrome:{runtime:{id:'a'.repeat(32),getManifest:()=>({version:'0.6.4'}),onConnect:{addListener(fn){connect=fn;},removeListener(fn){if(connect===fn)connect=null;}},onMessage:{addListener(){}}}},
    FreightDeskX1Reader:{async create(){return {viewDiagnostic:()=>({view:'ACTIVE_LOADS'}),detailDiagnostic:()=>({failed_category:'new_containers',measured:9,maximum:8}),boardDiagnostic:()=>({failed_predicate:'ROW_CELL_COUNT_MISMATCH'}),async executeRuntime(c,lease){reads++;if(wait)await wait;lease();if(failure)throw Error(failure);return {authenticated_app:true};}};}}};
  vm.createContext(s);for(const file of ['build.js','contract.js','read-errors.js','content.js'])vm.runInContext(fs.readFileSync(dir+'/'+file,'utf8'),s);
  function port(sender={id:'a'.repeat(32)}){
    let receive,disconnect;
    const p={name:'freightdesk-x1-identity',sender,sent:[],closed:false,
      onMessage:{addListener(fn){receive=fn;}},onDisconnect:{addListener(fn){disconnect=fn;}},
      postMessage(m){if(p.closed)throw Error('FIXTURE_PORT_DISCONNECTED');p.sent.push(m);},
      disconnect(){p.closed=true;},lost(){p.closed=true;disconnect();},call:m=>receive(m)};
    connect(p);return p;
  }
  assert.ok(port({id:'a'.repeat(32),tab:{id:1}}).closed);assert.equal(reads,0);
  // READY must attest the installed workspace module, never a hardcoded content-script claim.
  const absent=port();assert.equal(absent.sent[0].mapping_reader_revision,undefined);absent.lost();
  s.FreightDeskWorkspace={readerRevision:0};const stale=port();assert.equal(stale.sent[0].mapping_reader_revision,0);stale.lost();
  s.FreightDeskWorkspace={readerRevision:2};
  const p=port();assert.equal(p.sent[0].kind,'X1_DOCUMENT_READY');assert.equal(reads,0);
  assert.equal(p.sent[0].mapping_reader_revision,2);
  const request={kind:'X1_RUNTIME_DISPATCH_V2',document_generation:p.sent[0].document_generation,document_id:p.sent[0].document_id,deadline:Date.now()/1000+10,command:command()};
  await p.call({...request,kind:'RUNTIME_DISPATCH'});assert.equal(reads,0);
  await p.call(request);assert.equal(reads,1);assert.equal(p.sent.at(-1).error_code,null);
  await p.call(request);assert.equal(reads,1);assert.equal(p.sent.at(-1).error_code,'DUPLICATE_REQUEST');
  await p.call({...request,command:{...command(),script:'PRIVATE_SCRIPT'}});assert.equal(reads,1);
  await p.call({...request,command:{...command(),operation:'ASCEND_OPEN_LOAD_READONLY',load_id:'1755',expected_revision:'a'.repeat(64),url:origin}});
  assert.equal(reads,1);
  let resume;wait=new Promise(resolve=>{resume=resolve;});const pending=p.call({...request,command:command()});
  await until(()=>reads===2);const count=p.sent.length;p.lost();resume();await pending;
  assert.equal(p.sent.length,count); // Lost pairing port cannot emit a late successful DOM result.
  wait=null;failure='BOARD_SCHEMA_INVALID';const p2=port(),ready=p2.sent[0];
  await p2.call({...request,document_id:ready.document_id,document_generation:ready.document_generation,command:command()});
  assert.equal(p2.sent.at(-1).error_code,'BOARD_SCHEMA_INVALID');
  assert.equal(p2.sent.at(-1).evidence.schema_diagnostic.failed_predicate,'ROW_CELL_COUNT_MISMATCH');
  failure='DETAIL_BOUND_NEW_CONTAINERS';
  await p2.call({...request,document_id:ready.document_id,document_generation:ready.document_generation,
    command:{...command(),operation:'ASCEND_OPEN_LOAD_READONLY',load_id:'1755',expected_revision:'a'.repeat(64)}});
  assert.equal(p2.sent.at(-1).evidence.detail_container_diagnostic.failed_category,'new_containers');
  assert.equal(p2.sent.at(-1).error_code,'DETAIL_BOUND_NEW_CONTAINERS');
  failure='PRIVATE_PROVIDER_ERROR';
  await p2.call({...request,document_id:ready.document_id,document_generation:ready.document_generation,command:command()});
  assert.equal(p2.sent.at(-1).evidence.schema_diagnostic,undefined);
  assert.ok(!JSON.stringify(p2.sent).includes('PRIVATE_PROVIDER_ERROR'));
}
async function readPopupChecks(){
  const elements={},messages=[];
  for(const id of ['read-tabs','read-tab','read-select','read-plan','read-state','read-next','read-receipt'])
    elements[id]={value:'',disabled:true,textContent:'',options:[],replaceChildren(...values){this.options=values;},add(value){this.options.push(value);}};
  let index=0;
  const s={document:{getElementById:id=>elements[id]},Option:function(text,value){this.text=text;this.value=value;},
    chrome:{runtime:{async sendMessage(m){
      messages.push(m);
      if(m.action==='READ_STATUS')return {state:'PAIRED',index:0};
      if(m.action==='LIST_ASCEND_TABS')return {tabs:[{tab_id:7,path:'/loads'}]};
      if(m.action==='SELECT_ASCEND_TAB')return {selected_tab:{tab_id:7}};
      if(m.action==='LOAD_READ_PLAN')return {state:'READ_ONLY_READY',plan:{load_id:'1755'}};
      if(m.action==='READ_NEXT'){index++;return {state:index===4?'IDENTITY_VERIFIED_READS_BLOCKED':'READ_ONLY_READY',index,receipt:{step:index}};}
      throw Error('UNEXPECTED_UI_COMMAND');
    }}}};
  vm.createContext(s);vm.runInContext(fs.readFileSync(dir+'/read-popup.js','utf8'),s);
  await until(()=>elements['read-state'].textContent==='PAIRED');
  assert.equal(messages.length,1);assert.ok(elements['read-next'].disabled);
  await elements['read-tabs'].onclick();assert.equal(elements['read-tab'].value,'');
  elements['read-select'].onclick();assert.equal(elements['read-state'].textContent,'TAB_SELECTION_REQUIRED');
  assert.equal(messages.filter(m=>m.action==='SELECT_ASCEND_TAB').length,0);
  elements['read-tab'].value='7';elements['read-select'].onclick();
  await until(()=>messages.some(m=>m.action==='SELECT_ASCEND_TAB'));await new Promise(resolve=>setImmediate(resolve));
  elements['read-plan'].onclick();await until(()=>elements['read-state'].textContent==='READ_ONLY_READY');
  assert.equal(messages.filter(m=>m.action==='READ_NEXT').length,0);
  for(let i=1;i<=4;i++){
    await elements['read-next'].onclick();
    assert.equal(messages.filter(m=>m.action==='READ_NEXT').length,i);
    assert.equal(JSON.parse(elements['read-receipt'].textContent).step,i);
  }
  assert.ok(elements['read-next'].disabled);assert.equal(elements['read-state'].textContent,'IDENTITY_VERIFIED_READS_BLOCKED');
}
async function main(){
  await contentChecks();
  await readPopupChecks();
  const s=routerApi();
  const empty=tabsFixture([]),no=s.FreightDeskTabRouter.create(empty.tabs,()=>true);
  assert.equal((await no.list()).length,0);await assert.rejects(()=>no.select(1),/NO_ELIGIBLE_TAB/);
  const many=tabsFixture([{id:1,url:origin+'/'},{id:2,url:origin+'/login.html'},{id:3,url:'https://other.invalid/PRIVATE'},
    {id:4,url:'https://ascendtms.com.attacker.invalid/loads'}]);
  const router=s.FreightDeskTabRouter.create(many.tabs,()=>true);
  assert.equal((await router.list()).length,2);
  await assert.rejects(()=>router.current(),/TAB_SELECTION_REQUIRED/);
  assert.equal((await router.select(2)).path,'/login.html');assert.equal(many.ports.length,1);
  await assert.rejects(()=>router.select(3),/TAB_SELECTION_REQUIRED/);
  for(const failure of ['closed','navigation','pairing','stale','query']){
    let paired=true;const f=tabsFixture(),r=s.FreightDeskTabRouter.create(f.tabs,()=>paired);
    const route=await r.select(1);assert.equal(route.eligible_tab_count,1);
    assert.ok(!JSON.stringify(route).includes('PRIVATE'));
    const dispatch={command:command(),route,deadline:Date.now()/1000+5};
    const work=r.execute(dispatch);const rejected=assert.rejects(work,/TAB_STATE_CHANGED|PAIRING_LOST/);
    await until(()=>f.ports[0].sent.length===1);
    if(failure==='closed')f.close();
    if(failure==='navigation')f.navigate();
    if(failure==='pairing'){paired=false;r.cancel('PAIRING_LOST');}
    if(failure==='stale')f.ports[0].crash();
    if(failure==='query'){f.items[0].url=origin+'/loads?CHANGED';f.navigate();}
    await rejected;assert.ok(f.ports[0].closed);
  }
  const f=tabsFixture(),r=s.FreightDeskTabRouter.create(f.tabs,()=>true),route=await r.select(1);
  for(const operation of ['ASCEND_SAVE_LOAD','ASCEND_READ_LOAD','eval','run_script','shell']){
    await assert.rejects(()=>r.execute({command:{...command(),operation},route,deadline:Date.now()/1000+5}));
  }
  const valid=r.execute({command:command(),route,deadline:Date.now()/1000+5});
  await until(()=>f.ports[0].sent.length===1);
  f.ports[0].emit({kind:'IDENTITY_RESULT',evidence:{authenticated_app:true},error_code:null});
  assert.equal((await valid).evidence.authenticated_app,true);r.cancel();
  // End-to-end worker orchestration: signed plan -> exact selected tab -> signed dispatch -> signed result -> signed receipt.
  const fixtures=tabsFixture(),pair=await paired(fixtures.tabs),{w,p,b,c}=pair;
  assert.equal((await w.send({action:'READ_STATUS'})).state,'PAIRED');
  let sequence=1;const api=w.sandbox.FreightDeskPairing;
  function emit(body){p.emit({kind:'AUTHENTICATED',protocol:1,envelope:signed(api,b,c,{state:'PAIRED',read_dispatch_enabled:false,
    protocol:1,tenant_id:'booking-logistics',actor:'FreightDesk/Avery',...body},++sequence)});}
  assert.equal((await w.send({action:'LIST_ASCEND_TABS'})).tabs.length,1);
  await w.send({action:'SELECT_ASCEND_TAB',tab_id:1});
  const load=w.send({action:'LOAD_READ_PLAN'});
  await until(()=>p.sent.some(m=>m.envelope?.body.kind==='READ_PLAN'));
  const plan={attempt_id:'owner-x1-identity-1755-offline-fixture',load_id:'1755'};emit({kind:'READ_PLAN',plan});
  assert.equal((await load).state,'READ_ONLY_READY');
  let revision=null;
  for(let i=0;i<4;i++){
    const task=w.send({action:'READ_NEXT'});
    await until(()=>p.sent.filter(m=>m.envelope?.body.kind==='READ_REQUEST').length===i+1);
    const request=p.sent.filter(m=>m.envelope?.body.kind==='READ_REQUEST').at(-1).envelope.body;
    assert.equal(request.command.expected_revision,i>=2?revision:null);
    const dispatch={kind:'READ_DISPATCH',command:request.command,route:request.route,deadline:Date.now()/1000+10,attempt_id:plan.attempt_id};
    emit(dispatch);await until(()=>fixtures.ports[0].sent.length===i+1);
    // No extra arbitrary selector/URL payload is accepted in the content dispatch.
    assert.deepEqual(Object.keys(fixtures.ports[0].sent.at(-1)).sort(),['command','deadline','document_id','kind']);
    fixtures.ports[0].emit({kind:'IDENTITY_RESULT',evidence:{fixture:true},error_code:null});
    await until(()=>p.sent.filter(m=>m.envelope?.body.kind==='READ_RESULT').length===i+1);
    const receipt={request_id:request.command.request_id,operation:request.command.operation,
      state:i===3?'IDENTITY_VERIFIED_READS_BLOCKED':'READ_ONLY_READY'};
    if(i===1){revision='b'.repeat(64);receipt.board_hash=revision;}
    emit({kind:'READ_RECEIPT',receipt});
    assert.equal((await task).state,i===3?'IDENTITY_VERIFIED_READS_BLOCKED':'READ_ONLY_READY');
  }
  assert.equal((await w.send({action:'READ_NEXT'})).error_code,'READ_SEQUENCE_INVALID');
  assert.equal(p.sent.filter(m=>m.envelope?.body.kind==='READ_REQUEST').length,4);
  assert.ok(fixtures.ports[0].closed);
  await w.send({action:'DISCONNECT'});
  assert.equal((await w.send({action:'READ_NEXT'})).error_code,'PAIRING_LOST');
  console.log('X1 offline tab routing, explicit selection, closed/stale/navigation, pairing loss and signed four-step orchestration passed.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
