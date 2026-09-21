/* Demo approval mint for ASCEND_CHANGE_LOAD_STATUS. Never executes Ascend. */
(() => {
  const form = document.querySelector('#status-approval-form');
  const status = document.querySelector('#status-approval-status');
  if (!form || !status) return;
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const loadId = String(document.querySelector('#status-load-id')?.value || '').trim();
    const requested = String(document.querySelector('#status-value')?.value || '').trim();
    const allowWholeFormSave = !!document.querySelector('#status-allow-whole-form-save')?.checked;
    status.textContent = 'Minting demo status approval…';
    try {
      const response = await fetch('/v1/ascend/approvals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-FreightDesk-Local': '1' },
        body: JSON.stringify({
          action: 'ASCEND_CHANGE_LOAD_STATUS',
          load_id: loadId,
          status: requested,
          allow_whole_form_save: allowWholeFormSave
        })
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : (data.error_code || 'approval_mint_failed');
        status.textContent = 'Approval mint failed: ' + detail + ' · not LIVE_VALIDATED';
        return;
      }
      status.textContent = 'Demo status approval minted for load ' + data.load_id +
        (data.requested_status ? (' → ' + data.requested_status) : '') +
        '. One-use token expires ' + data.expires_at +
        '. Copy approval_token from the agent mint or this one-time value: ' +
        data.approval_token +
        (data.allow_whole_form_save
          ? ' · allow_whole_form_save · commits via stay-on-load Save'
          : '') +
        ' · CANDIDATE · not LIVE_VALIDATED';
    } catch {
      status.textContent = 'Approval mint unavailable · not LIVE_VALIDATED';
    }
  });
})();
