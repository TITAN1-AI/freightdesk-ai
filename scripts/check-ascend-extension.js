'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=require('node:path').join(__dirname,'../extensions/ascend-x1');
const command={version:1,request_id:'a'.repeat(32),operation:'ASCEND_GET_SESSION_STATE',load_id:null,
  tenant_id:'booking-logistics',actor:'FreightDesk/Avery',expected_revision:null};
const contentFiles=['build.js','contract.js','read-errors.js','load-board-view.js','detail-scope.js','webbridge.js','mapping-scope.js','workspace.js','reader.js','content.js'];
for(const file of ['background.js','content.js']){
  let listener,connects=0;
  const sandbox={URL,crypto:require('node:crypto').webcrypto,location:{origin:'https://ascendtms.com',pathname:'/loads'},
    addEventListener(){},removeEventListener(){},document:{addEventListener(){},removeEventListener(){}},
    chrome:{runtime:{id:'a'.repeat(32),
    getURL:file=>'chrome-extension://'+'a'.repeat(32)+'/'+file,
    getManifest:()=>({version:'0.6.2'}),
    connectNative(){connects++;throw Error('must not connect');},onConnect:{addListener(){}},
    onMessage:{addListener(fn){listener=fn;}}}}};
  vm.createContext(sandbox);
  sandbox.importScripts=(...names)=>names.forEach(name=>vm.runInContext(fs.readFileSync(root+'/'+name,'utf8'),sandbox));
  if(file==='content.js')contentFiles.slice(0,-1).forEach(name=>sandbox.importScripts(name));
  else sandbox.importScripts('contract.js');
  sandbox.importScripts(file);
  let response;
  const sender=file==='background.js'?{id:'a'.repeat(32),tab:{id:1},frameId:0,url:'https://ascendtms.com/loads?private=token'}:{id:'a'.repeat(32)};
  listener(command,sender,r=>{response=r;});
  if(file==='background.js')assert.equal(response,undefined);
  else assert.equal(response.error_code,'production_bridge_disabled');
  assert.equal(connects,0);
  response=null;listener(command,{...sender,id:'b'.repeat(32)},r=>{response=r;});assert.equal(response,null);
  for(const operation of ['ASCEND_SAVE_LOAD','ASCEND_ADD_NOTE','ASCEND_UPLOAD_DOCUMENT','eval']){
    assert.throws(()=>sandbox.FreightDeskX1Contract.validate({...command,operation}));
  }
  assert.throws(()=>sandbox.FreightDeskX1Contract.validate({...command,javascript:'untrusted code'}));
}
console.log('Ascend X1 bootstrap isolation and disabled automatic native connection checks passed.');
