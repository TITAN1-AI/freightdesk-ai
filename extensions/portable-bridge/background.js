'use strict';
const DEFAULT_API = 'http://127.0.0.1:8787';
const ASCEND_ORIGIN = 'https://ascendtms.com';
const ALARM = 'portable-harvest';
const PORTABLE_HEADER = { 'X-FreightDesk-Portable': '1' };
const CONTENT_FILES = Object.freeze(['build.js', 'board-view.js', 'harvest.js', 'write-note.js', 'write-status.js', 'content.js']);
const BRIDGE_VERSION = '0.1.11';
const WRITE_ALARM = 'portable-writes';
const WRITE_SOON = 'portable-writes-soon';
const CONTENT_RELOAD_MESSAGE = 'Reload the Ascend Active Loads tab now (F5), then press Start harvest.';
let writePollInFlight = null;

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
    const code = response.status === 401 ? 'NOT_SIGNED_IN' : detailCode(payload, response.status);
    throw Object.assign(new Error(code), { code, status: response.status });
  }
  return payload;
}

function detailCode(payload, status) {
  const detail = payload && payload.detail;
  const code = safeCode(detail);
  if (code && code !== 'ERROR' && code !== '[object Object]') return code;
  return 'HTTP_' + status;
}

function safeCode(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'string') return value === '[object Object]' ? 'ERROR' : value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value) && value.length) return safeCode(value[0]);
  if (typeof value === 'object') {
    return safeCode(value.code || value.error_code || value.msg || value.message || value.detail || value.type) || 'ERROR';
  }
  return 'ERROR';
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
  await armWritePolls();
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
  await chrome.alarms.clear(WRITE_SOON);
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
  await armWritePolls();
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

async function armWritePolls() {
  await chrome.alarms.create(WRITE_ALARM, { periodInMinutes: 1 });
  await chrome.alarms.create(WRITE_SOON, { when: Date.now() + 1000 });
}

function scheduleWriteSoon() {
  chrome.alarms.create(WRITE_SOON, { when: Date.now() + 4000 });
}

async function markWrite(patch) {
  const state = await stored();
  const prev = state.last_write || {};
  return save({ last_write: { ...prev, ...patch, updated_at: new Date().toISOString() } });
}

async function claimPendingWithRetry(token) {
  let last = null;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      return await request('/v1/portable/writes/pending', { token });
    } catch (error) {
      last = error;
      const code = safeCode(error?.code) || 'NOTE_CLAIM_FAILED';
      if (code === 'NOT_SIGNED_IN' || code === 'device_session_required') throw error;
      await new Promise((resolve) => setTimeout(resolve, 300 * (attempt + 1)));
    }
  }
  throw last || Object.assign(new Error('NOTE_CLAIM_FAILED'), { code: 'NOTE_CLAIM_FAILED' });
}

async function pollWrites() {
  if (writePollInFlight) return writePollInFlight;
  writePollInFlight = pollWritesOnce().finally(() => { writePollInFlight = null; });
  return writePollInFlight;
}

