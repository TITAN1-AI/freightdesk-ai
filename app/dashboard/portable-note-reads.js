/* Demo ALLOW capture for ASCEND_READ_LOAD_NOTES. Never renders note text. */
(() => {
  const form = document.querySelector('#note-capture-form');
  const status = document.querySelector('#note-capture-status');
  if (!form || !status) return;
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const loadId = String(document.querySelector('#note-capture-load-id')?.value || '').trim();
    status.textContent = 'Queueing note read-back…';
    try {
      const response = await fetch('/v1/ascend/loads/' + encodeURIComponent(loadId) + '/notes/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-FreightDesk-Local': '1' }
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : (data.error_code || 'note_capture_failed');
        status.textContent = 'Note capture failed: ' + detail + ' · not LIVE_VALIDATED';
        return;
      }
      status.textContent = 'Note capture ' + data.status + ' for load ' + data.load_id +
        ' · write_id ' + data.write_id +
        ' · READ_ONLY · Bridge claims then reads #scratch and #notes · CANDIDATE · not LIVE_VALIDATED';
    } catch {
      status.textContent = 'Note capture unavailable · not LIVE_VALIDATED';
    }
  });
})();
