/* Mail content is served only through the dedicated owner session. No Graph calls here. */
(() => {
  const root = document.querySelector('#mail-content');
  let generation = 0;
  const line = (parent, value, tag = 'p') => {
    const el = document.createElement(tag); el.textContent = value; parent.append(el); return el;
  };
  async function refresh() {
    const current = ++generation;
    const status = await fetch('/api/mail/status').then(r => r.json());
    if (current !== generation) return;
    document.querySelector('#mail-status').textContent = status.status;
    root.replaceChildren();
    const response = await fetch('/api/mail/summary');
    if (current !== generation) return;
    if (!response.ok) { line(root, 'Mailbox records are protected. Open the owner read view to inspect local records.'); return; }
    const data = await response.json();
    if (current !== generation) return;
    if (data.connection.status === 'MAILBOX_VERIFIED') document.querySelector('#mail-status').textContent = 'Mailbox identity verified · see capability evidence';
    line(root, `${data.messages_discovered} discovered · ${data.messages_processed} processed · ${data.unmatched_messages} unmatched · ${data.classification_failures} classification failures`);
    line(root, `${data.attachment_count} attachments · ${data.drafts_created} unsent drafts · ${data.errors} recorded errors`);
    line(root, `Last completed sync page: ${data.last_successful_sync || 'Never'}`);
    if (!data.recent.length) line(root, 'No mailbox messages imported. Microsoft live validation is pending.');
    for (const row of data.recent) line(root, `${row.time || 'Unknown time'} · ${row.sender_company || 'Unknown sender domain'} · ${row.subject} · ${row.intent} · ${row.matched_load || 'Unmatched'} · ${Math.round(row.confidence * 100)}% · ${row.status} · ${row.action}`);
    const related = document.querySelector('#live-mail-records');
    const detail = await fetch('/api/mail/shipments/live-poc-001');
    if (current !== generation) return;
    related.replaceChildren();
    if (detail.ok) {
      const associated = await detail.json();
      line(related, 'Associated mail and documents', 'h3');
      if (!associated.recent.length) line(related, 'No associated mail evidence. Document gates remain unchanged.');
      for (const row of associated.recent) line(related, `${row.time || ''} · ${row.subject} · ${row.intent} · ${row.status}`);
      for (const doc of associated.documents) line(related, `${doc.kind} candidate · ${doc.verified ? 'Verified' : 'Requires review'} · ${doc.scan_status}`);
    }
  }
  document.querySelector('#mail-refresh').addEventListener('click', () => refresh().catch(() => { root.textContent = 'Local mailbox view unavailable.'; }));
  document.addEventListener('freightdesk-live-ready', () => refresh().catch(() => {}));
  refresh().catch(() => { root.textContent = 'Local mailbox view unavailable.'; });
})();