async function pollWritesOnce() {
  const state = await stored();
  if (!state.device_token) return;
  scheduleWriteSoon();
  if (state.last_write && (state.last_write.status === 'DISPATCHED' || state.last_write.status === 'IDLE')) {
    await markWrite({
      status: 'DISPATCHED',
      stage: state.last_write.stage === 'claimed' ? 'claimed' : 'claim_wait',
      error_code: null,
      write_id: state.last_write.write_id || null
    });
  }
  let pending;
  try {
    pending = await claimPendingWithRetry(state.device_token);
  } catch (error) {
    const code = safeCode(error.code) || 'NOTE_CLAIM_FAILED';
    if (code === 'NOT_SIGNED_IN' || code === 'device_session_required') return;
    await markWrite({ write_id: state.last_write?.write_id || null, status: 'FAILED', error_code: code, stage: 'claim' });
    return;
  }
  if (!pending?.pending || !pending.write_id) {
    const timeout = safeCode(pending?.error_code);
    if (timeout === 'BRIDGE_CLAIM_TIMEOUT') {
      await markWrite({
        write_id: pending.write_id || state.last_write?.write_id || null,
        status: 'FAILED',
        error_code: 'BRIDGE_CLAIM_TIMEOUT',
        stage: 'claim'
      });
    }
    return;
  }
  await markWrite({
    write_id: pending.write_id,
    load_id: pending.load_id,
    status: 'DISPATCHED',
    stage: 'claimed',
    error_code: null,
    allow_whole_form_save: !!pending.allow_whole_form_save,
    commit_kind: pending.commit_kind || null
  });
  const tabs = await chrome.tabs.query({ url: ASCEND_ORIGIN + '/*' });
  if (!tabs.length) {
    await completeWrite(state.device_token, pending.write_id, {
      verified: false,
      note_present: false,
      error_code: 'ASCEND_TAB_MISSING',
      live_validated: false,
      production_writes: false,
      stage: 'tab',
      opener_strategy: 'none',
      tab_hint: 'no_tab',
      bridge_version: BRIDGE_VERSION
    });
    return;
  }
  for (const candidate of tabs) {
    await ensureWriteContent(candidate);
  }
  const isStatus = pending.action === 'CHANGE_LOAD_STATUS' ||
    pending.policy_action === 'ASCEND_CHANGE_LOAD_STATUS';
  const choice = await pickWriteTab(tabs, pending.load_id, pending.status || pending.requested_status);
  const tab = choice?.tab;
  const tabHint = choice.tab_hint || (tab?.id ? ('tab:' + tab.id) : 'no_tab');
  if (tab?.id && chrome.tabs?.update) {
    try { await chrome.tabs.update(tab.id, { active: true }); } catch { /* keep going */ }
  }
  await ensureWriteContent(tab);
  let result;
  try {
    result = await chrome.tabs.sendMessage(tab.id, isStatus ? {
      action: 'CHANGE_LOAD_STATUS',
      write_id: pending.write_id,
      load_id: pending.load_id,
      status: pending.status || pending.requested_status,
      requested_status: pending.requested_status || pending.status,
      allow_whole_form_save: !!pending.allow_whole_form_save,
      forbid_searchbox: !!(choice.scratch_present || choice.status_present),
      tab_hint: tabHint
    } : {
      action: 'ADD_INTERNAL_NOTE',
      write_id: pending.write_id,
      load_id: pending.load_id,
      text: pending.text,
      note_kind: pending.note_kind || 'PRIVATE_INTERNAL',
      allow_whole_form_save: !!pending.allow_whole_form_save,
      forbid_searchbox: !!choice.scratch_present,
      tab_hint: tabHint
    });
  } catch {
    result = { verified: false, note_present: false, status_matched: false,
      error_code: 'CONTENT_UNAVAILABLE', stage: 'content' };
  }
  if (isStatus) {
    const shouldReopen = result?.save_variant === 'SAVE_AND_EXIT'
      || result?.stage === 'reopen'
      || result?.error_code === 'LOAD_OPENER_UNVERIFIED'
      || result?.error_code === 'CONTENT_UNAVAILABLE'
      || result?.error_code === 'status_not_matched';
    if (shouldReopen && (!result?.verified || !result?.status_matched)) {
      result = await reopenStatusFromBackground(tabs, tab, pending, result, tabHint);
    } else if (!result?.verified || !result?.status_matched) {
      const recovered = await recoverStatusOnAnyTab(tabs, pending.load_id,
        pending.status || pending.requested_status);
      if (recovered.status_matched) {
        result = {
          ...(result || {}),
          verified: true,
          status_matched: true,
          observed_status: recovered.observed_status || result?.observed_status,
          error_code: null,
          stage: 'verify',
          opener_strategy: result?.opener_strategy || 'already_open',
          verify_reason: 'verified_via_status_readback',
          tab_hint: recovered.tab_hint || tabHint
        };
      }
    }
    await completeWrite(state.device_token, pending.write_id, {
      verified: !!result?.verified,
      note_present: false,
      status_matched: !!result?.status_matched,
      observed_status: result?.observed_status || null,
      error_code: safeCode(result?.error_code),
      live_validated: false,
      production_writes: false,
      stage: result?.stage || 'execute',
      opener_strategy: result?.opener_strategy || null,
      commit_kind: result?.commit_kind || null,
      save_variant: result?.save_variant || null,
      tab_hint: tabHint,
      reopen_attempts: result?.reopen_attempts || 0,
      verify_reason: result?.verify_reason || null,
      bridge_version: BRIDGE_VERSION,
      allow_whole_form_save: !!pending.allow_whole_form_save
    });
    return;
  }
  const shouldReopen = result?.save_variant === 'SAVE_AND_EXIT'
    || result?.stage === 'reopen'
    || result?.error_code === 'LOAD_OPENER_UNVERIFIED'
    || result?.error_code === 'CONTENT_UNAVAILABLE'
    || result?.error_code === 'note_not_present';
  if (shouldReopen && (!result?.verified || !result?.note_present)) {
    result = await reopenFromBackground(tabs, tab, pending, result, tabHint);
  } else if (!result?.verified || !result?.note_present) {
    const recovered = await recoverNoteOnAnyTab(tabs, pending.load_id, pending.text);
    if (recovered.note_present) {
      result = {
        ...(result || {}),
        verified: true,
        note_present: true,
        error_code: null,
        stage: 'verify',
        opener_strategy: result?.opener_strategy || 'already_open',
        verify_reason: 'verified_via_scratch_scan',
        tab_hint: recovered.tab_hint || tabHint
      };
    }
  }
  await completeWrite(state.device_token, pending.write_id, {
    verified: !!result?.verified,
    note_present: !!result?.note_present,
    error_code: safeCode(result?.error_code),
    live_validated: false,
    production_writes: false,
    stage: result?.stage || 'execute',
    opener_strategy: result?.opener_strategy || null,
    note_label: result?.note_label || null,
    commit_kind: result?.commit_kind || null,
    save_variant: result?.save_variant || null,
    tab_hint: tabHint,
    reopen_attempts: result?.reopen_attempts || 0,
    verify_reason: result?.verify_reason || null,
    bridge_version: BRIDGE_VERSION,
    allow_whole_form_save: !!pending.allow_whole_form_save
  });
}

