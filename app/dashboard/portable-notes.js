/* Demo approval mint for ASCEND_ADD_INTERNAL_NOTE. Never renders note text. */
(() => {
  const form = document.querySelector('#note-approval-form');
  const status = document.querySelector('#note-approval-status');
  if (!form || !status) return;
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const loadId = String(document.querySelector('#note-load-id')?.value || '').trim();
    const allowWholeFormSave = !!document.querySelector('#note-allow-whole-form-save')?.checked;
    status.textContent = 'Minting demo approval…';
    try {
      const response = await fetch('/v1/ascend/approvals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-FreightDesk-Local': '1' },
        body: JSON.stringify({
          action: 'ASCEND_ADD_INTERNAL_NOTE',
          load_id: loadId,
          allow_whole_form_save: allowWholeFormSave
        })
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : (data.error_code || 'approval_mint_failed');
        status.textContent = 'Approval mint failed: ' + detail + ' · not LIVE_VALIDATED';
        return;
      }
      status.textContent = 'Demo approval minted for load ' + data.load_id +
        '. One-use token expires ' + data.expires_at +
        '. Copy approval_token from the agent mint or this one-time value: ' +
        data.approval_token +
        (data.allow_whole_form_save
          ? ' · allow_whole_form_save · commits via Save / Save & Exit on #scratch'
          : '') +
        ' · CANDIDATE · not LIVE_VALIDATED';
    } catch {
      status.textContent = 'Approval mint unavailable · not LIVE_VALIDATED';
    }
  });
})();
