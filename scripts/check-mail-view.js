const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const nodes = new Map();
const events = new Map();
function element() {
  return {children: [], textContent: '', append(child) { this.children.push(child); },
    replaceChildren() { this.children = []; }, addEventListener(name, fn) { events.set(name, fn); }};
}
const document = {querySelector(id) { if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id); },
  createElement: element, addEventListener(name, fn) { events.set(name, fn); }};
const data = {connection:{status:'NOT_AUTHENTICATED'}, messages_discovered:1, messages_processed:1,
  unmatched_messages:1, classification_failures:0, attachment_count:0, drafts_created:0, errors:0,
  last_successful_sync:null, recent:[{subject:'<script>never execute</script>', confidence:.9,
    intent:'UNKNOWN', status:'REVIEW_REQUIRED', action:'NONE'}], documents:[]};
const fetch = async url => ({ok:true, json:async () => url.endsWith('/status') ? {status:'Awaiting Entra registration'} : data});
vm.runInNewContext(fs.readFileSync('app/dashboard/mail.js','utf8'), {document, fetch});
events.get('freightdesk-live-ready')(); // Overlap initial refresh, as actual owner-session startup does.
setImmediate(() => {
  const rows = nodes.get('#mail-content').children;
  assert.equal(rows.filter(row => row.textContent.includes('discovered')).length, 1);
  assert(rows.some(row => row.textContent.includes('<script>never execute</script>')));
  assert(rows.every(row => row.innerHTML === undefined));
  console.log('Mail UI overlapping-refresh and text-only rendering checks passed');
});