async function ensureWriteContent(tab) {
  if (!tab?.id || !ascendTabUrl(tab.url)) return 'skipped';
  try {
    await injectIsolatedContent(tab.id);
  } catch { /* keep probing */ }
  if (await pingTab(tab.id)) return 'injected';
  return 'reload_required';
}

function knownLoadTabUrl(loadId) {
  const id = String(loadId || '');
  if (!/^\d{1,20}$/.test(id)) return null;
  return ASCEND_ORIGIN + '/loads/' + id;
}

async function waitTabComplete(tabId, timeoutMs) {
  if (!tabId) return 'no_tab';
  if (!chrome.tabs?.onUpdated) {
    await new Promise((resolve) => setTimeout(resolve, Math.min(timeoutMs || 2000, 2000)));
    return 'slept';
  }
  return new Promise((resolve) => {
    let done = false;
    const finish = (reason) => {
      if (done) return;
      done = true;
      try { chrome.tabs.onUpdated.removeListener(listener); } catch { /* ignore */ }
      resolve(reason);
    };
    const timer = setTimeout(() => finish('timeout'), timeoutMs == null ? 4000 : timeoutMs);
    const listener = (id, info) => {
      if (id === tabId && info.status === 'complete') {
        clearTimeout(timer);
        finish('complete');
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
  });
}

async function reopenFromBackground(tabs, tab, pending, result, tabHint, backoffMs) {
  const step = backoffMs == null ? 1000 : backoffMs;
  let attempts = Number(result?.reopen_attempts) || 0;
  let lastStrategy = result?.opener_strategy || 'none';
  let latest = tabs || [];
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, step * (attempt + 1)));
    attempts += 1;
    try { latest = await chrome.tabs.query({ url: ASCEND_ORIGIN + '/*' }); } catch { latest = tabs || []; }
    const recovered = await recoverNoteOnAnyTab(latest, pending.load_id, pending.text);
    if (recovered.note_present) {
      return {
        ...(result || {}),
        verified: true,
        note_present: true,
        error_code: null,
        stage: 'verify',
        opener_strategy: lastStrategy === 'none' ? 'already_open' : lastStrategy,
        tab_hint: recovered.tab_hint || tabHint,
        reopen_attempts: attempts,
        verify_reason: 'verified_via_scratch_scan'
      };
    }
    for (const candidate of latest) {
      await ensureWriteContent(candidate);
      try {
        const reply = await chrome.tabs.sendMessage(candidate.id, {
          action: 'REOPEN_AND_VERIFY',
          load_id: pending.load_id,
          text: pending.text,
          tab_hint: tabHint,
          reopen_backoff_ms: 5,
          wait_board_attempts: 4
        });
        lastStrategy = reply?.opener_strategy || lastStrategy;
        attempts += Number(reply?.reopen_attempts) || 0;
        if (reply?.note_present || reply?.verified) {
          return {
            ...(result || {}),
            ...reply,
            verified: true,
            note_present: true,
            error_code: null,
            stage: 'verify',
            tab_hint: tabHint,
            reopen_attempts: attempts,
            verify_reason: reply?.verify_reason || null
          };
        }
      } catch { /* try next tab or URL */ }
    }
    const href = knownLoadTabUrl(pending.load_id);
    const target = latest.find((item) => item.active) || tab || latest[0];
    if (href && target?.id && chrome.tabs?.update) {
      try {
        await chrome.tabs.update(target.id, { url: href });
        lastStrategy = 'known_load_url';
        await waitTabComplete(target.id, 4000);
        await ensureWriteContent(target);
        const verify = await chrome.tabs.sendMessage(target.id, {
          action: 'VERIFY_NOTE',
          load_id: pending.load_id,
          text: pending.text,
          tab_hint: tabHint
        });
        if (verify?.note_present || verify?.verified) {
          return {
            ...(result || {}),
            verified: true,
            note_present: true,
            error_code: null,
            stage: 'verify',
            opener_strategy: 'known_load_url',
            tab_hint: tabHint,
            reopen_attempts: attempts,
            verify_reason: verify?.verify_reason || 'verified_via_scratch_scan'
          };
        }
      } catch { /* next backoff */ }
    }
  }
  const finalScan = await recoverNoteOnAnyTab(latest, pending.load_id, pending.text);
  if (finalScan.note_present) {
    return {
      ...(result || {}),
      verified: true,
      note_present: true,
      error_code: null,
      stage: 'verify',
      opener_strategy: lastStrategy,
      tab_hint: finalScan.tab_hint || tabHint,
      reopen_attempts: attempts,
      verify_reason: 'verified_via_scratch_scan'
    };
  }
  return {
    ...(result || {}),
    verified: false,
    note_present: false,
    error_code: safeCode(result?.error_code) || 'LOAD_OPENER_UNVERIFIED',
    stage: 'reopen',
    opener_strategy: lastStrategy || 'none',
    tab_hint: tabHint,
    reopen_attempts: attempts,
    verify_reason: null
  };
}

