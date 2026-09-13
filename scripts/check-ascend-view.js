const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const nodes = new Map();
const events = new Map();
function element() {
  return {children:[], textContent:'', append(node) {this.children.push(node);},
    replaceChildren() {this.children=[];}, addEventListener(name, fn) {events.set(name, fn);}};
}
const document = {querySelector(id) {if (!nodes.has(id)) nodes.set(id,element()); return nodes.get(id);},
  createElement:element, addEventListener(name, fn) {events.set(name, fn);}};
const data = {connection:{status:'READ_COMPLETE', executor_status:'STOPPED', last_verified_company:null,
  last_successful_read:null}, production_writes:'BLOCKED', pending_approvals:[], audit:[],
  loads:[{load_number:'1752', observed_at:'fixture-time', reconciliation:[{field:'customer',
    comparison_source:'canonical', status:'UNKNOWN', evidence_reference:null}], provider_facts:[{
      field:'customer', display_value:'<img src=x onerror=alert(1)>', raw_display:'Synthetic raw',
      availability:'PRESENT', source_section:'fixture'}]}]};
vm.runInNewContext(fs.readFileSync('app/dashboard/ascend.js','utf8'), {
  document, fetch:async () => ({ok:true, json:async () => data})});
events.get('freightdesk-live-ready')();
setImmediate(() => {
  function flatten(node) {return [node, ...node.children.flatMap(flatten)];}
  const rows = flatten(nodes.get('#ascend-content'));
  assert(rows.some(r => r.textContent.includes('<img src=x onerror=alert(1)>')));
  assert(rows.every(r => r.innerHTML === undefined));
  assert.equal(rows.filter(r => r.textContent.includes('FreightDesk-derived reconciliation')).length, 1);
  assert(rows.some(r => r.textContent.includes('Last verified account: Unverified')));
  assert(rows.some(r => r.textContent.includes('canonical evidence comparison')));
  console.log('Ascend local view: source separation, private placeholders, text-only rendering and overlapping refresh passed');
});
