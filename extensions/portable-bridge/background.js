'use strict';
const DEFAULT_API = 'http://127.0.0.1:8787';
const ASCEND_ORIGIN = 'https://ascendtms.com';
const ALARM = 'portable-harvest';
const PORTABLE_HEADER = { 'X-FreightDesk-Portable': '1' };
const CONTENT_FILES = Object.freeze(['build.js', 'board-view.js', 'harvest.js', 'write-note.js', 'content.js']);
const WRITE_ALARM = 'portable-writes';
const CONTENT_RELOAD_MESSAGE = 'Reload the Ascend Active Loads tab now (F5), then press Start harvest.';

async function stored() {
  return chrome.storage.local.get({
    api_base: DEFAULT_API,
    device_token: null,
    device_id: null,
    lease: null,
    harvest_enabled: false,
    last_error: null,
    last_harvest: null,
    last_write: null,
    signed_in: false
  });
}

async function save(patch) {
  await chrome.storage.local.set(patch);
  return stored();
}

function apiUrl(base, path) {
  return String(base || DEFAULT_API).replace(/\/$/, '') + path;
}

async function request(path, { method = 'GET', token = null, body = null, extraHeaders = {} } = {}) {
  const state = await stored();
  const headers = { ...PORTABLE_HEADER, ...extraHeaders };
  if (token) headers.Authorization = 'Bearer ' + token;
  if (body) headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(apiUrl(state.api_base, path), {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined
    });
  } catch {
    throw Object.assign(new Error('API_UNREACHABLE'), { code: 'API_UNREACHABLE' });
  }
  let payload = null;
  try { payload = await response.json(); } catch { payload = null; }
  if (!response.ok) {
    const detail = payload?.detail || ('HTTP_' + response.status);
    const code = response.status === 401 ? 'NOT_SIGNED_IN' : String(detail);
    throw Object.assign(new Error(code), { code, status: response.status });
  }
  return payload;
}

async function publicStatus() {
  const state = await stored();
  const view = {
    signed_in: !!state.device_token,
    harvest_enabled: !!state.harvest_enabled,
    api_base: state.api_base,
    lease: state.lease,
    last_error: state.last_error,
    last_harvest: state.last_harvest,
    last_write: state.last_write,
    live_validated: false,
    production_writes: false,
    native_messaging: false,
    origin: ASCEND_ORIGIN
  };
  if (!state.device_token) {
    return { ...view, signed_in: false, code: 'NOT_SIGNED_IN', message: 'Sign in with the demo placeholder to create a lease.' };
  }
  if (!state.lease || state.lease.status !== 'ACTIVE') {
    return { ...view, code: 'LEASE_MISSING', message: 'Create a VISIBLE_BOARD_ONLY harvest lease before starting.' };
  }
  if (state.harvest_enabled && state.last_error?.code === 'CONTENT_UNAVAILABLE') {
    return { ...view, code: 'HARVESTING', message: state.last_error.message || CONTENT_RELOAD_MESSAGE };
  }
  return { ...view, code: state.harvest_enabled ? 'HARVESTING' : 'LEASE_READY' };
}

async function signInPlaceholder() {
  const payload = await request('/v1/portable/session', {
    method: 'POST',
    extraHeaders: PORTABLE_HEADER,
    body: { placeholder: true }
  });
  await chrome.alarms.create(WRITE_ALARM, { periodInMinutes: 1 });
  const next = await save({
    device_token: payload.device_token,
    device_id: payload.device_id,
    signed_in: true,
    last_error: null
  });
  await pollWrites();
  return next;
}

async function signOut() {
  await chrome.alarms.clear(ALARM);
  await chrome.alarms.clear(WRITE_ALARM);
  return save({
    device_token: null,
    device_id: null,
    lease: null,
    harvest_enabled: false,
    signed_in: false,
    last_error: null,
    last_harvest: null,
    last_write: null
  });
}

