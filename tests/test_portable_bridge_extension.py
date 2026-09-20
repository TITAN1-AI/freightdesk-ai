"""Manifest and packaged-identity smoke for the portable bridge. Load unpacked is owner-manual."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extensions" / "portable-bridge"
FORBIDDEN = ("nativeMessaging", "connectNative", "eval(", "new Function", "document.cookie",
             "WebSocket(", ".click(", ".submit(", "ASCEND_SAVE", "ASCEND_SET_DRIVER")
CONTENT_FILES = ["build.js", "board-view.js", "harvest.js", "write-note.js", "content.js"]
READ_ONLY_JS = ("background.js", "board-view.js", "harvest.js", "popup.js", "build.js")


def test_portable_manifest_has_no_native_host_and_keeps_write_block():
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["name"] == "FreightDesk Bridge"
    assert manifest["version"] == "0.1.8"
    assert "nativeMessaging" not in manifest["permissions"]
    assert manifest["permissions"] == ["storage", "alarms", "scripting"]
    assert manifest["host_permissions"][0] == "https://ascendtms.com/*"
    assert "http://127.0.0.1/*" in manifest["host_permissions"]
    assert manifest["content_scripts"][0]["matches"] == ["https://ascendtms.com/*"]
    assert manifest["content_scripts"][0]["js"] == CONTENT_FILES
    assert manifest["content_scripts"][0]["world"] == "ISOLATED"
    assert manifest["content_scripts"][0]["all_frames"] is False
    assert "externally_connectable" not in manifest
    assert "web_accessible_resources" not in manifest
    identity = (EXT / "build.js").read_text(encoding="utf-8")
    assert "extension_version: '0.1.8'" in identity
    assert "native_messaging: false" in identity
    assert "live_validated: false" in identity
    assert "production_writes: false" in identity
    sources = "\n".join((EXT / name).read_text(encoding="utf-8") for name in READ_ONLY_JS)
    for token in FORBIDDEN:
        assert token not in sources
    write_note = (EXT / "write-note.js").read_text(encoding="utf-8")
    for token in ("nativeMessaging", "connectNative", "eval(", "new Function", "document.cookie",
                  "WebSocket(", ".click(", ".submit("):
        assert token not in write_note
    assert "ADD_INTERNAL_NOTE" in write_note
    assert "WRITE_ACTION_FORBIDDEN" in write_note
    assert "FORBIDDEN_ACTIONS" in write_note
    content = (EXT / "content.js").read_text(encoding="utf-8")
    assert "ADD_INTERNAL_NOTE" in content
    assert "PROBE_NOTE_WORKSPACE" in content
    assert "HARVEST_BOARD" in content
    assert "chrome.runtime.connectNative" not in "\n".join(path.read_text(encoding="utf-8") for path in EXT.glob("*.js"))
    assert "FreightDeskAscendHost" not in sources


def test_portable_javascript_syntax():
    files = sorted(EXT.glob("*.js"))
    assert files
    for path in files:
        completed = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        assert completed.returncode == 0, path.name + "\n" + completed.stderr


def test_portable_reinjects_content_and_keeps_manual_reload_copy():
    background = (EXT / "background.js").read_text(encoding="utf-8")
    content = (EXT / "content.js").read_text(encoding="utf-8")
    popup_js = (EXT / "popup.js").read_text(encoding="utf-8")
    popup_html = (EXT / "popup.html").read_text(encoding="utf-8")
    readme = (EXT / "README.md").read_text(encoding="utf-8")
    assert "CONTENT_FILES = Object.freeze(['build.js', 'board-view.js', 'harvest.js', 'write-note.js', 'content.js'])" in background
    assert "chrome.scripting.executeScript" in background
    inject = background.split("async function injectIsolatedContent", 1)[1].split("async function ensureAscendContent", 1)[0]
    assert "world: 'ISOLATED'" in inject
    assert "frameIds: [0]" in inject
    assert "files: [...CONTENT_FILES]" in inject
    assert "func:" not in inject
    assert "code:" not in inject
    assert "Reload the Ascend Active Loads tab now (F5), then press Start harvest." in background
    assert "Reload the Ascend tab after loading this unpacked extension." not in background
    assert "ensureOpenAscendTabs({ allowReload })" in background
    assert "details.reason === 'install' || details.reason === 'update'" in background
    assert "ensureOpenAscendTabs({ allowReload: false })" in background
    assert "parsed.pathname !== '/' && parsed.pathname !== '/loads'" in background
    assert "FreightDeskPortableContentBound" in content
    assert "message.action === 'PING'" in content
    assert "attachFailed" in popup_js
    assert "reload the Ascend tab first" in popup_js
    assert "reload that Active Loads tab (F5)" in popup_html
    assert "last-write" in popup_html
    assert "writeBanner" in popup_js
    assert "NOTE_COMMIT_REQUIRES_OWNER_PATH" in popup_js
    assert "BRIDGE_CLAIM_TIMEOUT" in popup_js
    assert "typed_but_not_saved" in popup_js
    assert "reopenAfterSave" in (EXT / "write-note.js").read_text(encoding="utf-8")
    assert "forbid_searchbox" in background
    assert "tab_hint" in background
    assert "probeTabScratchDom" in background
    assert "allFrames: true" in background
    assert "scratch_tab_required" in (EXT / "write-note.js").read_text(encoding="utf-8")
    assert "formatLastWrite" in popup_js
    assert "safeCode" in popup_js
    assert "POLL_WRITES" in popup_js
    assert "POLL_WRITES" in background
    assert "WRITE_SOON" in background
    assert "claimPendingWithRetry" in background
    assert "armWritePolls" in background
    assert "body: payload" in background
    assert "live_validated: false" in _extract_function(background, "completeWrite")
    assert "Reload the Ascend **Active Loads** tab now" in readme
    assert "chrome.scripting.executeScript" in readme


def _extract_function(source: str, name: str) -> str:
    token = "function " + name + "("
    start = source.index(token)
    if start >= 6 and source[start - 6:start] == "async ":
        start -= 6
    header_end = source.index(")", start)
    body_start = source.index("{", header_end)
    depth = 0
    for index, char in enumerate(source[body_start:], start=body_start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("unclosed " + name)


def test_portable_safe_reload_only_exact_active_loads():
    background = (EXT / "background.js").read_text(encoding="utf-8")
    script = "\n".join([
        "const ASCEND_ORIGIN = 'https://ascendtms.com';",
        _extract_function(background, "ascendTabUrl"),
        _extract_function(background, "isSafeReloadTarget"),
        "const cases = [",
        "  [{url:'https://ascendtms.com/loads', status:'complete'}, true],",
        "  [{url:'https://ascendtms.com/', status:'complete'}, true],",
        "  [{url:'https://ascendtms.com/loads', discarded:true}, true],",
        "  [{url:'https://ascendtms.com/loads?x=1', status:'complete'}, false],",
        "  [{url:'https://ascendtms.com/loads#panel', status:'complete'}, false],",
        "  [{url:'https://ascendtms.com/loads/1763', status:'complete'}, false],",
        "  [{url:'https://example.com/loads', status:'complete'}, false],",
        "  [{url:'https://ascendtms.com/loads', status:'loading'}, false],",
        "  [{url:'https://ascendtms.com/other', status:'complete'}, false],",
        "  [{url:'http://ascendtms.com/loads', status:'complete'}, false]",
        "];",
        "for (const [tab, expected] of cases) {",
        "  if (isSafeReloadTarget(tab) !== expected) {",
        "    throw new Error(JSON.stringify({tab, expected, safe: isSafeReloadTarget(tab)}));",
        "  }",
        "}",
        "if (!ascendTabUrl('https://ascendtms.com/other')) throw new Error('inject helper too strict');",
        "if (ascendTabUrl('https://evil.example/')) throw new Error('origin helper leaked');",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_portable_harvest_start_injects_without_reloading():
    background = (EXT / "background.js").read_text(encoding="utf-8")
    script = "\n".join([
        "const ASCEND_ORIGIN = 'https://ascendtms.com';",
        "const CONTENT_FILES = Object.freeze(['build.js', 'board-view.js', 'harvest.js', 'write-note.js', 'content.js']);",
        "let injected = false;",
        "const calls = [];",
        "const chrome = {",
        "  scripting: { executeScript: async (opts) => { calls.push(['inject', opts]); injected = true; } },",
        "  tabs: {",
        "    sendMessage: async (id, msg) => {",
        "      calls.push(['msg', msg.action]);",
        "      if (msg.action === 'PING' && injected) return { ok: true };",
        "      throw new Error('no listener');",
        "    },",
        "    reload: async (id) => { calls.push(['reload', id]); }",
        "  }",
        "};",
        _extract_function(background, "ascendTabUrl"),
        _extract_function(background, "isSafeReloadTarget"),
        _extract_function(background, "pingTab"),
        _extract_function(background, "injectIsolatedContent"),
        _extract_function(background, "ensureAscendContent"),
        "const tab = {id: 7, url: 'https://ascendtms.com/loads', status: 'complete'};",
        "(async () => {",
        "  const result = await ensureAscendContent(tab, { allowReload: false });",
        "  if (result !== 'injected') throw new Error('expected injected, got ' + result);",
        "  if (calls.some((item) => item[0] === 'reload')) throw new Error('harvest must not reload');",
        "  const inject = calls.find((item) => item[0] === 'inject')[1];",
        "  if (inject.world !== 'ISOLATED' || inject.target.frameIds[0] !== 0) throw new Error('bad target');",
        "  if (inject.files.join(',') !== 'build.js,board-view.js,harvest.js,write-note.js,content.js') throw new Error('bad files');",
        "  injected = true;",
        "  const ready = await ensureAscendContent(tab, { allowReload: true });",
        "  if (ready !== 'ready') throw new Error('expected ready, got ' + ready);",
        "  if (calls.filter((item) => item[0] === 'inject').length !== 1) throw new Error('duplicate inject');",
        "  injected = false;",
        "  chrome.scripting.executeScript = async () => { throw new Error('blocked'); };",
        "  const reloaded = await ensureAscendContent(tab, { allowReload: true });",
        "  if (reloaded !== 'reloaded') throw new Error('expected reloaded, got ' + reloaded);",
        "  const blocked = await ensureAscendContent({id: 8, url: 'https://ascendtms.com/loads/1763', status: 'complete'}, { allowReload: true });",
        "  if (blocked !== 'reload_required') throw new Error('detail path must not reload');",
        "})().catch((error) => { console.error(error); process.exit(1); });",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_portable_write_note_blocks_non_note_actions():
    script = "\n".join([
        "const fs = require('fs');",
        "eval(fs.readFileSync(" + json.dumps(str(EXT / "write-note.js")) + ", 'utf8'));",
        "const W = globalThis.FreightDeskPortableWriteNote;",
        "if (!W || W.action !== 'ADD_INTERNAL_NOTE') throw new Error('write module missing');",
        "const scan = {",
        "  textareas: [{label:'Private Notes', visible:true, value:''}],",
        "  buttons: [{label:'Add Note', visible:true}]",
        "};",
        "const ok = W.inspect(scan, {action:'ADD_INTERNAL_NOTE', note_kind:'PRIVATE_INTERNAL'});",
        "if (!ok.ok) throw new Error('expected private note plan, got ' + ok.code);",
        "for (const action of ['ASCEND_SAVE_LOAD','ASCEND_SET_DRIVER','ASCEND_UPDATE_STATUS','ASCEND_NEW_LOAD','ADD_PUBLIC_NOTE']) {",
        "  const result = W.inspect(scan, {action});",
        "  if (result.ok || result.code !== 'WRITE_ACTION_FORBIDDEN') throw new Error(action + ' leaked: ' + JSON.stringify(result));",
        "}",
        "const kind = W.inspect(scan, {action:'ADD_INTERNAL_NOTE', note_kind:'PUBLIC'});",
        "if (kind.ok || kind.code !== 'NOTE_KIND_FORBIDDEN') throw new Error('public kind leaked');",
        "const publicOnly = W.inspect({",
        "  textareas: [{label:'Notes', visible:true, value:''}],",
        "  buttons: [{label:'Add Note', visible:true}]",
        "}, {action:'ADD_INTERNAL_NOTE'});",
        "if (publicOnly.ok || publicOnly.code !== 'PUBLIC_NOTE_BLOCKED') throw new Error('public notes leaked');",
        "const saveLoad = W.inspect({",
        "  textareas: [{label:'Private Notes', visible:true, value:''}],",
        "  buttons: [{label:'Save Load', visible:true}]",
        "}, {action:'ADD_INTERNAL_NOTE'});",
        "if (saveLoad.ok || saveLoad.code !== 'NOTE_COMMIT_REQUIRES_OWNER_PATH') throw new Error('save load accepted');",
        "if (saveLoad.commit_kind !== 'WHOLE_FORM_SAVE') throw new Error('save load kind');",
        "if (!W.isForbiddenCommitLabel('Assign carrier') || W.isNoteCommitLabel('Save Load')) throw new Error('label helpers');",
        "if (!W.isOwnerPathCommit('Save & Exit to Load Board') || W.isNoteCommitLabel('Save & Exit to Load Board')) throw new Error('owner path helper');",
        "if (!W.isPrivateNoteLabel('Private Load Note')) throw new Error('private load note label');",
        "if (!W.isPrivateNoteControl({id:'scratch', label:''}) || W.isPrivateNoteControl({id:'notes', label:'Notes'})) throw new Error('atlas ids');",
        "const publicId = W.inspect({",
        "  textareas: [{id:'notes', label:'Public Load Note', visible:true, value:''}],",
        "  buttons: [{label:'Save', visible:true}]",
        "}, {action:'ADD_INTERNAL_NOTE', allow_whole_form_save:true});",
        "if (publicId.ok || publicId.code !== 'PUBLIC_NOTE_BLOCKED') throw new Error('public #notes leaked: ' + JSON.stringify(publicId));",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_portable_write_note_opener_and_owner_path():
    script = "\n".join([
        "const fs = require('fs');",
        "eval(fs.readFileSync(" + json.dumps(str(EXT / "write-note.js")) + ", 'utf8'));",
        "const W = globalThis.FreightDeskPortableWriteNote;",
        "const already = W.planWorkspace({",
        "  textareas: [{label:'Private Load Note', visible:true, value:''}],",
        "  headings: [{text:'load basics', visible:true}],",
        "  inputs: [], rows: [], labeled: [], href: 'https://ascendtms.com/loads', title: ''",
        "}, '1763');",
        "if (!already.ready || already.strategy !== 'already_open') throw new Error('already-open workspace missed: ' + JSON.stringify(already));",
        "const identified = W.planWorkspace({",
        "  textareas: [{label:'Private Load Note', visible:true, value:''}],",
        "  headings: [{text:'load 1763', visible:true}],",
        "  inputs: [{label:'Load Number', value:'1763', visible:true}],",
        "  rows: [], labeled: [], href: 'https://ascendtms.com/loads', title: ''",
        "}, '1763');",
        "if (!identified.ready) throw new Error('identity workspace missed');",
        "const scratchOpen = W.planWorkspace({",
        "  textareas: [{id:'scratch', label:'', visible:false, value:''}],",
        "  headings: [], inputs: [], rows: [], labeled: [], href: 'https://ascendtms.com/loads', title: ''",
        "}, '1763');",
        "if (!scratchOpen.ready || scratchOpen.strategy !== 'already_open') throw new Error('#scratch must already-open without board/identity: ' + JSON.stringify(scratchOpen));",
        "const conflict = W.planWorkspace({",
        "  textareas: [{label:'Private Load Note', visible:true, value:''}],",
        "  headings: [], inputs: [{label:'Load Number', value:'1755', visible:true}],",
        "  rows: [], labeled: [], href: 'https://ascendtms.com/loads', title: ''",
        "}, '1763');",
        "if (conflict.ready || conflict.code !== 'LOAD_IDENTITY_UNVERIFIED') throw new Error('conflict leaked: ' + JSON.stringify(conflict));",
        "const scratchWins = W.planWorkspace({",
        "  textareas: [{id:'scratch', label:'Private Load Note', visible:true, value:''}],",
        "  headings: [], inputs: [{label:'Load Number', value:'1755', visible:true}],",
        "  rows: [], labeled: [], href: 'https://ascendtms.com/loads', title: ''",
        "}, '1763');",
        "if (!scratchWins.ready || scratchWins.strategy !== 'already_open') throw new Error('#scratch should skip identity/opener: ' + JSON.stringify(scratchWins));",
        "const noBoard = W.planOpener({ rows: [], searchboxes: [], buttons: [], links: [] }, '1763');",
        "if (noBoard.error !== 'LOAD_OPENER_UNVERIFIED') throw new Error('expected opener unverified, got ' + JSON.stringify(noBoard));",
        "const row = W.planOpener({",
        "  rows: [{cells:[{text:'1763', label:'1763', visible:true, tag:'td'},{text:'View', label:'View', visible:true, tag:'a'}]}],",
        "  searchboxes: [], buttons: [], links: []",
        "}, '1763');",
        "if (row.strategy !== 'unique_row_opener') throw new Error('row opener missed: ' + JSON.stringify(row));",
        "const search = W.planOpener({",
        "  rows: [], buttons: [], links: [],",
        "  searchboxes: [{label:'search', visible:true, value:''}]",
        "}, '1763');",
        "if (search.strategy !== 'unique_searchbox') throw new Error('searchbox opener missed: ' + JSON.stringify(search));",
        "const linkSave = W.inspect({",
        "  textareas: [{id:'scratch', label:'Private Load Note', visible:true, value:''}],",
        "  buttons: [],",
        "  links: [{label:'Save & Exit to Load Board', visible:true}]",
        "}, {action:'ADD_INTERNAL_NOTE'});",
        "if (linkSave.ok || linkSave.code !== 'NOTE_COMMIT_REQUIRES_OWNER_PATH') throw new Error('link save missed: ' + JSON.stringify(linkSave));",
        "const linkStay = W.inspect({",
        "  textareas: [{id:'scratch', label:'Private Load Note', visible:true, value:''}],",
        "  buttons: [],",
        "  links: [{label:'Save', visible:true, value:'Save'}]",
        "}, {action:'ADD_INTERNAL_NOTE', allow_whole_form_save:true});",
        "if (!linkStay.ok || linkStay.commit_kind !== 'WHOLE_FORM_SAVE' || linkStay.save_variant !== 'SAVE_STAY') throw new Error('link Save stay missed: ' + JSON.stringify(linkStay));",
        "const owner = W.inspect({",
        "  textareas: [{label:'Private Load Note', visible:true, value:''}],",
        "  buttons: [{label:'Save & Exit to Load Board', visible:true}]",
        "}, {action:'ADD_INTERNAL_NOTE'});",
        "if (owner.ok || owner.code !== 'NOTE_COMMIT_REQUIRES_OWNER_PATH') throw new Error('save and exit accepted: ' + JSON.stringify(owner));",
        "if (owner.commit_kind !== 'WHOLE_FORM_SAVE') throw new Error('owner commit kind');",
        "const missing = W.inspect({",
        "  textareas: [{label:'Private Load Note', visible:true, value:''}],",
        "  buttons: []",
        "}, {action:'ADD_INTERNAL_NOTE'});",
        "if (missing.ok || missing.code !== 'NOTE_SAVE_CONTROL_UNVERIFIED') throw new Error('missing save code: ' + JSON.stringify(missing));",
        "const source = fs.readFileSync(" + json.dumps(str(EXT / "write-note.js")) + ", 'utf8');",
        "if (source.includes('.click(') || source.includes('.submit(')) throw new Error('write-note used native click/submit');",
        "if (!source.includes('NOTE_COMMIT_REQUIRES_OWNER_PATH')) throw new Error('owner path code missing');",
        "if (!source.includes('fillNoSubmit')) throw new Error('search fill helper missing');",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_portable_write_note_execute_skips_save_and_exit():
    script = "\n".join([
        "const fs = require('fs');",
        "globalThis.getComputedStyle = () => ({ visibility: 'visible' });",
        "globalThis.MouseEvent = class { constructor(type, init) { this.type = type; Object.assign(this, init || {}); } };",
        "globalThis.Event = class { constructor(type, init) { this.type = type; Object.assign(this, init || {}); } };",
        "function el(tag, attrs) {",
        "  attrs = attrs || {};",
        "  const node = {",
        "    tagName: String(tag).toUpperCase(),",
        "    textContent: attrs.text || attrs.label || '',",
        "    value: attrs.value || '',",
        "    placeholder: attrs.placeholder || '',",
        "    labels: attrs.label ? [{ textContent: attrs.label }] : [],",
        "    events: [],",
        "    children: attrs.children || [],",
        "    getClientRects: () => (attrs.hidden ? [] : [{}]),",
        "    getAttribute: (name) => (attrs.attrs || {})[name] || null,",
        "    closest: () => null,",
        "    matches: () => false,",
        "    focus() { node.focused = true; },",
        "    dispatchEvent(ev) { node.events.push(ev.type); return true; },",
        "    querySelectorAll(sel) {",
        "      return (node.children || []).filter((child) => {",
        "        if (sel.includes('td') && child.tagName === 'TD') return true;",
        "        if (sel.includes('a') && child.tagName === 'A') return true;",
        "        if (sel.includes('button') && child.tagName === 'BUTTON') return true;",
        "        return false;",
        "      });",
        "    },",
        "    querySelector() { return null; }",
        "  };",
        "  return node;",
        "}",
        "const note = el('textarea', { label: 'Private Load Note', value: '' });",
        "const saveExit = el('button', { label: 'Save & Exit to Load Board', text: 'Save & Exit to Load Board' });",
        "const heading = el('h2', { text: 'Load Basics' });",
        "const doc = {",
        "  title: 'AscendTMS',",
        "  defaultView: { location: { origin: 'https://ascendtms.com', href: 'https://ascendtms.com/loads' } },",
        "  getElementById: () => null,",
        "  querySelectorAll(sel) {",
        "    if (sel.includes('textarea')) return [note];",
        "    if (sel.includes('button,input[type=\"submit\"]')) return [saveExit];",
        "    if (sel.includes('h1,h2')) return [heading];",
        "    if (sel.includes('input[type=\"search\"]')) return [];",
        "    if (sel.includes('tbody')) return [];",
        "    if (sel.includes('input,select')) return [];",
        "    if (sel === 'label') return [];",
        "    if (sel.includes('[data-note-kind')) return [];",
        "    if (sel.includes('a,[role=\"link\"]')) return [];",
        "    return [];",
        "  }",
        "};",
        "eval(fs.readFileSync(" + json.dumps(str(EXT / "write-note.js")) + ", 'utf8'));",
        "const W = globalThis.FreightDeskPortableWriteNote;",
        "(async () => {",
        "  const result = await W.execute(doc, { action: 'ADD_INTERNAL_NOTE', load_id: '1763', text: 'secret-note', note_kind: 'PRIVATE_INTERNAL', origin: 'https://ascendtms.com' });",
        "  if (result.ok || result.error_code !== 'NOTE_COMMIT_REQUIRES_OWNER_PATH') throw new Error('execute should fail owner path: ' + JSON.stringify(result));",
        "  if (result.opener_strategy !== 'already_open') throw new Error('should skip board opener: ' + JSON.stringify(result));",
        "  if (result.commit_kind !== 'WHOLE_FORM_SAVE') throw new Error('commit kind: ' + JSON.stringify(result));",
        "  if (note.value === 'secret-note') throw new Error('must not type when only Save & Exit exists');",
        "  if (saveExit.events.includes('click')) throw new Error('must not activate Save & Exit');",
        "})().catch((error) => { console.error(error); process.exit(1); });",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_portable_write_tab_prefers_url_with_load_id():
    background = (EXT / "background.js").read_text(encoding="utf-8")
    script = "\n".join([
        "const chrome = { tabs: { sendMessage: async (id) => ({ scratch: id === 9, already_open: id === 9 }) } };",
        _extract_function(background, "probeTabScratchDom"),
        _extract_function(background, "probeTabScratch"),
        _extract_function(background, "tabHintFor"),
        _extract_function(background, "pickWriteTab"),
        "const tabs = [",
        "  {id:1, url:'https://ascendtms.com/loads', active:true},",
        "  {id:2, url:'https://ascendtms.com/loads/1763', active:false}",
        "];",
        "(async () => {",
        "  const picked = await pickWriteTab(tabs, '1763');",
        "  if (!picked.tab || picked.tab.id !== 2) throw new Error('expected url match, got ' + JSON.stringify(picked));",
        "  if (picked.scratch_present) throw new Error('url-only pick should not claim scratch');",
        "  const fallback = await pickWriteTab([{id:3, url:'https://ascendtms.com/', active:true}], '1763');",
        "  if (!fallback.tab || fallback.tab.id !== 3) throw new Error('expected active fallback');",
        "  const scratchTab = await pickWriteTab([",
        "    {id:8, url:'https://ascendtms.com/loads', active:true},",
        "    {id:9, url:'https://ascendtms.com/loads', active:false}",
        "  ], '1763');",
        "  if (!scratchTab.tab || scratchTab.tab.id !== 9) throw new Error('expected scratch probe, got ' + JSON.stringify(scratchTab));",
        "  if (!scratchTab.scratch_present) throw new Error('scratch_present missing');",
        "  if (!String(scratchTab.tab_hint || '').includes('scratch:9')) throw new Error('tab_hint: ' + scratchTab.tab_hint);",
        "  if (!String(scratchTab.tab_hint || '').includes('skip=board:8')) throw new Error('tab_hint skip: ' + scratchTab.tab_hint);",
        "  chrome.tabs.sendMessage = async () => { throw new Error('unbound'); };",
        "  chrome.scripting = { executeScript: async ({ target }) => [{ result: { scratch: target.tabId === 9 } }] };",
        "  const viaDom = await pickWriteTab([",
        "    {id:8, url:'https://ascendtms.com/loads', active:true},",
        "    {id:9, url:'https://ascendtms.com/loads', active:false}",
        "  ], '1763');",
        "  if (!viaDom.tab || viaDom.tab.id !== 9 || !viaDom.scratch_present) throw new Error('dom probe must pick scratch: ' + JSON.stringify(viaDom));",
        "})().catch((error) => { console.error(error); process.exit(1); });",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_portable_write_uses_scratch_tab_not_board_searchbox():
    background = (EXT / "background.js").read_text(encoding="utf-8")
    script = "\n".join([
        "const fs = require('fs');",
        "globalThis.getComputedStyle = () => ({ visibility: 'visible' });",
        "globalThis.MouseEvent = class { constructor(type, init) { this.type = type; Object.assign(this, init || {}); } };",
        "globalThis.Event = class { constructor(type, init) { this.type = type; Object.assign(this, init || {}); } };",
        "function el(tag, attrs) {",
        "  attrs = attrs || {};",
        "  const node = {",
        "    id: attrs.id || '',",
        "    tagName: String(tag).toUpperCase(),",
        "    textContent: attrs.text || attrs.label || '',",
        "    value: attrs.value || '',",
        "    placeholder: attrs.placeholder || '',",
        "    labels: attrs.label ? [{ textContent: attrs.label }] : [],",
        "    events: [],",
        "    getClientRects: () => (attrs.hidden ? [] : [{}]),",
        "    getAttribute: (name) => name === 'id' ? (attrs.id || '') : ((attrs.attrs || {})[name] || null),",
        "    closest: () => null,",
        "    matches: () => false,",
        "    focus() { node.focused = true; },",
        "    dispatchEvent(ev) { node.events.push(ev.type); return true; },",
        "    querySelectorAll() { return []; },",
        "    querySelector() { return null; }",
        "  };",
        "  return node;",
        "}",
        "const chrome = { tabs: { sendMessage: async (id) => ({ scratch: id === 9, already_open: id === 9 }) } };",
        _extract_function(background, "probeTabScratchDom"),
        _extract_function(background, "probeTabScratch"),
        _extract_function(background, "tabHintFor"),
        _extract_function(background, "pickWriteTab"),
        "const scratch = el('textarea', { id: 'scratch', label: 'Private Load Note', value: 'prior note' });",
        "const save = el('button', { label: 'Save', text: 'Save' });",
        "const search = el('input', { label: 'search', value: '' });",
        "search.tagName = 'INPUT';",
        "const basics = {",
        "  title: 'AscendTMS',",
        "  defaultView: { location: { origin: 'https://ascendtms.com', href: 'https://ascendtms.com/loads/1763' } },",
        "  getElementById: (id) => id === 'scratch' ? scratch : null,",
        "  querySelectorAll(sel) {",
        "    if (sel.includes('iframe')) return [];",
        "    if (sel.includes('textarea')) return [scratch];",
        "    if (sel.includes('button,input[type=\"submit\"]')) return [save];",
        "    if (sel.includes('h1,h2')) return [];",
        "    if (sel.includes('input[type=\"search\"]')) return [];",
        "    if (sel.includes('tbody')) return [];",
        "    if (sel.includes('input,select')) return [];",
        "    if (sel === 'label') return [];",
        "    if (sel.includes('[data-note-kind')) return [];",
        "    if (sel.includes('a,[role=\"link\"]')) return [];",
        "    return [];",
        "  }",
        "};",
        "const board = {",
        "  title: 'AscendTMS',",
        "  defaultView: { location: { origin: 'https://ascendtms.com', href: 'https://ascendtms.com/loads' } },",
        "  getElementById: () => null,",
        "  querySelectorAll(sel) {",
        "    if (sel.includes('iframe')) return [];",
        "    if (sel.includes('textarea')) return [];",
        "    if (sel.includes('button,input[type=\"submit\"]')) return [];",
        "    if (sel.includes('h1,h2')) return [];",
        "    if (sel.includes('input[type=\"search\"]')) return [search];",
        "    if (sel.includes('tbody')) return [];",
        "    if (sel.includes('input,select')) return [search];",
        "    if (sel === 'label') return [];",
        "    if (sel.includes('[data-note-kind')) return [];",
        "    if (sel.includes('a,[role=\"link\"]')) return [];",
        "    return [];",
        "  }",
        "};",
        "eval(fs.readFileSync(" + json.dumps(str(EXT / "write-note.js")) + ", 'utf8'));",
        "const W = globalThis.FreightDeskPortableWriteNote;",
        "(async () => {",
        "  const choice = await pickWriteTab([",
        "    {id:8, url:'https://ascendtms.com/loads', active:true},",
        "    {id:9, url:'https://ascendtms.com/loads/1763', active:false}",
        "  ], '1763');",
        "  if (!choice.tab || choice.tab.id !== 9 || !choice.scratch_present) throw new Error('must pick scratch tab: ' + JSON.stringify(choice));",
        "  if (!String(choice.tab_hint).includes('scratch:9') || !String(choice.tab_hint).includes('board:8')) throw new Error('hint: ' + choice.tab_hint);",
        "  const blocked = await W.execute(board, { action: 'ADD_INTERNAL_NOTE', load_id: '1763', text: 'B-new', note_kind: 'PRIVATE_INTERNAL', origin: 'https://ascendtms.com', allow_whole_form_save: true, forbid_searchbox: true, tab_hint: choice.tab_hint });",
        "  if (blocked.opener_strategy !== 'scratch_tab_required') throw new Error('must not unique_searchbox when scratch tab exists: ' + JSON.stringify(blocked));",
        "  if (search.events.includes('input') || search.value === '1763') throw new Error('filled board searchbox');",
        "  const allowed = await W.execute(basics, { action: 'ADD_INTERNAL_NOTE', load_id: '1763', text: 'B-new', note_kind: 'PRIVATE_INTERNAL', origin: 'https://ascendtms.com', allow_whole_form_save: true, forbid_searchbox: true, tab_hint: choice.tab_hint });",
        "  if (!allowed.ok || !allowed.note_present || allowed.opener_strategy !== 'already_open') throw new Error('scratch tab write: ' + JSON.stringify(allowed));",
        "  if (allowed.tab_hint !== choice.tab_hint) throw new Error('tab_hint not on result');",
        "  if (scratch.value !== 'B-new' || !save.events.includes('click')) throw new Error('did not type/save on scratch tab');",
        "})().catch((error) => { console.error(error); process.exit(1); });",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_portable_write_note_whole_form_save_requires_flag():
    script = "\n".join([
        "const fs = require('fs');",
        "eval(fs.readFileSync(" + json.dumps(str(EXT / "write-note.js")) + ", 'utf8'));",
        "const W = globalThis.FreightDeskPortableWriteNote;",
        "const scan = {",
        "  textareas: [{id:'scratch', label:'Private Load Note', visible:true, value:''}],",
        "  buttons: [{label:'Save', visible:true}, {label:'Save & Exit to Load Board', visible:true}]",
        "};",
        "const denied = W.inspect(scan, {action:'ADD_INTERNAL_NOTE'});",
        "if (denied.ok || denied.code !== 'NOTE_COMMIT_REQUIRES_OWNER_PATH') throw new Error('flagless save leaked: ' + JSON.stringify(denied));",
        "const allowed = W.inspect(scan, {action:'ADD_INTERNAL_NOTE', allow_whole_form_save:true});",
        "if (!allowed.ok || allowed.commit_kind !== 'WHOLE_FORM_SAVE') throw new Error('flagged save blocked: ' + JSON.stringify(allowed));",
        "if (allowed.save_variant !== 'SAVE_STAY') throw new Error('should prefer stay-on-load Save: ' + JSON.stringify(allowed));",
        "if (allowed.target.id !== 'scratch') throw new Error('must target #scratch');",
        "const exitOnly = W.inspect({",
        "  textareas: [{id:'scratch', label:'Private Load Note', visible:true, value:''}],",
        "  buttons: [{label:'Save & Exit to Load Board', visible:true}]",
        "}, {action:'ADD_INTERNAL_NOTE', allow_whole_form_save:true});",
        "if (!exitOnly.ok || exitOnly.save_variant !== 'SAVE_AND_EXIT') throw new Error('exit-only flagged path: ' + JSON.stringify(exitOnly));",
        "if (W.classifyWholeFormSave('Save') !== 'SAVE_STAY' || W.classifyWholeFormSave('Save & Exit to Load Board') !== 'SAVE_AND_EXIT') throw new Error('classify');",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_portable_write_note_execute_whole_form_save_on_scratch():
    script = "\n".join([
        "const fs = require('fs');",
        "globalThis.getComputedStyle = () => ({ visibility: 'visible' });",
        "globalThis.MouseEvent = class { constructor(type, init) { this.type = type; Object.assign(this, init || {}); } };",
        "globalThis.Event = class { constructor(type, init) { this.type = type; Object.assign(this, init || {}); } };",
        "function el(tag, attrs) {",
        "  attrs = attrs || {};",
        "  const node = {",
        "    id: attrs.id || '',",
        "    tagName: String(tag).toUpperCase(),",
        "    textContent: attrs.text || attrs.label || '',",
        "    value: attrs.value || '',",
        "    placeholder: attrs.placeholder || '',",
        "    labels: attrs.label ? [{ textContent: attrs.label }] : [],",
        "    events: [],",
        "    children: attrs.children || [],",
        "    getClientRects: () => (attrs.hidden ? [] : [{}]),",
        "    getAttribute: (name) => name === 'id' ? (attrs.id || '') : ((attrs.attrs || {})[name] || null),",
        "    closest: () => null,",
        "    matches: () => false,",
        "    focus() { node.focused = true; },",
        "    dispatchEvent(ev) { node.events.push(ev.type); return true; },",
        "    querySelectorAll() { return []; },",
        "    querySelector() { return null; }",
        "  };",
        "  return node;",
        "}",
        "const scratch = el('textarea', { id: 'scratch', label: 'Private Load Note', value: '' });",
        "const publicNotes = el('textarea', { id: 'notes', label: 'Public Load Note', value: 'customer visible' });",
        "const save = el('button', { label: 'Save', text: 'Save' });",
        "const saveExit = el('button', { label: 'Save & Exit to Load Board', text: 'Save & Exit to Load Board' });",
        "const heading = el('h2', { text: 'Load Basics' });",
        "const doc = {",
        "  title: 'AscendTMS',",
        "  defaultView: { location: { origin: 'https://ascendtms.com', href: 'https://ascendtms.com/loads' } },",
        "  getElementById: (id) => id === 'scratch' ? scratch : (id === 'notes' ? publicNotes : null),",
        "  querySelectorAll(sel) {",
        "    if (sel.includes('textarea')) return [scratch, publicNotes];",
        "    if (sel.includes('button,input[type=\"submit\"]')) return [save, saveExit];",
        "    if (sel.includes('h1,h2')) return [heading];",
        "    if (sel.includes('input[type=\"search\"]')) return [];",
        "    if (sel.includes('tbody')) return [];",
        "    if (sel.includes('input,select')) return [];",
        "    if (sel === 'label') return [];",
        "    if (sel.includes('[data-note-kind')) return [];",
        "    if (sel.includes('a,[role=\"link\"]')) return [];",
        "    return [];",
        "  }",
        "};",
        "eval(fs.readFileSync(" + json.dumps(str(EXT / "write-note.js")) + ", 'utf8'));",
        "const W = globalThis.FreightDeskPortableWriteNote;",
        "(async () => {",
        "  const denied = await W.execute(doc, { action: 'ADD_INTERNAL_NOTE', load_id: '1763', text: 'secret-note', note_kind: 'PRIVATE_INTERNAL', origin: 'https://ascendtms.com' });",
        "  if (denied.error_code !== 'NOTE_COMMIT_REQUIRES_OWNER_PATH') throw new Error('denied: ' + JSON.stringify(denied));",
        "  if (scratch.value === 'secret-note' || save.events.includes('click') || saveExit.events.includes('click')) throw new Error('typed or saved without flag');",
        "  const allowed = await W.execute(doc, { action: 'ADD_INTERNAL_NOTE', load_id: '1763', text: 'secret-note', note_kind: 'PRIVATE_INTERNAL', origin: 'https://ascendtms.com', allow_whole_form_save: true });",
        "  if (!allowed.ok || !allowed.note_present || allowed.commit_kind !== 'WHOLE_FORM_SAVE') throw new Error('allowed: ' + JSON.stringify(allowed));",
        "  if (allowed.save_variant !== 'SAVE_STAY') throw new Error('expected SAVE_STAY, got ' + allowed.save_variant);",
        "  if (scratch.value !== 'secret-note') throw new Error('did not type #scratch');",
        "  if (publicNotes.value !== 'customer visible' || publicNotes.events.includes('input')) throw new Error('touched #notes');",
        "  if (!save.events.includes('click')) throw new Error('did not activate stay-on-load Save');",
        "  if (saveExit.events.includes('click')) throw new Error('activated Save & Exit when Save was available');",
        "})().catch((error) => { console.error(error); process.exit(1); });",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_portable_write_note_already_open_scratch_skips_opener():
    script = "\n".join([
        "const fs = require('fs');",
        "globalThis.getComputedStyle = () => ({ visibility: 'visible' });",
        "globalThis.MouseEvent = class { constructor(type, init) { this.type = type; Object.assign(this, init || {}); } };",
        "globalThis.Event = class { constructor(type, init) { this.type = type; Object.assign(this, init || {}); } };",
        "function el(tag, attrs) {",
        "  attrs = attrs || {};",
        "  const node = {",
        "    id: attrs.id || '',",
        "    tagName: String(tag).toUpperCase(),",
        "    textContent: attrs.text || attrs.label || '',",
        "    value: attrs.value || '',",
        "    placeholder: attrs.placeholder || '',",
        "    labels: attrs.label ? [{ textContent: attrs.label }] : [],",
        "    events: [],",
        "    children: attrs.children || [],",
        "    getClientRects: () => (attrs.hidden ? [] : [{}]),",
        "    getAttribute: (name) => name === 'id' ? (attrs.id || '') : ((attrs.attrs || {})[name] || null),",
        "    closest: () => null,",
        "    matches: () => false,",
        "    focus() { node.focused = true; },",
        "    dispatchEvent(ev) { node.events.push(ev.type); return true; },",
        "    querySelectorAll() { return []; },",
        "    querySelector() { return null; }",
        "  };",
        "  return node;",
        "}",
        "const scratch = el('textarea', { id: 'scratch', label: 'Private Load Note', value: '' });",
        "const save = el('button', { label: 'Save', text: 'Save' });",
        "const board = {",
        "  title: 'AscendTMS',",
        "  defaultView: { location: { origin: 'https://ascendtms.com', href: 'https://ascendtms.com/loads' } },",
        "  getElementById: (id) => id === 'scratch' ? scratch : null,",
        "  querySelectorAll(sel) {",
        "    if (sel.includes('iframe')) return [];",
        "    if (sel.includes('textarea')) return [];",
        "    if (sel.includes('button,input[type=\"submit\"]')) return [save];",
        "    if (sel.includes('h1,h2')) return [];",
        "    if (sel.includes('input[type=\"search\"]')) return [];",
        "    if (sel.includes('tbody')) return [];",
        "    if (sel.includes('input,select')) return [];",
        "    if (sel === 'label') return [];",
        "    if (sel.includes('[data-note-kind')) return [];",
        "    if (sel.includes('a,[role=\"link\"]')) return [];",
        "    return [];",
        "  }",
        "};",
        "eval(fs.readFileSync(" + json.dumps(str(EXT / "write-note.js")) + ", 'utf8'));",
        "const W = globalThis.FreightDeskPortableWriteNote;",
        "(async () => {",
        "  if (!W.findScratch(board) || W.findScratch(board).id !== 'scratch') throw new Error('findScratch missed #scratch');",
        "  const probe = W.probeWorkspace(board, '1763');",
        "  if (!probe.scratch || !probe.already_open) throw new Error('probe: ' + JSON.stringify(probe));",
        "  const noFlag = await W.execute(board, { action: 'ADD_INTERNAL_NOTE', load_id: '1763', text: 'B2-note', note_kind: 'PRIVATE_INTERNAL', origin: 'https://ascendtms.com' });",
        "  if (noFlag.error_code !== 'NOTE_COMMIT_REQUIRES_OWNER_PATH') throw new Error('no flag: ' + JSON.stringify(noFlag));",
        "  if (noFlag.opener_strategy !== 'already_open') throw new Error('must not LOAD_OPENER_UNVERIFIED when #scratch exists: ' + JSON.stringify(noFlag));",
        "  if (scratch.value === 'B2-note' || save.events.includes('click')) throw new Error('typed/saved without flag');",
        "  const allowed = await W.execute(board, { action: 'ADD_INTERNAL_NOTE', load_id: '1763', text: 'B2-note', note_kind: 'PRIVATE_INTERNAL', origin: 'https://ascendtms.com', allow_whole_form_save: true });",
        "  if (!allowed.ok || !allowed.note_present || allowed.opener_strategy !== 'already_open') throw new Error('allowed: ' + JSON.stringify(allowed));",
        "  if (scratch.value !== 'B2-note') throw new Error('did not type #scratch');",
        "  if (!save.events.includes('click')) throw new Error('did not click Save');",
        "  const typed = el('textarea', { id: 'scratch', label: 'Private Load Note', value: 'B2-note' });",
        "  const emptyDoc = {",
        "    title: 'AscendTMS',",
        "    defaultView: { location: { origin: 'https://ascendtms.com', href: 'https://ascendtms.com/loads' } },",
        "    getElementById: (id) => id === 'scratch' ? typed : null,",
        "    querySelectorAll(sel) {",
        "      if (sel.includes('iframe')) return [];",
        "      if (sel.includes('textarea')) return [];",
        "      if (sel.includes('button,input[type=\"submit\"]')) return [];",
        "      if (sel.includes('h1,h2')) return [];",
        "      if (sel.includes('input[type=\"search\"]')) return [];",
        "      if (sel.includes('tbody')) return [];",
        "      if (sel.includes('input,select')) return [];",
        "      if (sel === 'label') return [];",
        "      if (sel.includes('[data-note-kind')) return [];",
        "      if (sel.includes('a,[role=\"link\"]')) return [];",
        "      return [];",
        "    }",
        "  };",
        "  const leftover = await W.execute(emptyDoc, { action: 'ADD_INTERNAL_NOTE', load_id: '1763', text: 'B2-note', note_kind: 'PRIVATE_INTERNAL', origin: 'https://ascendtms.com', allow_whole_form_save: true });",
        "  if (leftover.error_code !== 'typed_but_not_saved') throw new Error('typed leftover: ' + JSON.stringify(leftover));",
        "  const frameScratch = el('textarea', { id: 'scratch', label: 'Private Load Note', value: '' });",
        "  const frameDoc = {",
        "    getElementById: (id) => id === 'scratch' ? frameScratch : null,",
        "    querySelectorAll(sel) {",
        "      if (sel.includes('iframe')) return [];",
        "      if (sel.includes('textarea')) return [frameScratch];",
        "      return [];",
        "    }",
        "  };",
        "  const framed = {",
        "    getElementById: () => null,",
        "    querySelectorAll(sel) {",
        "      if (sel.includes('iframe')) return [{ contentDocument: frameDoc }];",
        "      return [];",
        "    }",
        "  };",
        "  if (!W.findScratch(framed) || W.findScratch(framed).id !== 'scratch') throw new Error('iframe #scratch missed');",
        "})().catch((error) => { console.error(error); process.exit(1); });",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_portable_write_note_reopen_after_save_and_exit_verifies():
    script = "\n".join([
        "const fs = require('fs');",
        "globalThis.getComputedStyle = () => ({ visibility: 'visible' });",
        "globalThis.MouseEvent = class { constructor(type, init) { this.type = type; Object.assign(this, init || {}); } };",
        "globalThis.Event = class { constructor(type, init) { this.type = type; Object.assign(this, init || {}); } };",
        "function el(tag, attrs) {",
        "  attrs = attrs || {};",
        "  const node = {",
        "    id: attrs.id || '',",
        "    tagName: String(tag).toUpperCase(),",
        "    textContent: attrs.text || attrs.label || '',",
        "    value: attrs.value || '',",
        "    placeholder: attrs.placeholder || '',",
        "    labels: attrs.label ? [{ textContent: attrs.label }] : [],",
        "    events: [],",
        "    children: attrs.children || [],",
        "    getClientRects: () => (attrs.hidden ? [] : [{}]),",
        "    getAttribute: (name) => name === 'id' ? (attrs.id || '') : ((attrs.attrs || {})[name] || null),",
        "    closest: () => null,",
        "    matches: () => false,",
        "    focus() { node.focused = true; },",
        "    dispatchEvent(ev) { node.events.push(ev.type); if (typeof node.onActivate === 'function' && ev.type === 'click') node.onActivate(); return true; },",
        "    querySelectorAll(sel) {",
        "      return (node.children || []).filter((child) => {",
        "        if (sel.includes('td') && child.tagName === 'TD') return true;",
        "        if (sel.includes('a') && child.tagName === 'A') return true;",
        "        if (sel.includes('button') && child.tagName === 'BUTTON') return true;",
        "        return false;",
        "      });",
        "    },",
        "    querySelector() { return null; }",
        "  };",
        "  return node;",
        "}",
        "let phase = 'workspace';",
        "const noteText = 'FreightDesk PR8 0.1.7 WHOLE-FORM B2';",
        "const scratch = el('textarea', { id: 'scratch', label: 'Private Load Note', value: '' });",
        "const saveExit = el('button', { label: 'Save & Exit to Load Board', text: 'Save & Exit to Load Board' });",
        "const idCell = el('td', { text: '1763' });",
        "const view = el('a', { text: 'View', label: 'View' });",
        "const row = { tagName: 'TR', getClientRects: () => [{}], closest: () => null, children: [idCell, view], querySelectorAll(sel) { return this.children.filter((child) => (sel.includes('td') && child.tagName === 'TD') || (sel.includes('a') && child.tagName === 'A')); } };",
        "saveExit.onActivate = () => { phase = 'board'; scratch.getClientRects = () => []; };",
        "view.onActivate = () => { phase = 'workspace'; scratch.getClientRects = () => [{}]; scratch.value = noteText; };",
        "const heading = el('h2', { text: 'Load Basics' });",
        "const doc = {",
        "  title: 'AscendTMS',",
        "  defaultView: { location: { origin: 'https://ascendtms.com', href: 'https://ascendtms.com/loads' } },",
        "  getElementById: (id) => (id === 'scratch' && phase === 'workspace') ? scratch : null,",
        "  querySelectorAll(sel) {",
        "    if (sel.includes('iframe')) return [];",
        "    if (sel.includes('textarea')) return phase === 'workspace' ? [scratch] : [];",
        "    if (sel.includes('button,input[type=\"submit\"]')) return phase === 'workspace' ? [saveExit] : [];",
        "    if (sel.includes('h1,h2')) return phase === 'workspace' ? [heading] : [];",
        "    if (sel.includes('input[type=\"search\"]')) return [];",
        "    if (sel.includes('tbody')) return phase === 'board' ? [row] : [];",
        "    if (sel.includes('input,select')) return [];",
        "    if (sel === 'label') return [];",
        "    if (sel.includes('[data-note-kind')) return [];",
        "    if (sel.includes('a,[role=\"link\"]')) return phase === 'board' ? [view] : [];",
        "    return [];",
        "  }",
        "};",
        "eval(fs.readFileSync(" + json.dumps(str(EXT / "write-note.js")) + ", 'utf8'));",
        "const W = globalThis.FreightDeskPortableWriteNote;",
        "(async () => {",
        "  const result = await W.execute(doc, { action: 'ADD_INTERNAL_NOTE', load_id: '1763', text: noteText, note_kind: 'PRIVATE_INTERNAL', origin: 'https://ascendtms.com', allow_whole_form_save: true });",
        "  if (!result.ok || !result.verified || !result.note_present) throw new Error('reopen verify failed: ' + JSON.stringify(result));",
        "  if (result.save_variant !== 'SAVE_AND_EXIT' || result.commit_kind !== 'WHOLE_FORM_SAVE') throw new Error('variant: ' + JSON.stringify(result));",
        "  if (!saveExit.events.includes('click')) throw new Error('did not click Save & Exit');",
        "  if (!view.events.includes('click')) throw new Error('did not reopen 1763 after Save & Exit');",
        "  if (scratch.value !== noteText) throw new Error('scratch lost note text');",
        "  const stayScratch = el('textarea', { id: 'scratch', label: 'Private Load Note', value: '' });",
        "  const staySave = el('button', { label: 'Save', text: 'Save' });",
        "  const stayExit = el('button', { label: 'Save & Exit to Load Board', text: 'Save & Exit to Load Board' });",
        "  const stayDoc = {",
        "    title: 'AscendTMS',",
        "    defaultView: { location: { origin: 'https://ascendtms.com', href: 'https://ascendtms.com/loads' } },",
        "    getElementById: (id) => id === 'scratch' ? stayScratch : null,",
        "    querySelectorAll(sel) {",
        "      if (sel.includes('iframe')) return [];",
        "      if (sel.includes('textarea')) return [stayScratch];",
        "      if (sel.includes('button,input[type=\"submit\"]')) return [staySave, stayExit];",
        "      if (sel.includes('h1,h2')) return [heading];",
        "      if (sel.includes('input[type=\"search\"]')) return [];",
        "      if (sel.includes('tbody')) return [];",
        "      if (sel.includes('input,select')) return [];",
        "      if (sel === 'label') return [];",
        "      if (sel.includes('[data-note-kind')) return [];",
        "      if (sel.includes('a,[role=\"link\"]')) return [];",
        "      return [];",
        "    }",
        "  };",
        "  const stayed = await W.execute(stayDoc, { action: 'ADD_INTERNAL_NOTE', load_id: '1763', text: noteText, note_kind: 'PRIVATE_INTERNAL', origin: 'https://ascendtms.com', allow_whole_form_save: true });",
        "  if (!stayed.ok || stayed.save_variant !== 'SAVE_STAY') throw new Error('prefer stay: ' + JSON.stringify(stayed));",
        "  if (!staySave.events.includes('click') || stayExit.events.includes('click')) throw new Error('should prefer stay-on-load Save');",
        "})().catch((error) => { console.error(error); process.exit(1); });",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_popup_and_request_stringify_error_objects():
    background = (EXT / "background.js").read_text(encoding="utf-8")
    popup = (EXT / "popup.js").read_text(encoding="utf-8")
    script = "\n".join([
        _extract_function(background, "safeCode"),
        _extract_function(background, "detailCode"),
        _extract_function(popup, "formatLastWrite"),
        "if (safeCode({msg:'NOTE_COMMIT_REQUIRES_OWNER_PATH'}) !== 'NOTE_COMMIT_REQUIRES_OWNER_PATH') throw new Error('safeCode object');",
        "if (safeCode([{loc:['body'], msg:'x'}]) !== 'x') throw new Error('safeCode list');",
        "if (safeCode('[object Object]') !== 'ERROR') throw new Error('safeCode literal');",
        "if (detailCode({detail:[{type:'value_error', msg:'write_not_completable'}]}, 422) !== 'write_not_completable') throw new Error('detailCode');",
        "if (detailCode({detail:{code:'NOTE_CLAIM_FAILED'}}, 403) !== 'NOTE_CLAIM_FAILED') throw new Error('detail object');",
        "const painted = formatLastWrite({status:'FAILED', error_code:{msg:'NOTE_SAVE_CONTROL_UNVERIFIED'}, stage:'inspect', opener_strategy:'already_open', commit_kind:'MISSING'});",
        "if (painted.includes('[object Object]')) throw new Error('popup leaked object: ' + painted);",
        "if (!painted.includes('NOTE_SAVE_CONTROL_UNVERIFIED')) throw new Error('popup missed code: ' + painted);",
        "const claiming = formatLastWrite({status:'DISPATCHED', stage:'claim_wait'});",
        "if (!claiming.includes('claiming')) throw new Error('claim progress missing: ' + claiming);",
        "if (formatLastWrite({status:'FAILED', error_code:[{msg:'BRIDGE_CLAIM_TIMEOUT'}]}).includes('[object Object]')) throw new Error('timeout object leaked');",
    ])
    completed = subprocess.run(["node", "--input-type=commonjs", "-e", script], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout
