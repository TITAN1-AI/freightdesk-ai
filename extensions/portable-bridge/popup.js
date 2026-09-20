'use strict';
const banner = document.getElementById('banner');
const leaseEl = document.getElementById('lease');
const harvestEl = document.getElementById('harvest');
const lastEl = document.getElementById('last');
const lastWriteEl = document.getElementById('last-write');
const apiEl = document.getElementById('api');

function paint(view) {
  const code = view.code || (view.signed_in ? 'LEASE_READY' : 'NOT_SIGNED_IN');
  const attachFailed = view.last_error?.code === 'CONTENT_UNAVAILABLE';
  const write = view.last_write;
  const writeFailed = write && write.status === 'FAILED' && write.error_code;
  const message = writeFailed
    ? writeBanner(write)
    : (view.message || view.last_error?.message || defaultMessage(code, view));
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
  lastWriteEl.textContent = write
    ? ([write.status, write.error_code || 'ok', write.stage, write.opener_strategy, write.commit_kind]
      .filter(Boolean).join(' · ') + ' · not LIVE_VALIDATED')
    : 'none';
  if (view.api_base) apiEl.value = view.api_base;
}

function writeBanner(write) {
  const code = write.error_code || 'NOTE_WRITE_FAILED';
  return ({
    LOAD_OPENER_UNVERIFIED: 'Could not open the load workspace (no unique row, searchbox, or already-open Private Load Note). Harvest Active Loads is not required.',
    LOAD_IDENTITY_UNVERIFIED: 'A private note control is visible, but this tab is not proven as the requested load.',
    LOAD_DETAIL_UNVERIFIED: 'Opened a load control, but the load workspace did not settle.',
    NOTE_COMMIT_REQUIRES_OWNER_PATH: 'Private Load Note (#scratch) needs a whole-form Save approval (allow_whole_form_save). Without it, Bridge will not click Save / Save & Exit.',
    NOTE_SAVE_CONTROL_UNVERIFIED: 'No note-specific Add/Save Note control was found. Bridge will not click Save Load.',
    ASCEND_TAB_MISSING: 'Open an authenticated Ascend tab, then retry the note write.',
    PRIVATE_NOTE_NOT_FOUND: 'Private Load Note / Private Notes was not found on the load workspace.',
    CONTENT_UNAVAILABLE: 'Reload the Ascend tab (F5) so the Bridge can attach, then retry the note write.'
  })[code] || ('Private note write failed (' + code + '). Receipt is FAILED, not success.');
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
  const status = action === 'STATUS' ? result : await chrome.runtime.sendMessage({ action: 'STATUS' });
  paint(status);
  return status;
}

document.getElementById('save-api').onclick = () => send('SET_API', { api_base: apiEl.value.trim() });
document.getElementById('sign-in').onclick = () => send('SIGN_IN');
document.getElementById('sign-out').onclick = () => send('SIGN_OUT');
document.getElementById('create').onclick = () => send('CREATE_LEASE');
document.getElementById('start').onclick = () => send('START');
document.getElementById('stop').onclick = () => send('STOP');
document.getElementById('revoke').onclick = () => send('REVOKE');
send('STATUS');