async function recoverStatusOnAnyTab(tabs, loadId, requested) {
  const probed = [];
  for (const tab of tabs || []) {
    const probe = await probeTabStatus(tab, loadId, requested);
    probed.push({ tab, scratch: !!probe.status_control, status_matched: !!probe.status_matched });
    if (probe.status_matched) {
      return {
        status_matched: true,
        observed_status: probe.observed_status || null,
        tab_hint: tabHintFor({ tab, scratch: true }, probed)
      };
    }
  }
  return { status_matched: false };
}

async function probeTabStatus(tab, loadId, requested) {
  if (!tab?.id || typeof chrome === 'undefined' || !chrome.tabs?.sendMessage) {
    return { status_control: false, status_matched: false };
  }
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const reply = await chrome.tabs.sendMessage(tab.id, {
        action: 'PROBE_STATUS_WORKSPACE',
        load_id: loadId,
        status: requested || null
      });
      return {
        status_control: !!(reply?.status_control || reply?.already_open),
        observed_status: reply?.observed_status || null,
        status_matched: !!reply?.status_matched
      };
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 150 * (attempt + 1)));
    }
  }
  return { status_control: false, status_matched: false };
}

async function reopenStatusFromBackground(tabs, tab, pending, result, tabHint, backoffMs) {
  const step = backoffMs == null ? 1000 : backoffMs;
  const requested = pending.status || pending.requested_status;
  let attempts = Number(result?.reopen_attempts) || 0;
  let lastStrategy = result?.opener_strategy || 'none';
  let latest = tabs || [];
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, step * (attempt + 1)));
    attempts += 1;
    try { latest = await chrome.tabs.query({ url: ASCEND_ORIGIN + '/*' }); } catch { latest = tabs || []; }
    const recovered = await recoverStatusOnAnyTab(latest, pending.load_id, requested);
    if (recovered.status_matched) {
      return {
        ...(result || {}),
        verified: true,
        status_matched: true,
        observed_status: recovered.observed_status,
        error_code: null,
        stage: 'verify',
        opener_strategy: lastStrategy === 'none' ? 'already_open' : lastStrategy,
        tab_hint: recovered.tab_hint || tabHint,
        reopen_attempts: attempts,
        verify_reason: 'verified_via_status_readback'
      };
    }
    for (const candidate of latest) {
      await ensureWriteContent(candidate);
      try {
        const reply = await chrome.tabs.sendMessage(candidate.id, {
          action: 'REOPEN_AND_VERIFY_STATUS',
          load_id: pending.load_id,
          status: requested,
          tab_hint: tabHint,
          reopen_backoff_ms: 5,
          wait_board_attempts: 4
        });
        lastStrategy = reply?.opener_strategy || lastStrategy;
        attempts += Number(reply?.reopen_attempts) || 0;
        if (reply?.status_matched || reply?.verified) {
          return {
            ...(result || {}),
            ...reply,
            verified: true,
            status_matched: true,
            error_code: null,
            stage: 'verify',
            tab_hint: tabHint,
            reopen_attempts: attempts,
            verify_reason: reply?.verify_reason || 'verified_via_status_readback'
          };
        }
      } catch { /* try next tab or URL */ }
    }
    const href = knownLoadTabUrl(pending.load_id);
    const target = latest.find((item) => item.active) || tab || latest[0];
    if (href && target?.id && chrome.tabs?.update) {
      try {
        await chrome.tabs.update(target.id, { url: href });
        lastStrategy = 'known_load_url';
        await waitTabComplete(target.id, 4000);
        await ensureWriteContent(target);
        const verify = await chrome.tabs.sendMessage(target.id, {
          action: 'VERIFY_STATUS',
          load_id: pending.load_id,
          status: requested,
          tab_hint: tabHint
        });
        if (verify?.status_matched || verify?.verified) {
          return {
            ...(result || {}),
            verified: true,
            status_matched: true,
            observed_status: verify?.observed_status,
            error_code: null,
            stage: 'verify',
            opener_strategy: 'known_load_url',
            tab_hint: tabHint,
            reopen_attempts: attempts,
            verify_reason: verify?.verify_reason || 'verified_via_status_readback'
          };
        }
      } catch { /* next backoff */ }
    }
  }
  const finalScan = await recoverStatusOnAnyTab(latest, pending.load_id, requested);
  if (finalScan.status_matched) {
    return {
      ...(result || {}),
      verified: true,
      status_matched: true,
      observed_status: finalScan.observed_status,
      error_code: null,
      stage: 'verify',
      opener_strategy: lastStrategy,
      tab_hint: finalScan.tab_hint || tabHint,
      reopen_attempts: attempts,
      verify_reason: 'verified_via_status_readback'
    };
  }
  return {
    ...(result || {}),
    verified: false,
    status_matched: false,
    error_code: safeCode(result?.error_code) || 'LOAD_OPENER_UNVERIFIED',
    stage: 'reopen',
    opener_strategy: lastStrategy || 'none',
    tab_hint: tabHint,
    reopen_attempts: attempts,
    verify_reason: null
  };
}