async function createLease() {
  const state = await stored();
  if (!state.device_token) throw Object.assign(new Error('NOT_SIGNED_IN'), { code: 'NOT_SIGNED_IN' });
  const lease = await request('/v1/portable/leases', {
    method: 'POST',
    token: state.device_token,
    body: { origin: ASCEND_ORIGIN, scope: 'VISIBLE_BOARD_ONLY', ttl_seconds: 900 }
  });
  await chrome.alarms.create(WRITE_ALARM, { periodInMinutes: 1 });
  const next = await save({ lease, last_error: null });
  await pollWrites();
  return next;
}

async function revokeLease() {
  const state = await stored();
  if (!state.device_token) throw Object.assign(new Error('NOT_SIGNED_IN'), { code: 'NOT_SIGNED_IN' });
  if (!state.lease?.id) throw Object.assign(new Error('LEASE_MISSING'), { code: 'LEASE_MISSING' });
  const lease = await request('/v1/portable/leases/' + state.lease.id + '/revoke', {
    method: 'POST',
    token: state.device_token
  });
  await chrome.alarms.clear(ALARM);
  return save({ lease, harvest_enabled: false, last_error: null });
}

async function pollWrites() {
  const state = await stored();
  if (!state.device_token) return;
  let pending;
  try {
    pending = await request('/v1/portable/writes/pending', { token: state.device_token });
  } catch (error) {
    const code = error.code || 'NOTE_CLAIM_FAILED';
    if (code === 'NOT_SIGNED_IN' || code === 'device_session_required') return;
    await save({ last_write: { write_id: null, status: 'FAILED', error_code: code, stage: 'claim' } });
    return;
  }
  if (!pending?.pending || !pending.write_id) return;
  const tabs = await chrome.tabs.query({ url: ASCEND_ORIGIN + '/*' });
  if (!tabs.length) {
    await completeWrite(state.device_token, pending.write_id, {
      verified: false,
      note_present: false,
      error_code: 'ASCEND_TAB_MISSING',
      live_validated: false,
      production_writes: false,
      stage: 'tab',
      opener_strategy: 'none'
    });
    return;
  }
  const tab = pickWriteTab(tabs, pending.load_id);
  await ensureAscendContent(tab, { allowReload: false });
  let result;
  try {
    result = await chrome.tabs.sendMessage(tab.id, {
      action: 'ADD_INTERNAL_NOTE',
      write_id: pending.write_id,
      load_id: pending.load_id,
      text: pending.text,
      note_kind: pending.note_kind || 'PRIVATE_INTERNAL'
    });
  } catch {
    result = { verified: false, note_present: false, error_code: 'CONTENT_UNAVAILABLE', stage: 'content' };
  }
  await completeWrite(state.device_token, pending.write_id, {
    verified: !!result?.verified,
    note_present: !!result?.note_present,
    error_code: result?.error_code || null,
    live_validated: false,
    production_writes: false,
    stage: result?.stage || null,
    opener_strategy: result?.opener_strategy || null,
    note_label: result?.note_label || null,
    commit_kind: result?.commit_kind || null
  });
}

function pickWriteTab(tabs, loadId) {
  const id = String(loadId || '');
  const urlHits = (tabs || []).filter((tab) => id && String(tab.url || '').includes(id));
  if (urlHits.length === 1) return urlHits[0];
  return (tabs || []).find((tab) => tab.active) || tabs[0] || null;
}

async function completeWrite(token, writeId, body) {
  const local = {
    write_id: writeId,
    status: body?.verified && body?.note_present ? 'VERIFIED' : 'FAILED',
    error_code: body?.error_code || null,
    stage: body?.stage || null,
    opener_strategy: body?.opener_strategy || null,
    note_label: body?.note_label || null,
    commit_kind: body?.commit_kind || null,
    completed_at: new Date().toISOString()
  };
  try {
    const receipt = await request('/v1/portable/writes/' + writeId + '/complete', {
      method: 'POST',
      token,
      body
    });
    await save({ last_write: { ...local, status: receipt?.status || local.status,
      error_code: receipt?.error_code || local.error_code } });
  } catch (error) {
    await save({ last_write: { ...local, status: 'FAILED',
      error_code: error.code || 'NOTE_COMPLETE_FAILED', stage: local.stage || 'complete' } });
  }
}

