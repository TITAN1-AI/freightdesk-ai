/* Candidate metadata adapter. Called only inside the existing mapping capture boundary. */
(() => {
  'use strict';
  const HEADERS = ['Stop Order', 'Action(s)', 'Scheduled Date/Time', 'Actual Date/Time',
    'Location', 'Address', 'Private Notes', 'Cargo', 'Reference #', 'Show on', 'Reorder'];
  const fail = code => { throw Error(code); };
  function bounded(items, max, code) {
    if (items.length > max) fail(code);
    return Array.from(items);
  }
  function visible(element) {
    for (let e = element; e; e = e.parentElement) {
      const s = e.ownerDocument.defaultView.getComputedStyle(e);
      if (e.hidden || s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return false;
    }
    const r = element.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  // Header text only, never aggregate row/cell/control text or operational values.
  function headerText(th) {
    const children = bounded(th.childNodes, 8, 'STOPS_HEADER_INVALID');
    if (children.some(n => n.nodeType !== 3)) fail('STOPS_HEADER_INVALID');
    const value = children.map(n => n.data).join('').trim();
    if (!HEADERS.includes(value)) fail('STOPS_HEADER_INVALID');
    return value;
  }
  function inspect(root, check) {
    check();
    const tables = bounded(root.querySelectorAll('table'), 8, 'STOPS_TABLE_BOUND')
      .filter(t => t.matches('.table-hover.table-striped.table-condensed.table-bordered') && visible(t));
    if (tables.length !== 1) fail('STOPS_TABLE_AMBIGUOUS');
    const table = tables[0];
    if (!table.tHead || table.tHead.rows.length !== 1 || table.tBodies.length !== 1) fail('STOPS_HEADER_INVALID');
    const cells = bounded(table.tHead.rows[0].cells, 11, 'STOPS_HEADER_INVALID');
    if (cells.length !== 11 || cells.some(c => c.tagName !== 'TH' || c.colSpan !== 1 || c.rowSpan !== 1 || !visible(c))) fail('STOPS_HEADER_INVALID');
    const headers = cells.map(headerText);
    if (new Set(headers).size !== 11) fail('STOPS_HEADER_DUPLICATE');
    const column = name => headers.indexOf(name);
    const rows = [], bindings = [table, ...cells];
    let auxiliary = 0;
    for (const tr of bounded(table.tBodies[0].rows, 20, 'STOPS_ROW_BOUND')) {
      check(); bindings.push(tr);
      const td = bounded(tr.cells, 11, 'STOPS_ROW_INVALID');
      if (!visible(tr)) fail('STOPS_ROW_HIDDEN');
      if (td.length === 1 && td[0].children.length === 1 && td[0].firstElementChild.matches('details') &&
          td[0].firstElementChild.querySelector(':scope > summary')) { auxiliary++; continue; }
      if (td.length !== 11 || td.some(c => c.colSpan !== 1 || c.rowSpan !== 1)) fail('STOPS_ROW_INVALID');
      const action = td[column('Action(s)')];
      const pickup = !!action.querySelector('span.label-success .fa-arrow-up');
      const delivery = !!action.querySelector('span.label-danger .fa-arrow-down');
      if (pickup === delivery) fail('STOPS_ACTION_AMBIGUOUS');
      const kind = pickup ? 'pickup' : 'delivery';
      const controls = bounded(tr.querySelectorAll('a,button,input,select,textarea,[role="button"]'), 20, 'STOPS_CONTROL_BOUND');
      if (controls.some(c => c.closest('tr') !== tr)) fail('STOPS_CONTAINMENT_INVALID');
      const actual = td[column('Actual Date/Time')];
      const surfaces = bounded(tr.querySelectorAll('.pickup-arrival,.pickup-departure,.delivery-arrival,.delivery-departure'), 4, 'STOPS_ACTUAL_AMBIGUOUS');
      const metadata = {};
      for (const phase of ['arrival', 'departure']) {
        const matches = surfaces.filter(e => e.matches('.editable-cell.' + kind + '-' + phase));
        if (matches.length !== 1 || !actual.contains(matches[0]) || matches[0].closest('tr') !== tr) fail('STOPS_CONTAINMENT_INVALID');
        metadata[phase] = {present: true, evidence: 'PROVIDER_CLASS', value_semantics: 'CANDIDATE_ONLY'};
      }
      if (surfaces.length !== 2 || surfaces.some(e => !actual.contains(e))) fail('STOPS_ACTUAL_AMBIGUOUS');
      bindings.push(...td, ...controls, ...surfaces);
      rows.push({capture_row_ref: rows.length, provider_row_key: null, action: kind.toUpperCase(),
        control_count: controls.length, scheduled: {surface_present: !!td[column('Scheduled Date/Time')].querySelector('a'), subtype: 'UNKNOWN'}, actual: metadata});
    }
    return {metadata: {headers, rows, auxiliary_row_count: auxiliary, coverage: 'CURRENT_RENDERED_TABLE_ONLY'}, bindings};
  }
  async function capture(doc, command, guard) {
    if (typeof guard !== 'function') fail('STOPS_AUTHORITY_REQUIRED');
    if (command.operation !== 'ASCEND_MAP_WORKSPACE' || !/^\d{1,20}$/.test(command.capture_load_id || '') || command.capture_section !== 'Edit Stops') fail('STOPS_SCOPE_DENIED');
    const started = performance.now();
    const check = () => {
      guard();
      if (performance.now() - started > 3000) fail('READ_TIMEOUT');
      if (doc.visibilityState !== 'visible' || !doc.hasFocus()) fail('MAPPING_OWNER_NOT_PRESENT');
    };
    const proof = () => {
      check();
      const workspace = FreightDeskWorkspace.observeWorkspace(doc, [command.capture_load_id], Date.now()/1000, check);
      const section = FreightDeskWorkspace.observeSection(workspace);
      if (workspace.contract.load_id !== command.capture_load_id || section.name !== 'Edit Stops') fail('STOPS_SCOPE_DENIED');
      if (!['SELECTED_CONTROL', 'SELECTED_ROUTE_AND_VISIBLE_HEADING'].includes(section.signal)) fail('WORKSPACE_SECTION_UNVERIFIED');
      return {workspace, section};
    };
    const before = proof(), first = inspect(before.section.root, check);
    await new Promise(resolve => setTimeout(resolve, 0));
    const after = proof(), second = inspect(after.section.root, check);
    if (before.workspace.shell !== after.workspace.shell || before.section.root !== after.section.root ||
        first.bindings.length !== second.bindings.length || first.bindings.some((e,i) => e !== second.bindings[i]) ||
        JSON.stringify(first.metadata) !== JSON.stringify(second.metadata)) fail('WORKSPACE_CHANGED');
    check();
    return {schema_version: 1, provider: 'AscendTMS', load_id: command.capture_load_id,
      activation: 'CANDIDATE_ONLY', values_included: false, writes_allowed: false,
      revalidated_after_capture: true, ...first.metadata};
  }
  globalThis.FreightDeskStopsMetadata = Object.freeze({capture,inspect});
})();
