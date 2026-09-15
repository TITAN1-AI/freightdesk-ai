(() => {
  'use strict';
  const ORIGIN = 'https://ascendtms.com';
  const MAX_ROWS = 100;
  const MAX_TABLES = 30;
  const STATUSES = ['Active', 'Available', 'Assigned', 'Booked', 'Dispatched', 'In Transit', 'Delivered', 'Completed'];
  const HEADERS = ['Load ID', 'Load Status', 'Last Contact/Tracking', 'Customer', 'Picks', 'Pick Date', 'Drops', 'Drop Date',
    'Users & Roles', 'Carrier', 'Driver', 'Equipment', 'Power Unit', 'Trailer', 'Distance', 'Weight', 'Income', 'Expenses',
    'Gross Profit/Loss', null, 'Reference', 'Truck Status', 'Branch', null, 'Smart Capacity', 'TruckSmarter', 'Asset Group',
    'Container', 'Last Free Day', 'Created', 'Load Posting Notes', 'Public Load Notes', 'Temperature'];
  const visible = (el) => !!el?.getClientRects().length && getComputedStyle(el).visibility !== 'hidden' &&
    !el.closest('[hidden],[aria-hidden="true"]');
  const norm = (value) => (value || '').replace(/\s+/g, ' ').trim();
  const loadId = (value) => /^[0-9]{1,20}$/.test(value) ? value : null;
  const boardDate = (value) => value.match(/^\d{2}\/\d{2}\/\d{4}(?=$|\s)/)?.[0] || null;
  const statusOf = (value) => STATUSES.includes(value) ? value : 'UNKNOWN';
  const key = (value) => norm(value).toLowerCase();
  const hex = (buffer) => [...new Uint8Array(buffer)].map((n) => n.toString(16).padStart(2, '0')).join('');

  function fail(code) {
    const error = new Error(code);
    error.code = code;
    throw error;
  }

  async function capture(doc, origin) {
    if (origin !== ORIGIN || doc.location.origin !== ORIGIN) fail('ORIGIN_NOT_ALLOWLISTED');
    const view = globalThis.FreightDeskPortableBoardView.observe(doc).diagnostic;
    if (view.confidence !== 'VERIFIED') fail('ACTIVE_VIEW_UNVERIFIED');
    if (view.view !== 'ACTIVE_LOADS') fail('ACTIVE_VIEW_NOT_ACTIVE_LOADS');
    const known = HEADERS.filter(Boolean);
    const tables = [...doc.querySelectorAll('table,[role="grid"]')];
    if (tables.length > MAX_TABLES) fail('BOARD_SCHEMA_INVALID');
    const eligible = [];
    for (const table of tables.slice(0, MAX_TABLES)) {
      if (!visible(table)) continue;
      const headers = [...table.querySelectorAll('thead th,[role="columnheader"]')]
        .filter((header) => header.closest('table,[role="grid"]') === table);
      if (headers.length !== 33) continue;
      const names = headers.map((header) => known.find((label) => key(label) === key(header.textContent)) ||
        (norm(header.textContent) ? 'UNKNOWN_LABEL' : 'EMPTY_LABEL'));
      const positions = Object.fromEntries(known.map((label) => [label, names.flatMap((name, index) => name === label ? [index] : [])]));
      const indexes = Object.fromEntries(known.map((label) => [label, positions[label].length === 1 ? positions[label][0] : null]));
      if (!['Load ID', 'Load Status', 'Pick Date', 'Drop Date'].every((label) => positions[label].length === 1)) continue;
      const rows = [...table.querySelectorAll('tbody > tr,[role="row"]')]
        .filter((row) => visible(row) && row.closest('table,[role="grid"]') === table);
      const data = rows.map((row) => ({
        cells: [...row.children].filter((cell) => cell.matches('td,[role="cell"],[role="gridcell"]')),
        indexes
      })).filter((entry) => entry.cells.length);
      const emptyMarker = data.length === 1 && data[0].cells.length === 1 &&
        data[0].cells[0].classList.contains('dataTables_empty');
      if (!emptyMarker && data.length) eligible.push({ data, indexes });
    }
    if (eligible.length !== 1) fail(eligible.length ? 'BOARD_SCHEMA_INVALID' : 'NO_VISIBLE_GRID');
    const selected = eligible[0];
    if (selected.data.length > MAX_ROWS) fail('ROW_COUNT_BOUND');
    const rows = selected.data.map(({ cells, indexes }) => {
      const number = loadId(norm(cells[indexes['Load ID']].textContent));
      if (!number) fail('ROW_IDENTITY_INVALID');
      return {
        load_id: number,
        pick_date: boardDate(norm(cells[indexes['Pick Date']].textContent)),
        drop_date: boardDate(norm(cells[indexes['Drop Date']].textContent)),
        load_status: statusOf(norm(cells[indexes['Load Status']].textContent))
      };
    });
    if (new Set(rows.map((row) => row.load_id)).size !== rows.length) fail('DUPLICATE_LOAD_ID');
    const facts = rows.map((row) => ({
      drop_date: row.drop_date,
      load_id: row.load_id,
      pick_date: row.pick_date
    })).sort((a, b) => Number(a.load_id) - Number(b.load_id));
    const revision = hex(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(facts))));
    return {
      origin: ORIGIN,
      view: 'ACTIVE_LOADS',
      view_confidence: 'VERIFIED',
      coverage: 'VISIBLE_BOARD_ONLY',
      evidence_class: 'CANDIDATE',
      live_validated: false,
      values_included: false,
      production_writes: false,
      revision,
      captured_at: new Date().toISOString(),
      row_count: rows.length,
      rows
    };
  }

  globalThis.FreightDeskPortableHarvest = Object.freeze({ capture, origin: ORIGIN });
})();
