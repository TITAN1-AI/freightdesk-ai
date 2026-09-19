(() => {
  'use strict';
  const ORIGIN = 'https://ascendtms.com';
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.action !== 'HARVEST_BOARD') return;
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