async function recoverNoteOnAnyTab(tabs, loadId, text) {
  const probed = [];
  for (const tab of tabs || []) {
    const probe = await probeTabScratch(tab, loadId, text);
    probed.push({ tab, scratch: !!probe.scratch, note_present: !!probe.note_present });
    if (probe.note_present) {
      return {
        note_present: true,
        tab_hint: tabHintFor({ tab, scratch: true }, probed)
      };
    }
  }
  return { note_present: false };
}

async function probeTabScratchDom(tab, expectedText) {
  if (!tab?.id || typeof chrome === 'undefined' || !chrome.scripting?.executeScript) {
    return { scratch: false, note_present: false };
  }
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id, allFrames: true },
      world: 'ISOLATED',
      args: [String(expectedText || '')],
      func: (expected) => {
        const seen = [];
        const walk = (root, acc) => {
          if (!root || seen.indexOf(root) >= 0) return;
          seen.push(root);
          acc.push(root);
          let frames = [];
          try { frames = [...root.querySelectorAll('iframe,frame')]; } catch { frames = []; }
          for (const frame of frames) {
            try { walk(frame.contentDocument, acc); } catch { /* cross-origin */ }
          }
        };
        const docs = [];
        walk(document, docs);
        for (const root of docs) {
          let el = null;
          try { el = root.getElementById ? root.getElementById('scratch') : null; } catch { el = null; }
          if (el) {
            const value = String(el.value || '');
            return { scratch: true, note_present: !!(expected && value.indexOf(expected) >= 0) };
          }
          let labeled = [];
          try { labeled = [...root.querySelectorAll('textarea,[role="textbox"],label')]; } catch { labeled = []; }
          for (const node of labeled) {
            const text = String(
              (node.getAttribute && node.getAttribute('aria-label')) || node.placeholder || node.textContent || ''
            ).replace(/\s+/g, ' ').trim().toLowerCase();
            if (text.indexOf('private load note') >= 0 || text.indexOf('private notes') >= 0 ||
                text.indexOf('internal notes') >= 0 || text.indexOf('internal load note') >= 0) {
              const value = String(node.value || '');
              return { scratch: true, note_present: !!(expected && value.indexOf(expected) >= 0) };
            }
          }
        }
        return { scratch: false, note_present: false };
      }
    });
    return {
      scratch: (results || []).some((item) => !!(item && item.result && item.result.scratch)),
      note_present: (results || []).some((item) => !!(item && item.result && item.result.note_present))
    };
  } catch {
    return { scratch: false, note_present: false };
  }
}

