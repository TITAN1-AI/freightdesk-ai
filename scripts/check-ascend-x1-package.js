'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const root=path.join(__dirname,'../extensions/ascend-x1');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
assert.equal(manifest.manifest_version,3);
assert.equal(manifest.version,'0.6.2');
assert.equal(manifest.background.service_worker,'background.js');
assert.equal(manifest.action.default_popup,'popup.html');
assert.deepEqual(manifest.permissions,['nativeMessaging','storage','alarms','scripting']);
assert.deepEqual(manifest.host_permissions,['https://ascendtms.com/*']);
assert.equal(manifest.content_scripts[0].world,'ISOLATED');
assert.equal(manifest.content_scripts[0].all_frames,false);
assert.deepEqual(manifest.content_scripts[0].matches,manifest.host_permissions);
assert.ok(!JSON.stringify(manifest).includes('webbridge-v2'));
for(const forbidden of ['externally_connectable','web_accessible_resources','optional_permissions'])
  assert.equal(manifest[forbidden],undefined);
const contentScripts=manifest.content_scripts[0].js;
for(const file of [manifest.background.service_worker,manifest.action.default_popup,'popup.css',...contentScripts,...Object.values(manifest.icons||{}),...Object.values(manifest.action.default_icon||{})])
  assert.ok(fs.existsSync(path.join(root,file)),file);
const html=fs.readFileSync(path.join(root,'popup.html'),'utf8');
assert.match(html,/<!doctype html>/i);
assert.match(html,/<head>/i);
const popupScripts=[...html.matchAll(/<script src="([^"]+)"/g)].map(m=>m[1]);
assert.deepEqual(popupScripts,['build.js','diagnostics.js','popup.js','read-popup.js','runtime-popup.js']);
for(const file of popupScripts)assert.ok(fs.existsSync(path.join(root,file)),file);
const background=fs.readFileSync(path.join(root,'background.js'),'utf8');
const imported=background.match(/^importScripts\(([^)]+)\)/m)[1].split(',').map(s=>s.trim().replace(/['"]/g,''));
assert.ok(imported.includes('build.js')&&imported.includes('runtime.js'));
for(const file of imported)assert.ok(fs.existsSync(path.join(root,file)),file);
assert.match(background,/PRODUCTION_CONNECTION_ENABLED=false/);
assert.match(background,/NATIVE_HOST='com\.freightdesk\.ascend_x1'/);
assert.match(fs.readFileSync(path.join(root,'content.js'),'utf8'),/PRODUCTION_CONNECTION_ENABLED=false/);
const router=fs.readFileSync(path.join(root,'tab-router.js'),'utf8');
const packaged=router.match(/packagedFiles=Object\.freeze\(\[([^\]]+)\]\)/)[1].split(',').map(s=>s.trim().replace(/['"]/g,''));
assert.deepEqual(packaged,contentScripts);
const build=fs.readFileSync(path.join(root,'build.js'),'utf8');
assert.match(build,new RegExp(`extension_version:'${manifest.version}'`));
assert.doesNotMatch(JSON.stringify(manifest),/webbridge-v2/);
for(const file of fs.readdirSync(root).filter(n=>n.endsWith('.js'))){
  const checked=spawnSync(process.execPath,['--check',path.join(root,file)],{encoding:'utf8'});
  assert.equal(checked.status,0,file+checked.stderr);
}
const chrome={runtime:{id:'a'.repeat(32),getURL:f=>'chrome-extension://'+'a'.repeat(32)+'/'+f,
  getManifest:()=>({version:manifest.version}),
  connectNative(){throw Error('must not connect during package check');},onConnect:{addListener(){}},
  onMessage:{addListener(){}},onStartup:{addListener(){}}},
  tabs:{onRemoved:{addListener(){}},onUpdated:{addListener(){}},onCreated:{addListener(){}},onActivated:{addListener(){}}},
  windows:{onFocusChanged:{addListener(){}}}};
const sandbox={URL,crypto:require('node:crypto').webcrypto,TextEncoder,Uint8Array,queueMicrotask,chrome,
  setTimeout(){return 0;},clearTimeout(){},setInterval(){return 0;},clearInterval(){}};
vm.createContext(sandbox);
sandbox.importScripts=(...names)=>names.forEach(name=>vm.runInContext(fs.readFileSync(path.join(root,name),'utf8'),sandbox));
sandbox.importScripts('background.js');
console.log('Ascend X1 unpacked package files, MV3 identity, V1-only manifest and worker syntax checks passed.');
