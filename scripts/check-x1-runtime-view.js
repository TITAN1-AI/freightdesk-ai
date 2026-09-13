'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),requests=[],actions=['enable','disable','pause','resume','rebind','repair'];
function element(){return {children:[],textContent:'',disabled:false,dataset:{},events:{},
  append(...items){this.children.push(...items);},replaceChildren(){this.children=[];},
  addEventListener(name,fn){this.events[name]=fn;}};}
const buttons=actions.map(action=>Object.assign(element(),{dataset:{x1Action:action}}));
const document={hidden:false,events:{},querySelector(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},
  createElement:element,addEventListener(name,fn){this.events[name]=fn;}};
document.querySelector('#x1-runtime').querySelectorAll=()=>buttons;
let status={state:'READ_ONLY_READY',extension:'CONNECTED',native_host:'CONNECTED',pairing:'VALID',
  session:'AUTHENTICATED',read_access:'DISABLED',bound_tab:'ACTIVE',view:'ACTIVE_LOADS',
  load_count:11,board_hash:'<img src=x onerror=alert(1)>',owner_action:'Enable read-only access.'};
const turn=()=>new Promise(resolve=>setImmediate(resolve));
vm.runInNewContext(fs.readFileSync('app/dashboard/ascend-runtime.js','utf8'),{document,
  setTimeout(){return 1;},clearTimeout(){},fetch:async(url,options)=>{
    requests.push({url,options});return {ok:true,json:async()=>status};}});
(async()=>{
  await turn();
  assert.equal(requests.length,1);assert.equal(requests[0].options,undefined);
  const facts=nodes.get('#x1-facts').children;
  assert(facts.some(n=>n.textContent==='<img src=x onerror=alert(1)>'));
  assert(facts.every(n=>n.innerHTML===undefined));
  assert(!buttons[0].disabled);
  buttons[0].events.click();await turn();
  const request=requests.at(-1);assert.equal(request.url,'/api/ascend/runtime/control');
  assert.equal(request.options.headers['x-freightdesk-local'],'1');
  assert.deepEqual(JSON.parse(request.options.body),{action:'enable',hours:8});
  status={...status,read_access:'ENABLED'};
  document.events['freightdesk-live-ready']();await turn();assert(buttons[0].disabled);
  buttons.at(-1).events.click();await turn();
  assert.equal(JSON.parse(requests.at(-1).options.body).action,'repair');
  assert(nodes.get('#x1-action').textContent.includes('closed'));
  assert(requests.every(r=>r.url.startsWith('/api/ascend/runtime/')));
  console.log('X1 runtime dashboard: inert refresh, owner-only explicit controls, text rendering and closed repair passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