async function probeTabScratch(tab, loadId, expectedText) {
  if (!tab?.id || typeof chrome === 'undefined' || !chrome.tabs?.sendMessage) {
    return { scratch: false, note_present: false };
  }
  let messageProbe = { scratch: false, note_present: false };
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (typeof ensureAscendContent === 'function') {
      try { await ensureAscendContent(tab, { allowReload: false }); } catch { /* keep probing */ }
    }
    try {
      const reply = await chrome.tabs.sendMessage(tab.id, {
        action: 'PROBE_NOTE_WORKSPACE',
        load_id: loadId,
        text: expectedText || null
      });
      messageProbe = {
        scratch: !!(reply?.scratch || reply?.already_open),
        note_label: reply?.note_label || null,
        note_present: !!reply?.note_present
      };
      if (messageProbe.note_present || (messageProbe.scratch && !expectedText)) return messageProbe;
      break;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 150 * (attempt + 1)));
    }
  }
  const domProbe = await probeTabScratchDom(tab, expectedText);
  if (domProbe.note_present || (domProbe.scratch && !expectedText)) {
    return {
      scratch: true,
      note_present: !!domProbe.note_present,
      note_label: messageProbe.note_label || 'scratch'
    };
  }
  return messageProbe;
}

function tabHintFor(chosen, probed) {
  if (!chosen?.tab) return 'no_tab';
  const reason = chosen.scratch ? 'scratch' : (chosen.urlHit ? 'url' : (chosen.active ? 'active' : 'first'));
  const skipped = (probed || []).filter((item) => item.tab && item.tab.id !== chosen.tab.id)
    .map((item) => (item.scratch ? 'scratch:' : 'board:') + item.tab.id);
  return (reason + ':' + chosen.tab.id + (skipped.length ? ';skip=' + skipped.join(',') : '')).slice(0, 80);
}

