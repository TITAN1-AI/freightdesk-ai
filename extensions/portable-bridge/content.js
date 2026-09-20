(() => {
  'use strict';
  const ORIGIN = 'https://ascendtms.com';
  const CONTENT_REV = '0.1.11';
  if (globalThis.FreightDeskPortableContentListener) {
    try { chrome.runtime.onMessage.removeListener(globalThis.FreightDeskPortableContentListener); } catch { /* keep going */ }
  }
  function onMessage(message, _sender, sendResponse) {
    if (!message || globalThis.FreightDeskPortableContentRev !== CONTENT_REV) return;
    if (message.action === 'PING') {
      sendResponse({ ok: true, ready: true, rev: CONTENT_REV });
      return;
    }
    if (message.action === 'PROBE_NOTE_WORKSPACE') {
      const probe = FreightDeskPortableWriteNote.probeWorkspace(document, message.load_id, message.text);
      sendResponse({ ok: true, rev: CONTENT_REV, ...probe });
      return;
    }
    if (message.action === 'PROBE_STATUS_WORKSPACE') {
      const probe = FreightDeskPortableWriteStatus.probeWorkspace(
        document, message.load_id, message.status || message.requested_status);
      sendResponse({ ok: true, rev: CONTENT_REV, ...probe });
      return;
    }
    if (message.action === 'CHANGE_LOAD_STATUS' || message.action === 'REOPEN_AND_VERIFY_STATUS' ||
        message.action === 'VERIFY_STATUS') {
      Promise.resolve().then(async () => {
        if (location.origin !== ORIGIN) {
          return { ok: false, verified: false, status_matched: false, error_code: 'ORIGIN_NOT_ALLOWLISTED' };
        }
        const mode = message.action === 'VERIFY_STATUS' ? 'verify'
          : (message.action === 'REOPEN_AND_VERIFY_STATUS' ? 'reopen' : message.mode);
        return FreightDeskPortableWriteStatus.execute(document, { ...message, origin: ORIGIN, mode });
      }).then(sendResponse);
      return true;
    }
    if (message.action === 'ADD_INTERNAL_NOTE' || message.action === 'REOPEN_AND_VERIFY' ||
        message.action === 'VERIFY_NOTE') {
      Promise.resolve().then(async () => {
        if (location.origin !== ORIGIN) {
          return { ok: false, verified: false, note_present: false, error_code: 'ORIGIN_NOT_ALLOWLISTED' };
        }
        const mode = message.action === 'VERIFY_NOTE' ? 'verify'
          : (message.action === 'REOPEN_AND_VERIFY' ? 'reopen' : message.mode);
        return FreightDeskPortableWriteNote.execute(document, { ...message, origin: ORIGIN, mode });
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
  }
  globalThis.FreightDeskPortableContentRev = CONTENT_REV;
  globalThis.FreightDeskPortableContentBound = true;
  globalThis.FreightDeskPortableContentListener = onMessage;
  chrome.runtime.onMessage.addListener(onMessage);
})();
