(() => {
  'use strict';
  if (globalThis.FreightDeskPortableContentBound) return;
  globalThis.FreightDeskPortableContentBound = true;
  const ORIGIN = 'https://ascendtms.com';
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message) return;
    if (message.action === 'PING') {
      sendResponse({ ok: true, ready: true });
      return;
    }
    if (message.action === 'PROBE_NOTE_WORKSPACE') {
      const probe = FreightDeskPortableWriteNote.probeWorkspace(document, message.load_id, message.text);
      sendResponse({ ok: true, ...probe });
      return;
    }
    if (message.action === 'ADD_INTERNAL_NOTE') {
      Promise.resolve().then(async () => {
        if (location.origin !== ORIGIN) {
          return { ok: false, verified: false, note_present: false, error_code: 'ORIGIN_NOT_ALLOWLISTED' };
        }
        return FreightDeskPortableWriteNote.execute(document, { ...message, origin: ORIGIN });
      }).then(sendResponse);
      return true;
    }
    if (message.action !== 'HARVEST_BOARD') return;
    Promise.resolve().then(async () => {
      if (location.origin !== ORIGIN) return { ok: false, code: 'ORIGIN_NOT_ALLOWLISTED' };
      try {
        const snapshot = await FreightDeskPortableHarvest.capture(document, location.origin);
        return { ok: true, snapshot };
      } catch (error) {
        return { ok: false, code: error?.code || error?.message || 'HARVEST_FAILED' };
      }
    }).then(sendResponse);
    return true;
  });
})();
