"""Manifest and packaged-identity smoke for the portable bridge. Load unpacked is owner-manual."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extensions" / "portable-bridge"
FORBIDDEN = ("nativeMessaging", "connectNative", "eval(", "new Function", "document.cookie",
             "WebSocket(", ".click(", ".submit(", "ASCEND_SAVE", "ASCEND_SET_DRIVER")


def test_portable_manifest_has_no_native_host_and_keeps_write_block():
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["name"] == "FreightDesk Bridge"
    assert manifest["version"] == "0.1.1"
    assert "nativeMessaging" not in manifest["permissions"]
    assert manifest["permissions"] == ["storage", "alarms", "scripting"]
    assert manifest["host_permissions"][0] == "https://ascendtms.com/*"
    assert "http://127.0.0.1/*" in manifest["host_permissions"]
    assert manifest["content_scripts"][0]["matches"] == ["https://ascendtms.com/*"]
    assert manifest["content_scripts"][0]["js"] == ["build.js", "board-view.js", "harvest.js", "content.js"]
    assert manifest["content_scripts"][0]["world"] == "ISOLATED"
    assert manifest["content_scripts"][0]["all_frames"] is False
    assert "externally_connectable" not in manifest
    assert "web_accessible_resources" not in manifest
    identity = (EXT / "build.js").read_text(encoding="utf-8")
    assert "extension_version: '0.1.1'" in identity
    assert "native_messaging: false" in identity
    assert "live_validated: false" in identity
    assert "production_writes: false" in identity
    sources = "\n".join(path.read_text(encoding="utf-8") for path in EXT.glob("*.js"))
    for token in FORBIDDEN:
        assert token not in sources
    assert "chrome.runtime.connectNative" not in sources
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
    assert "CONTENT_FILES = Object.freeze(['build.js', 'board-view.js', 'harvest.js', 'content.js'])" in background
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
    assert "Reload the Ascend **Active Loads** tab now" in readme
    assert "chrome.scripting.executeScript" in readme


def _extract_function(source: str, name: str) -> str:
    token = "function " + name
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
        "const CONTENT_FILES = Object.freeze(['build.js', 'board-view.js', 'harvest.js', 'content.js']);",
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
        "  if (inject.files.join(',') !== 'build.js,board-view.js,harvest.js,content.js') throw new Error('bad files');",
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