async function setHarvest(enabled) {
  const state = await stored();
  if (enabled) {
    if (!state.device_token) throw Object.assign(new Error('NOT_SIGNED_IN'), { code: 'NOT_SIGNED_IN' });
    if (!state.lease?.id || state.lease.status !== 'ACTIVE' || !state.lease.lease_token) {
      throw Object.assign(new Error('LEASE_MISSING'), { code: 'LEASE_MISSING' });
    }
    await chrome.alarms.create(ALARM, { periodInMinutes: 1 });
    await chrome.alarms.create(WRITE_ALARM, { periodInMinutes: 1 });
    await save({ harvest_enabled: true, last_error: null });
    await ensureOpenAscendTabs({ allowReload: false });
    await harvestOnce();
    return stored();
  }
  await chrome.alarms.clear(ALARM);
  return save({ harvest_enabled: false });
}

async function harvestOnce() {
  const state = await stored();
  if (!state.harvest_enabled || !state.lease?.lease_token) return;
  const tabs = await chrome.tabs.query({ url: ASCEND_ORIGIN + '/*' });
  if (!tabs.length) {
    await save({ last_error: { code: 'ASCEND_TAB_MISSING', message: 'Open Ascend Active Loads at https://ascendtms.com.' } });
    return;
  }
  const tab = tabs.find((item) => item.active) || tabs[0];
  await ensureAscendContent(tab, { allowReload: false });
  let result;
  try {
    result = await chrome.tabs.sendMessage(tab.id, { action: 'HARVEST_BOARD' });
  } catch {
    await save({ last_error: { code: 'CONTENT_UNAVAILABLE', message: CONTENT_RELOAD_MESSAGE } });
    return;
  }
  if (!result?.ok) {
    await save({ last_error: { code: result?.code || 'HARVEST_FAILED', message: harvestMessage(result?.code) } });
    return;
  }
  const snapshot = { ...result.snapshot, lease_id: state.lease.id };
  try {
    const accepted = await request('/v1/portable/harvest', {
      method: 'POST',
      token: state.lease.lease_token,
      body: snapshot
    });
    await save({
      last_error: null,
      last_harvest: {
        accepted_at: new Date().toISOString(),
        revision: accepted.revision,
        row_count: accepted.row_count,
        evidence_class: 'CANDIDATE',
        live_validated: false
      }
    });
  } catch (error) {
    const code = error.code || 'HARVEST_POST_FAILED';
    if (code === 'lease_revoked' || code === 'lease_expired' || code === 'lease_inactive') {
      await chrome.alarms.clear(ALARM);
      await save({ harvest_enabled: false, last_error: { code, message: harvestMessage(code) } });
      return;
    }
    await save({ last_error: { code, message: harvestMessage(code) } });
  }
}

function harvestMessage(code) {
  return ({
    NOT_SIGNED_IN: 'Not signed in. Use demo sign-in or paste a future cloud device token.',
    LEASE_MISSING: 'No active harvest lease.',
    ORIGIN_NOT_ALLOWLISTED: 'This page origin is not allowlisted. Use https://ascendtms.com.',
    ACTIVE_VIEW_UNVERIFIED: 'Active Loads is not verified in the current tab.',
    ACTIVE_VIEW_NOT_ACTIVE_LOADS: 'The visible board is not Active Loads.',
    BOARD_SCHEMA_INVALID: 'The visible grid did not match the identity board contract.',
    NO_VISIBLE_GRID: 'No visible Active Loads grid was found.',
    API_UNREACHABLE: 'The local lease API was unreachable. Start the FreightDesk demo server.',
    CONTENT_UNAVAILABLE: CONTENT_RELOAD_MESSAGE,
    lease_revoked: 'The lease was revoked. Harvest stopped.',
    lease_expired: 'The lease expired. Harvest stopped.',
    ASCEND_TAB_MISSING: 'Open Ascend Active Loads at https://ascendtms.com.'
  })[code] || ('Harvest did not complete (' + (code || 'UNKNOWN') + '). Evidence remains CANDIDATE.');
}