async function pickWriteTab(tabs, loadId, requestedStatus) {
  const id = String(loadId || '');
  const probed = [];
  for (const tab of tabs || []) {
    const probe = await probeTabScratch(tab, id);
    const statusProbe = requestedStatus ? await probeTabStatus(tab, id, requestedStatus) : { status_control: false };
    probed.push({
      tab,
      scratch: !!(probe.scratch || statusProbe.status_control),
      status_control: !!statusProbe.status_control,
      urlHit: !!(id && String(tab.url || '').includes(id)),
      active: !!tab.active
    });
  }
  const withScratch = probed.filter((item) => item.scratch);
  let chosen = null;
  if (withScratch.length === 1) chosen = withScratch[0];
  else if (withScratch.length > 1) {
    const url = withScratch.filter((item) => item.urlHit);
    chosen = url.length === 1 ? url[0] : (withScratch.find((item) => item.active) || withScratch[0]);
  } else {
    const urlHits = probed.filter((item) => item.urlHit);
    chosen = urlHits.length === 1 ? urlHits[0]
      : (probed.find((item) => item.active) || probed[0] || null);
  }
  return {
    tab: chosen?.tab || null,
    tab_hint: tabHintFor(chosen, probed),
    scratch_present: withScratch.length > 0,
    status_present: probed.some((item) => item.status_control)
  };
}

async function completeWrite(token, writeId, body) {
  const payload = {
    verified: !!body?.verified,
    note_present: !!body?.note_present,
    error_code: safeCode(body?.error_code),
    live_validated: false,
    production_writes: false,
    stage: body?.stage || null,
    opener_strategy: body?.opener_strategy || null,
    note_label: body?.note_label || null,
    commit_kind: body?.commit_kind || null,
    save_variant: body?.save_variant || null,
    tab_hint: body?.tab_hint || 'missing',
    reopen_attempts: body?.reopen_attempts || 0,
    verify_reason: body?.verify_reason || null,
    bridge_version: body?.bridge_version || BRIDGE_VERSION,
    status_matched: !!body?.status_matched,
    observed_status: body?.observed_status || null
  };
  const verifiedOk = payload.verified && (payload.note_present || payload.status_matched);
  const local = {
    write_id: writeId,
    status: verifiedOk ? 'VERIFIED' : 'FAILED',
    error_code: payload.error_code,
    stage: payload.stage,
    opener_strategy: payload.opener_strategy,
    note_label: payload.note_label,
    commit_kind: payload.commit_kind,
    save_variant: payload.save_variant,
    tab_hint: payload.tab_hint,
    reopen_attempts: payload.reopen_attempts,
    verify_reason: payload.verify_reason,
    bridge_version: payload.bridge_version,
    allow_whole_form_save: !!body?.allow_whole_form_save,
    completed_at: new Date().toISOString()
  };
  try {
    const receipt = await request('/v1/portable/writes/' + writeId + '/complete', {
      method: 'POST',
      token,
      body: payload
    });
    await save({ last_write: { ...local, status: receipt?.status || local.status,
      error_code: safeCode(receipt?.error_code) || local.error_code } });
  } catch (error) {
    await save({ last_write: { ...local, status: 'FAILED',
      error_code: safeCode(error.code) || 'NOTE_COMPLETE_FAILED',
      stage: local.stage || 'complete' } });
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
    await armWritePolls();
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
  armWritePolls();
});

chrome.runtime.onStartup.addListener(() => {
  ensureOpenAscendTabs({ allowReload: false });
  armWritePolls();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM) harvestOnce();
  if (alarm.name === WRITE_ALARM || alarm.name === WRITE_SOON) pollWrites();
});

if (chrome.tabs?.onUpdated) {
  chrome.tabs.onUpdated.addListener((_tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && ascendTabUrl(tab?.url)) pollWrites();
  });
}
if (chrome.tabs?.onActivated) {
  chrome.tabs.onActivated.addListener(() => { pollWrites(); });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const actions = {
    STATUS: publicStatus,
    SIGN_IN: signInPlaceholder,
    SIGN_OUT: signOut,
    CREATE_LEASE: createLease,
    REVOKE: revokeLease,
    START: () => setHarvest(true),
    STOP: () => setHarvest(false),
    POLL_WRITES: pollWrites,
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
