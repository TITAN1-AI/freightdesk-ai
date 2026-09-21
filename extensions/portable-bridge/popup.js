'use strict';
const banner = document.getElementById('banner');
const leaseEl = document.getElementById('lease');
const harvestEl = document.getElementById('harvest');
const lastEl = document.getElementById('last');
const lastWriteEl = document.getElementById('last-write');
const apiEl = document.getElementById('api');

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

function paint(view) {
  const code = view.code || (view.signed_in ? 'LEASE_READY' : 'NOT_SIGNED_IN');
  const attachFailed = view.last_error?.code === 'CONTENT_UNAVAILABLE';
  const write = view.last_write;
  const writeFailed = write && write.status === 'FAILED' && write.error_code;
  const writeClaiming = write && (write.status === 'DISPATCHED' || write.stage === 'claim_wait' || write.stage === 'claimed');
  const message = writeFailed
    ? writeBanner(write)
    : (writeClaiming ? claimBanner(write) : (view.message || view.last_error?.message || defaultMessage(code, view)));
  banner.textContent = message;
  banner.className = 'status ' + ((code === 'HARVESTING' || code === 'LEASE_READY') && !attachFailed && !writeFailed ? 'ok' : 'warn');
  const lease = view.lease;
  leaseEl.textContent = lease
    ? (lease.status + ' · ' + lease.scope + ' · expires ' + lease.expires_at)
    : 'none';
  harvestEl.textContent = view.harvest_enabled
    ? (attachFailed ? 'running, but reload the Ascend tab first' : 'running (CANDIDATE, one-minute poll)')
    : 'stopped';
  const last = view.last_harvest;
  lastEl.textContent = last
    ? (last.row_count + ' rows · ' + last.revision.slice(0, 12) + '… · not LIVE_VALIDATED')
    : 'none';
  lastWriteEl.textContent = formatLastWrite(write);
  if (view.api_base) apiEl.value = view.api_base;
}

function formatLastWrite(write) {
  if (!write) return 'none';
  const parts = [
    write.status,
    safeCode(write.error_code) || (write.stage === 'claim_wait' || write.stage === 'claimed' ? 'claiming' : 'ok'),
    write.stage,
    write.opener_strategy,
    write.commit_kind,
    write.tab_hint,
    write.reopen_attempts != null ? ('reopen×' + write.reopen_attempts) : null,
    write.verify_reason
  ].filter(Boolean);
  return parts.join(' · ') + ' · not LIVE_VALIDATED';
}

function claimBanner(write) {
  if (write.stage === 'claimed') return 'Bridge claimed the write and is running on the Ascend tab.';
  return 'Waiting to claim a dispatched write. Keep this popup or the Ascend tab focused.';
}

function writeBanner(write) {
  const code = safeCode(write.error_code) || 'NOTE_WRITE_FAILED';
  return ({
    LOAD_OPENER_UNVERIFIED: 'Could not reopen the load after Save & Exit. Reload unpacked 0.1.13 and restart the demo API. Bridge force-reinjects, waits seconds, then unique row / search+Enter /loads/{id}.',
    typed_but_not_saved: 'Private Load Note already has the text, but Save / Save & Exit was not clicked. Reload unpacked 0.1.13 and retry with whole-form approval.',
    LOAD_IDENTITY_UNVERIFIED: 'A private note control is visible, but this tab is not proven as the requested load.',
    LOAD_DETAIL_UNVERIFIED: 'Opened a load control, but the load workspace did not settle.',
    NOTE_COMMIT_REQUIRES_OWNER_PATH: 'Private Load Note (#scratch) needs a whole-form Save approval (allow_whole_form_save). Without it, Bridge will not click Save / Save & Exit.',
    STATUS_COMMIT_REQUIRES_OWNER_PATH: 'Load Status needs a whole-form Save approval (allow_whole_form_save). Without it, Bridge will not change status or click Save.',
    NOTE_SAVE_CONTROL_UNVERIFIED: 'No note-specific Add/Save Note control was found. Bridge will not click Save Load.',
    STATUS_SAVE_CONTROL_UNVERIFIED: 'No stay-on-load Save or unique Save & Exit was found for the status change.',
    STATUS_CONTROL_NOT_FOUND: 'Load Status / Status was not found on Load Basics.',
    STATUS_OPTION_NOT_FOUND: 'The requested status is not an option on the Load Status control.',
    BRIDGE_CLAIM_TIMEOUT: 'Bridge did not claim the write in time. Reload unpacked 0.1.13, keep the popup open, and retry.',
    ASCEND_TAB_MISSING: 'Open an authenticated Ascend tab, then retry the write.',
    PRIVATE_NOTE_NOT_FOUND: 'Private Load Note / Private Notes was not found on the load workspace.',
    NOTE_CONTROLS_NOT_FOUND: 'Private #scratch and public #notes were not found. Sit on Load Basics and retry capture.',
    CONTENT_UNAVAILABLE: 'Reload the Ascend tab (F5) so the Bridge can attach, then retry the write.'
  })[code] || ('Write failed (' + code + '). Receipt is FAILED, not success.');
}

function defaultMessage(code, view) {
  if (code === 'NOT_SIGNED_IN') return 'Not signed in. Demo sign-in issues a placeholder device session.';
  if (code === 'LEASE_MISSING') return 'Signed in, but no harvest lease is active.';
  if (code === 'HARVESTING') return 'Harvest running. Snapshots stay CANDIDATE evidence.';
  if (code === 'LEASE_READY') return 'Lease ready. Start harvest on the Ascend Active Loads tab.';
  if (view.last_error?.message) return view.last_error.message;
  return 'FreightDesk Bridge';
}

async function send(action, extra) {
  const result = await chrome.runtime.sendMessage({ action, ...extra });
  if (result?.error) {
    paint({ ...result, code: result.code, message: result.message, signed_in: false });
    const status = await chrome.runtime.sendMessage({ action: 'STATUS' });
    paint({ ...status, message: result.message, code: result.code });
    return result;
  }
  const status = action === 'STATUS' || action === 'POLL_WRITES'
    ? (action === 'STATUS' ? result : await chrome.runtime.sendMessage({ action: 'STATUS' }))
    : await chrome.runtime.sendMessage({ action: 'STATUS' });
  paint(status);
  return status;
}

async function refreshWrites() {
  await chrome.runtime.sendMessage({ action: 'POLL_WRITES' });
  return send('STATUS');
}

document.getElementById('save-api').onclick = () => send('SET_API', { api_base: apiEl.value.trim() });
document.getElementById('sign-in').onclick = () => send('SIGN_IN');
document.getElementById('sign-out').onclick = () => send('SIGN_OUT');
document.getElementById('create').onclick = () => send('CREATE_LEASE');
document.getElementById('start').onclick = () => send('START');
document.getElementById('stop').onclick = () => send('STOP');
document.getElementById('revoke').onclick = () => send('REVOKE');
send('STATUS').then(refreshWrites);
setInterval(refreshWrites, 4000);
