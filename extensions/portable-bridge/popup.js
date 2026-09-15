'use strict';
const banner = document.getElementById('banner');
const leaseEl = document.getElementById('lease');
const harvestEl = document.getElementById('harvest');
const lastEl = document.getElementById('last');
const apiEl = document.getElementById('api');

function paint(view) {
  const code = view.code || (view.signed_in ? 'LEASE_READY' : 'NOT_SIGNED_IN');
  const message = view.message || view.last_error?.message || defaultMessage(code, view);
  banner.textContent = message;
  banner.className = 'status ' + (code === 'HARVESTING' || code === 'LEASE_READY' ? 'ok' : 'warn');
  const lease = view.lease;
  leaseEl.textContent = lease
    ? (lease.status + ' · ' + lease.scope + ' · expires ' + lease.expires_at)
    : 'none';
  harvestEl.textContent = view.harvest_enabled ? 'running (CANDIDATE, one-minute poll)' : 'stopped';
  const last = view.last_harvest;
  lastEl.textContent = last
    ? (last.row_count + ' rows · ' + last.revision.slice(0, 12) + '… · not LIVE_VALIDATED')
    : 'none';
  if (view.api_base) apiEl.value = view.api_base;
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