function ascendTabUrl(url) {
  try {
    const parsed = new URL(String(url || ''));
    return parsed.origin === ASCEND_ORIGIN && parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

function isSafeReloadTarget(tab) {
  try {
    const parsed = new URL(String(tab?.url || ''));
    if (parsed.origin !== ASCEND_ORIGIN || parsed.protocol !== 'https:') return false;
    if (parsed.search || parsed.hash) return false;
    if (parsed.pathname !== '/' && parsed.pathname !== '/loads') return false;
    return tab.status === 'complete' || !!tab.discarded;
  } catch {
    return false;
  }
}

async function pingTab(tabId) {
  try {
    const reply = await chrome.tabs.sendMessage(tabId, { action: 'PING' });
    return !!reply?.ok;
  } catch {
    return false;
  }
}

async function injectIsolatedContent(tabId) {
  if (!chrome.scripting?.executeScript) return false;
  await chrome.scripting.executeScript({
    target: { tabId, frameIds: [0] },
    world: 'ISOLATED',
    files: [...CONTENT_FILES]
  });
  return true;
}

async function ensureAscendContent(tab, { allowReload = false } = {}) {
  if (!tab?.id || !ascendTabUrl(tab.url)) return 'skipped';
  if (await pingTab(tab.id)) return 'ready';
  try {
    await injectIsolatedContent(tab.id);
  } catch {
    // Injection can fail on a discarded or still-loading tab.
  }
  if (await pingTab(tab.id)) return 'injected';
  if (allowReload && isSafeReloadTarget(tab)) {
    try {
      await chrome.tabs.reload(tab.id);
      return 'reloaded';
    } catch {
      return 'reload_required';
    }
  }
  return 'reload_required';
}

async function ensureOpenAscendTabs({ allowReload = false } = {}) {
  const tabs = await chrome.tabs.query({ url: ASCEND_ORIGIN + '/*' });
  for (const tab of tabs) {
    await ensureAscendContent(tab, { allowReload });
  }
}

chrome.runtime.onInstalled.addListener((details) => {
  chrome.storage.local.set({ api_base: DEFAULT_API, harvest_enabled: false, live_validated: false });
  const allowReload = details.reason === 'install' || details.reason === 'update';
  ensureOpenAscendTabs({ allowReload });
});

chrome.runtime.onStartup.addListener(() => {
  ensureOpenAscendTabs({ allowReload: false });
  chrome.alarms.create(WRITE_ALARM, { periodInMinutes: 1 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM) harvestOnce();
  if (alarm.name === WRITE_ALARM) pollWrites();
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const actions = {
    STATUS: publicStatus,
    SIGN_IN: signInPlaceholder,
    SIGN_OUT: signOut,
    CREATE_LEASE: createLease,
    REVOKE: revokeLease,
    START: () => setHarvest(true),
    STOP: () => setHarvest(false),
    SET_API: async () => {
      const apiBase = String(message.api_base || DEFAULT_API).replace(/\/$/, '');
      if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(apiBase)) {
        throw Object.assign(new Error('API_ORIGIN_DENIED'), { code: 'API_ORIGIN_DENIED' });
      }
      return save({ api_base: apiBase });
    }
  };
  const run = actions[message?.action];
  if (!run) return;
  Promise.resolve().then(run).then(sendResponse).catch(async (error) => {
    const code = error.code || error.message || 'ERROR';
    await save({ last_error: { code, message: harvestMessage(code) } });
    sendResponse({ error: true, code, message: harvestMessage(code) });
  });
  return true;
});
