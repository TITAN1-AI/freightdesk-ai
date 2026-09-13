/* Local protected projection only. Provider values are text, never HTML or browser commands. */
(() => {
  let revision = 0;
  const content = document.querySelector('#ascend-content');
  function line(parent, text, tag = 'p') {
    const node = document.createElement(tag);
    node.textContent = text;
    parent.append(node);
  }
  async function refresh() {
    const current = ++revision;
    try {
      const response = await fetch('/api/ascend/summary');
      if (current !== revision) return;
      content.replaceChildren();
      if (!response.ok) {
        document.querySelector('#ascend-status').textContent = 'Protected local view · owner session required';
        line(content, 'M4B offline foundation is ready. Ascend has not been authenticated or live validated.');
        return;
      }
      const data = await response.json();
      if (current !== revision) return;
      content.replaceChildren();
      const c = data.connection;
      document.querySelector('#ascend-status').textContent = c.status;
      line(content, `Executor: ${c.executor_status} · Last verified account: ${c.last_verified_company ?? 'Unverified'}`);
      line(content, `Last successful read: ${c.last_successful_read ?? 'None'} · Production writes: ${data.production_writes}`);
      for (const load of data.loads) {
        const detail = document.createElement('details');
        line(detail, `Load ${load.load_number} · Ascend provider facts · ${load.observed_at}`, 'summary');
        for (const fact of load.provider_facts) {
          line(detail, `${fact.field}: ${fact.display_value ?? 'Unknown'} · raw: ${fact.raw_display ?? 'Unavailable'} · ${fact.availability} · ${fact.source_section}`);
        }
        line(detail, 'FreightDesk-derived reconciliation — source evidence remains separate', 'h3');
        for (const source of ['canonical', 'CarrierView', 'Outlook', 'Ascend history']) {
          const group = document.createElement('details');
          line(group, `${source} evidence comparison`, 'summary');
          for (const row of load.reconciliation.filter(r => r.comparison_source === source)) {
            line(group, `${row.field}: ${row.status} · observed ${row.comparison_observed_at ?? 'Unavailable'} · evidence ${row.evidence_reference ?? 'None'}`);
          }
          detail.append(group);
        }
        content.append(detail);
      }
      line(content, `Pending Ascend approvals / reconciliation: ${data.pending_approvals.length}`, 'h3');
      for (const action of data.pending_approvals) line(content, `${action.operation} · ${action.state}`);
      line(content, 'Ascend action audit', 'h3');
      for (const event of data.audit) line(content, `${event.timestamp} · ${event.event}`);
    } catch {
      if (current !== revision) return;
      content.replaceChildren();
      line(content, 'Local Ascend evidence is unavailable. No browser operation was attempted.');
    }
  }
  document.querySelector('#ascend-refresh').addEventListener('click', refresh);
  document.addEventListener('freightdesk-live-ready', refresh);
  refresh();
})();
