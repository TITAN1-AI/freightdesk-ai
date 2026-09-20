(() => {
  'use strict';
  const ORIGIN = 'https://ascendtms.com';
  const ACTION = 'ADD_INTERNAL_NOTE';
  const PRIVATE_LABELS = Object.freeze([
    'private notes', 'internal notes', 'private load note', 'private load notes',
    'internal load note', 'internal load notes'
  ]);
  const PUBLIC_LABELS = Object.freeze([
    'notes', 'load posting notes', 'public load notes', 'public load note', 'public notes'
  ]);
  const NOTE_COMMIT = Object.freeze([
    'add note', 'save note', 'add internal note', 'save internal note',
    'add private note', 'save private note', 'add private load note', 'save private load note'
  ]);
  const FORBIDDEN_COMMIT = Object.freeze([
    'save load', 'save', 'submit', 'book it', 'new load', 'create load', 'assign', 'assign carrier',
    'update status', 'change status', 'rates', 'upload', 'send', 'delete', 'cancel load'
  ]);
  const FORBIDDEN_ACTIONS = Object.freeze([
    'ASCEND_SAVE', 'ASCEND_SAVE_LOAD', 'ASCEND_SET_DRIVER', 'ASCEND_ASSIGN', 'ASCEND_UPDATE_STATUS',
    'ASCEND_UPDATE_RATES', 'ASCEND_NEW_LOAD', 'ASCEND_UPLOAD', 'ASCEND_SEND', 'ADD_PUBLIC_NOTE'
  ]);
  const OPEN_NAMES = Object.freeze(['view', 'details', 'open']);
  const IDENTITY_LABELS = Object.freeze(['load number', 'load id', 'load #', 'load no', 'load no.']);
  const PRIVATE_NOTE_ID = 'scratch';
  const PUBLIC_NOTE_ID = 'notes';

  function fail(code) {
    const error = new Error(code);
    error.code = code;
    throw error;
  }

  function norm(value) {
    return String(value || '').replace(/\s+/g, ' ').trim().toLowerCase().replace(/[:*]+$/, '');
  }

  function visible(el) {
    return !!el?.getClientRects?.().length && getComputedStyle(el).visibility !== 'hidden' &&
      !el.closest?.('[hidden],[aria-hidden="true"]');
  }

  function controlLabel(el) {
    const labeled = el.labels && el.labels.length === 1 ? el.labels[0].textContent : '';
    return norm(el.getAttribute('aria-label') || labeled || el.getAttribute('title') ||
      el.placeholder || el.value || el.textContent);
  }

  function isPrivateNoteLabel(label) {
    return PRIVATE_LABELS.includes(norm(label));
  }

  function isPublicNoteLabel(label) {
    const key = norm(label);
    return PUBLIC_LABELS.includes(key) && !isPrivateNoteLabel(key);
  }

  function isPublicNoteControl(item) {
    if (String(item?.id || '') === PUBLIC_NOTE_ID) return true;
    return isPublicNoteLabel(item?.label);
  }

  function isPrivateNoteControl(item) {
    if (isPublicNoteControl(item)) return false;
    if (String(item?.id || '') === PRIVATE_NOTE_ID) return true;
    return isPrivateNoteLabel(item?.label);
  }

  function classifyWholeFormSave(label) {
    const key = norm(label).replace(/[.\u2026]+$/, '');
    if (isNoteCommitLabel(key)) return null;
    if (/^save\s*(&|and)\s*exit\b/.test(key)) return 'SAVE_AND_EXIT';
    if (key === 'save' || key === 'save load') return 'SAVE_STAY';
    if (/^save\b/.test(key) && !/\bexit\b/.test(key) && !/\bnote\b/.test(key)) return 'SAVE_STAY';
    return null;
  }

  function isNoteCommitLabel(label) {
    return NOTE_COMMIT.includes(norm(label));
  }

  function isOwnerPathCommit(label) {
    const key = norm(label);
    if (isNoteCommitLabel(key)) return false;
    if (classifyWholeFormSave(key) === 'SAVE_STAY' || classifyWholeFormSave(key) === 'SAVE_AND_EXIT') return true;
    return false;
  }

  function isForbiddenCommitLabel(label) {
    const key = norm(label);
    if (isNoteCommitLabel(key)) return false;
    if (isOwnerPathCommit(key)) return true;
    return FORBIDDEN_COMMIT.includes(key) || /\b(assign|book it|new load|upload|send|rate|status)\b/.test(key);
  }

  function isLoadIdentityLabel(label) {
    return IDENTITY_LABELS.includes(norm(label));
  }

  function report(partial) {
    return {
      ok: false,
      verified: false,
      note_present: false,
      error_code: null,
      live_validated: false,
      production_writes: false,
      stage: null,
      opener_strategy: null,
      note_label: null,
      commit_kind: null,
      save_variant: null,
      allow_whole_form_save: false,
      tab_hint: null,
      reopen_attempts: 0,
      verify_reason: null,
      bridge_version: '0.1.12',
      ...partial
    };
  }

  function pickStaySave(stay) {
    if (!stay.length) return null;
    if (stay.length === 1) return stay[0];
    const save = stay.filter((item) => norm(item.label) === 'save');
    if (save.length) return save[0];
    const saveLoad = stay.filter((item) => norm(item.label) === 'save load');
    if (saveLoad.length) return saveLoad[0];
    return stay[0];
  }

  function planCommit(scan, options) {
    const allow = !!(options && options.allow_whole_form_save);
    const controls = commitControls(scan);
    const commits = controls.filter((item) => item.visible && isNoteCommitLabel(item.label));
    const stayAll = controls.filter((item) => classifyWholeFormSave(item.label) === 'SAVE_STAY');
    const stayVisible = stayAll.filter((item) => item.visible);
    const stay = stayVisible.length ? stayVisible : stayAll;
    const exit = controls.filter((item) => item.visible && classifyWholeFormSave(item.label) === 'SAVE_AND_EXIT');
    const forbidden = controls.filter((item) => item.visible && isForbiddenCommitLabel(item.label));
    if (commits.length === 1) {
      return { ok: true, commit: commits[0], commit_kind: 'NOTE_SPECIFIC', save_variant: 'NOTE_SPECIFIC',
        forbidden_visible: forbidden.length };
    }
    if (commits.length > 1) {
      return { ok: false, code: 'NOTE_SAVE_CONTROL_UNVERIFIED', commit_kind: 'AMBIGUOUS',
        forbidden_visible: forbidden.length };
    }
    const stayChosen = pickStaySave(stay);
    if (stayChosen) {
      if (!allow) {
        return {
          ok: false,
          code: 'NOTE_COMMIT_REQUIRES_OWNER_PATH',
          commit_kind: 'WHOLE_FORM_SAVE',
          save_variant: 'SAVE_STAY',
          owner_path_label: stayChosen.label,
          forbidden_visible: forbidden.length
        };
      }
      return {
        ok: true,
        commit: stayChosen,
        commit_kind: 'WHOLE_FORM_SAVE',
        save_variant: 'SAVE_STAY',
        forbidden_visible: forbidden.length
      };
    }
    if (exit.length > 1) {
      return { ok: false, code: 'NOTE_SAVE_CONTROL_UNVERIFIED', commit_kind: 'AMBIGUOUS',
        forbidden_visible: forbidden.length };
    }
    const chosen = exit.length === 1 ? exit[0] : null;
    if (chosen) {
      if (!allow) {
        return {
          ok: false,
          code: 'NOTE_COMMIT_REQUIRES_OWNER_PATH',
          commit_kind: 'WHOLE_FORM_SAVE',
          save_variant: 'SAVE_AND_EXIT',
          owner_path_label: chosen.label,
          forbidden_visible: forbidden.length
        };
      }
      return {
        ok: true,
        commit: chosen,
        commit_kind: 'WHOLE_FORM_SAVE',
        save_variant: 'SAVE_AND_EXIT',
        forbidden_visible: forbidden.length
      };
    }
    return { ok: false, code: 'NOTE_SAVE_CONTROL_UNVERIFIED', commit_kind: 'MISSING',
      forbidden_visible: forbidden.length };
  }

  function commitControls(scan) {
    const seen = new Set();
    const out = [];
    for (const item of [...(scan.buttons || []), ...(scan.links || [])]) {
      const key = item.el || item.label || item;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(item);
    }
    return out;
  }

  function inspect(scan, command) {
    if (!command || FORBIDDEN_ACTIONS.includes(command.action) || command.action !== ACTION) {
      return { ok: false, code: 'WRITE_ACTION_FORBIDDEN' };
    }
    if (command.note_kind && command.note_kind !== 'PRIVATE_INTERNAL') {
      return { ok: false, code: 'NOTE_KIND_FORBIDDEN' };
    }
    if (command.change_status || command.assign || command.rates || command.new_load || command.send) {
      return { ok: false, code: 'WRITE_ACTION_FORBIDDEN' };
    }
    const privateNotes = (scan.textareas || []).filter((item) => item.visible && isPrivateNoteControl(item));
    const publicNotes = (scan.textareas || []).filter((item) => item.visible && isPublicNoteControl(item));
    if (publicNotes.length && !privateNotes.length) {
      return { ok: false, code: 'PUBLIC_NOTE_BLOCKED' };
    }
    if (privateNotes.length !== 1) {
      return { ok: false, code: privateNotes.length ? 'PRIVATE_NOTE_AMBIGUOUS' : 'PRIVATE_NOTE_NOT_FOUND' };
    }
    const commit = planCommit(scan, command);
    if (!commit.ok) {
      return {
        ok: false,
        code: commit.code,
        commit_kind: commit.commit_kind,
        save_variant: commit.save_variant || null,
        note_label: privateNotes[0].label || privateNotes[0].id,
        forbidden_visible: commit.forbidden_visible
      };
    }
    return {
      ok: true,
      target: privateNotes[0],
      commit: commit.commit,
      commit_kind: commit.commit_kind,
      save_variant: commit.save_variant || null,
      note_label: privateNotes[0].label || privateNotes[0].id
    };
  }

  function mapControl(el) {
    return {
      el,
      id: String(el.id || el.getAttribute?.('id') || ''),
      label: controlLabel(el),
      visible: visible(el),
      value: el.value || el.textContent || '',
      text: norm(el.textContent),
      tag: String(el.tagName || '').toLowerCase(),
      role: el.getAttribute?.('role') || '',
      href: el.getAttribute?.('href') || ''
    };
  }

  function frameDocuments(doc) {
    const out = [];
    const seen = [];
    const walk = (root) => {
      if (!root || seen.indexOf(root) >= 0) return;
      seen.push(root);
      out.push(root);
      let frames = [];
      try { frames = [...root.querySelectorAll('iframe,frame')]; } catch { frames = []; }
      for (const frame of frames) {
        try { walk(frame.contentDocument); } catch { /* cross-origin */ }
      }
    };
    walk(doc);
    return out;
  }

  function collect(root, selector) {
    try { return [...root.querySelectorAll(selector)]; } catch { return []; }
  }

  function findScratch(doc) {
    for (const root of frameDocuments(doc)) {
      let el = null;
      try { el = root.getElementById ? root.getElementById(PRIVATE_NOTE_ID) : null; } catch { el = null; }
      if (el) {
        const item = mapControl(el);
        item.visible = true;
        return item;
      }
      const notes = collect(root, 'textarea,[role="textbox"]').map(mapControl)
        .filter((item) => isPrivateNoteControl(item));
      if (notes.length === 1) {
        notes[0].visible = true;
        return notes[0];
      }
    }
    return null;
  }

  function probeWorkspace(doc, loadId, expectedText) {
    const scratch = findScratch(doc);
    const workspace = planWorkspace(scan(doc), loadId);
    const value = scratch ? String(scratch.value || scratch.el?.value || '') : '';
    return {
      scratch: !!scratch,
      already_open: !!(scratch || workspace.ready),
      note_label: (scratch && (scratch.label || scratch.id)) || workspace.note_label || null,
      note_present: !!(expectedText && value.includes(String(expectedText)))
    };
  }

  function scan(doc) {
    const docs = frameDocuments(doc);
    const textareas = [];
    const buttons = [];
    const headings = [];
    const inputs = [];
    const labeled = [];
    const searchboxes = [];
    const rows = [];
    const links = [];
    for (const root of docs) {
      textareas.push(...collect(root, 'textarea,[role="textbox"]').map(mapControl));
      buttons.push(...collect(root, 'button,input[type="submit"],input[type="button"],[role="button"]').map(mapControl));
      headings.push(...collect(root, 'h1,h2,h3,[role="heading"]').map((el) => ({
        el, text: norm(el.textContent), visible: visible(el)
      })));
      inputs.push(...collect(root, 'input,select').map(mapControl));
      labeled.push(...collect(root, 'label').map((el) => {
        const forId = el.getAttribute('for');
        const control = (forId && root.getElementById) ? root.getElementById(forId) : el.querySelector?.('input,span,strong');
        return {
          el,
          label: norm(el.textContent),
          visible: visible(el),
          value: control ? String(control.value || control.textContent || '').trim() : ''
        };
      }));
      searchboxes.push(...collect(root, 'input[type="search"],[role="searchbox"]')
        .filter((el) => visible(el) && String(el.tagName || '').toUpperCase() !== 'TEXTAREA')
        .map(mapControl));
      rows.push(...collect(root, 'tbody > tr,[role="row"]').filter(visible).map((row) => ({
        el: row,
        cells: collect(row, 'td,[role="cell"],[role="gridcell"],a,button,[role="link"],[role="button"]')
          .map(mapControl)
      })));
      links.push(...collect(root, 'a,[role="link"]').map(mapControl));
    }
    if (!searchboxes.length) {
      const labeledSearch = inputs.filter((item) => item.visible && /\bsearch\b/.test(item.label) &&
        !/submit|button|hidden/.test(item.role));
      if (labeledSearch.length === 1) searchboxes.push(labeledSearch[0]);
    }
    const scratch = findScratch(doc);
    if (scratch && !textareas.some((item) => item.el === scratch.el || item.id === PRIVATE_NOTE_ID)) {
      textareas.push(scratch);
    }
    return {
      textareas,
      buttons,
      headings,
      inputs,
      labeled,
      searchboxes,
      rows,
      links,
      href: String(doc.defaultView?.location?.href || ''),
      title: norm(doc.title || '')
    };
  }

  function identityProven(scanResult, loadId) {
    const id = String(loadId);
    const heading = (scanResult.headings || []).some((item) => item.visible &&
      (norm(item.text) === id || new RegExp('\\b' + id + '\\b').test(item.text)));
    const input = (scanResult.inputs || []).some((item) => item.visible &&
      String(item.value || '').trim() === id && isLoadIdentityLabel(item.label));
    const labeled = (scanResult.labeled || []).some((item) => item.visible &&
      isLoadIdentityLabel(item.label) && String(item.value || '').trim() === id);
    let urlHas = false;
    try {
      urlHas = String(scanResult.href || '').startsWith(ORIGIN) && String(scanResult.href || '').includes(id);
    } catch {
      urlHas = false;
    }
    const titled = String(scanResult.title || '').includes(id);
    return heading || input || labeled || urlHas || titled;
  }

  function planWorkspace(scanResult, loadId) {
    const notes = (scanResult.textareas || []).filter((item) =>
      (item.visible || String(item.id || '') === PRIVATE_NOTE_ID) && isPrivateNoteControl(item));
    if (notes.length > 1) return { ready: false, code: 'PRIVATE_NOTE_AMBIGUOUS' };
    if (notes.length !== 1) return { ready: false };
    const note = notes[0];
    const noteLabel = note.label || note.id || PRIVATE_NOTE_ID;
    if (String(note.id || '') === PRIVATE_NOTE_ID) {
      return {
        ready: true,
        strategy: 'already_open',
        note,
        note_label: noteLabel,
        identity: identityProven(scanResult, loadId) ? 'proven' : 'scratch_visible'
      };
    }
    if (identityProven(scanResult, loadId)) {
      return { ready: true, strategy: 'already_open', note, note_label: noteLabel };
    }
    const labeledOthers = [...(scanResult.inputs || []), ...(scanResult.labeled || [])].filter((item) => {
      const value = String(item.value || '').trim();
      return item.visible && isLoadIdentityLabel(item.label) && value && value !== String(loadId);
    });
    if (labeledOthers.length) {
      return { ready: false, code: 'LOAD_IDENTITY_UNVERIFIED', note_label: noteLabel };
    }
    return {
      ready: true,
      strategy: 'already_open',
      note,
      note_label: noteLabel,
      identity: 'private_note_workspace'
    };
  }

  function isActivateable(cell) {
    const tag = String(cell.tag || '').toLowerCase();
    const role = String(cell.role || '').toLowerCase();
    return tag === 'a' || tag === 'button' || role === 'link' || role === 'button' || !!cell.href;
  }

  function forbiddenOpenLabel(label) {
    return /\b(save|submit|assign|book|status|rate|send|upload|delete|new load|create)\b/.test(norm(label));
  }

  function planOpener(scanResult, loadId) {
    const id = String(loadId);
    const matches = [];
    let ambiguous = false;
    for (const row of scanResult.rows || []) {
      const identityCells = (row.cells || []).filter((cell) => cell.visible && norm(cell.text) === id);
      if (!identityCells.length) continue;
      const named = (row.cells || []).filter((cell) => {
        const label = norm(cell.label || cell.text);
        return cell.visible && (OPEN_NAMES.includes(label) || label === id) && !forbiddenOpenLabel(label);
      });
      let chosen = null;
      if (named.length === 1) chosen = named[0];
      else if (named.length > 1) {
        const preferred = named.filter((cell) => OPEN_NAMES.includes(norm(cell.label || cell.text)));
        if (preferred.length === 1) chosen = preferred[0];
        else ambiguous = true;
      } else if (identityCells.length === 1 && isActivateable(identityCells[0])) {
        chosen = identityCells[0];
      }
      if (chosen) matches.push(chosen);
    }
    const standalone = [...(scanResult.buttons || []), ...(scanResult.links || [])].filter((item) =>
      item.visible && norm(item.label || item.text) === id && !forbiddenOpenLabel(item.label || item.text));
    if (ambiguous || matches.length > 1) return { error: 'LOAD_OPENER_AMBIGUOUS' };
    if (matches.length === 1) return { strategy: 'unique_row_opener', target: matches[0] };
    if (standalone.length === 1) return { strategy: 'unique_id_control', target: standalone[0] };
    if (standalone.length > 1) return { error: 'LOAD_OPENER_AMBIGUOUS' };
    const boxes = (scanResult.searchboxes || []).filter((item) => item.visible);
    if (boxes.length === 1) return { strategy: 'unique_searchbox', target: boxes[0] };
    return { error: 'LOAD_OPENER_UNVERIFIED' };
  }

  function activate(el) {
    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  }

  function fillNoSubmit(el, text) {
    if (!el) fail('LOAD_OPENER_UNVERIFIED');
    if (typeof el.focus === 'function') el.focus();
    el.value = String(text);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function pressEnter(el) {
    if (!el) return;
    const Ctor = globalThis.KeyboardEvent || globalThis.Event;
    const opts = { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true };
    el.dispatchEvent(new Ctor('keydown', opts));
    el.dispatchEvent(new Ctor('keypress', opts));
    el.dispatchEvent(new Ctor('keyup', opts));
  }

  function knownLoadHref(loadId) {
    const id = String(loadId || '');
    if (!/^\d{1,20}$/.test(id)) return null;
    return ORIGIN + '/loads/' + id;
  }

  function looksLikeBoard(scanResult) {
    const heading = (scanResult.headings || []).some((item) =>
      /\b(active loads|all loads|load board)\b/.test(norm(item.text)));
    const search = (scanResult.searchboxes || []).some((item) => item.visible);
    return heading || search;
  }

  async function waitForBoard(doc, loadId, attempts) {
    const limit = attempts == null ? 8 : attempts;
    for (let attempt = 0; attempt < limit; attempt += 1) {
      if (findScratch(doc)) return scan(doc);
      const scanned = scan(doc);
      if (looksLikeBoard(scanned) || planOpener(scanned, loadId).strategy) return scanned;
      await sleep(200);
    }
    return scan(doc);
  }

  function assignLoadUrl(doc, loadId) {
    const href = knownLoadHref(loadId);
    const loc = doc?.defaultView?.location;
    if (!href || !loc || String(loc.origin || '') !== ORIGIN) return { ok: false };
    if (typeof loc.assign === 'function') loc.assign(href);
    else loc.href = href;
    return { ok: true, opener_strategy: 'known_load_url', stage: 'url' };
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function waitForScratch(doc, attempts) {
    for (let attempt = 0; attempt < (attempts || 8); attempt += 1) {
      const found = findScratch(doc);
      if (found) return found;
      await sleep(250);
    }
    return findScratch(doc);
  }

  function looksLikeLoadBasics(scanResult) {
    const texts = [...(scanResult.headings || []).map((item) => item.text), scanResult.title];
    return texts.some((text) => /\bload basics\b/.test(norm(text)));
  }

  async function settleWorkspace(doc, loadId) {
    for (let attempt = 0; attempt < 20; attempt += 1) {
      if (findScratch(doc) || planWorkspace(scan(doc), loadId).ready) return true;
      await sleep(250);
    }
    return !!(findScratch(doc) || planWorkspace(scan(doc), loadId).ready);
  }

  async function settleOpener(doc, loadId) {
    for (let attempt = 0; attempt < 24; attempt += 1) {
      if (findScratch(doc)) return scan(doc);
      const scanned = scan(doc);
      if (planWorkspace(scanned, loadId).ready) return scanned;
      const opener = planOpener(scanned, loadId);
      if (opener.strategy === 'unique_row_opener' || opener.strategy === 'unique_id_control' ||
          opener.strategy === 'unique_searchbox') {
        return scanned;
      }
      await sleep(250);
    }
    return scan(doc);
  }

  function scratchValue(doc) {
    const found = findScratch(doc);
    if (found) return String(found.value || found.el?.value || '');
    const el = doc.getElementById ? doc.getElementById(PRIVATE_NOTE_ID) : null;
    if (!el) return '';
    return String(el.value || '');
  }

  function typeNote(box, text) {
    if (!box) return;
    if (typeof box.focus === 'function') box.focus();
    box.value = String(text);
    box.dispatchEvent(new Event('input', { bubbles: true }));
    box.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function verifyPresence(doc, text) {
    const expected = String(text || '');
    if (expected && scratchValue(doc).includes(expected)) return true;
    const scanned = scan(doc);
    const privateNotes = scanned.textareas.filter((item) => item.visible && isPrivateNoteControl(item));
    if (privateNotes.some((item) => String(item.value || '').includes(expected))) return true;
    const listed = [...doc.querySelectorAll('[data-note-kind="private"],[data-note-kind="internal"]')]
      .some((el) => visible(el) && String(el.textContent || '').includes(expected));
    return listed;
  }

  async function openWorkspace(doc, loadId, options) {
    const waitAttempts = options && options.waitAttempts;
    const immediate = findScratch(doc);
    if (immediate) {
      return {
        ok: true,
        opener_strategy: 'already_open',
        note_label: immediate.label || immediate.id || PRIVATE_NOTE_ID,
        stage: 'workspace'
      };
    }
    const first = scan(doc);
    const openerNow = planOpener(first, loadId);
    const onBoard = !!openerNow.strategy || looksLikeBoard(first);
    if (!onBoard) {
      const waited = await waitForScratch(doc, waitAttempts == null ? 8 : waitAttempts);
      if (waited) {
        return {
          ok: true,
          opener_strategy: 'already_open',
          note_label: waited.label || waited.id || PRIVATE_NOTE_ID,
          stage: 'workspace'
        };
      }
      if (looksLikeLoadBasics(scan(doc))) {
        const late = await waitForScratch(doc, 16);
        if (late) {
          return {
            ok: true,
            opener_strategy: 'already_open',
            note_label: late.label || late.id || PRIVATE_NOTE_ID,
            stage: 'workspace'
          };
        }
      }
    }
    const settled = onBoard ? first : await settleOpener(doc, loadId);
    const workspace = planWorkspace(settled, loadId);
    if (findScratch(doc) || workspace.ready) {
      return { ok: true, opener_strategy: 'already_open', note_label: workspace.note_label || PRIVATE_NOTE_ID,
        stage: 'workspace' };
    }
    if (workspace.code === 'LOAD_IDENTITY_UNVERIFIED' || workspace.code === 'PRIVATE_NOTE_AMBIGUOUS') {
      return { ok: false, error_code: workspace.code, opener_strategy: 'none', note_label: workspace.note_label,
        stage: 'workspace' };
    }
    const planned = planOpener(settled, loadId);
    if (planned.error === 'LOAD_OPENER_AMBIGUOUS') {
      return { ok: false, error_code: planned.error, opener_strategy: 'none', stage: 'opener' };
    }
    if (planned.strategy === 'unique_searchbox') {
      if (options && options.forbid_searchbox) {
        return {
          ok: false,
          error_code: 'LOAD_OPENER_UNVERIFIED',
          opener_strategy: 'scratch_tab_required',
          stage: 'tab'
        };
      }
      fillNoSubmit(planned.target.el, loadId);
      if (options && options.allow_search_submit) pressEnter(planned.target.el);
      const afterSearch = await settleOpener(doc, loadId);
      const afterWorkspace = planWorkspace(afterSearch, loadId);
      if (findScratch(doc) || afterWorkspace.ready) {
        return { ok: true, opener_strategy: 'unique_searchbox', note_label: afterWorkspace.note_label, stage: 'search' };
      }
      const afterOpen = planOpener(afterSearch, loadId);
      if (afterOpen.strategy === 'unique_row_opener' || afterOpen.strategy === 'unique_id_control') {
        activate(afterOpen.target.el);
        if (!await settleWorkspace(doc, loadId)) {
          return { ok: false, error_code: 'LOAD_DETAIL_UNVERIFIED', opener_strategy: 'unique_searchbox', stage: 'detail' };
        }
        return { ok: true, opener_strategy: 'unique_searchbox', stage: 'detail' };
      }
      if (!(options && options.allow_load_url)) {
        return { ok: false, error_code: 'LOAD_OPENER_UNVERIFIED', opener_strategy: 'unique_searchbox', stage: 'search' };
      }
    }
    if (planned.strategy === 'unique_row_opener' || planned.strategy === 'unique_id_control') {
      activate(planned.target.el);
      if (!await settleWorkspace(doc, loadId)) {
        return { ok: false, error_code: 'LOAD_DETAIL_UNVERIFIED', opener_strategy: planned.strategy, stage: 'detail' };
      }
      return { ok: true, opener_strategy: planned.strategy, stage: 'detail' };
    }
    if (options && options.allow_load_url) {
      const assigned = assignLoadUrl(doc, loadId);
      if (assigned.ok) {
        if (await settleWorkspace(doc, loadId)) {
          return { ok: true, opener_strategy: 'known_load_url', stage: 'url' };
        }
        const afterUrl = await settleOpener(doc, loadId);
        if (findScratch(doc) || planWorkspace(afterUrl, loadId).ready) {
          return { ok: true, opener_strategy: 'known_load_url', stage: 'url' };
        }
        const afterUrlOpen = planOpener(afterUrl, loadId);
        if (afterUrlOpen.strategy === 'unique_row_opener' || afterUrlOpen.strategy === 'unique_id_control') {
          activate(afterUrlOpen.target.el);
          if (await settleWorkspace(doc, loadId)) {
            return { ok: true, opener_strategy: 'known_load_url', stage: 'url' };
          }
        }
      }
    }
    return { ok: false, error_code: 'LOAD_OPENER_UNVERIFIED', opener_strategy: planned.strategy || 'none', stage: 'opener' };
  }

  async function reopenAfterSave(doc, loadId, text, prior, options) {
    const backoff = options && options.backoff_ms != null ? options.backoff_ms : 1000;
    const boardTries = options && options.board_attempts != null ? options.board_attempts : 8;
    let attempts = 0;
    let last = { ok: false, error_code: 'LOAD_OPENER_UNVERIFIED', opener_strategy: 'none', stage: 'reopen' };
    if (verifyPresence(doc, text)) {
      return {
        ok: true, opener_strategy: prior?.opener_strategy || 'already_open', stage: 'verify',
        reopen_attempts: 0, verify_reason: 'verified_via_scratch_scan'
      };
    }
    for (let attempt = 0; attempt < 3; attempt += 1) {
      attempts += 1;
      if (verifyPresence(doc, text)) {
        return {
          ok: true, opener_strategy: last.opener_strategy || 'already_open', stage: 'verify',
          reopen_attempts: attempts, verify_reason: 'verified_via_scratch_scan'
        };
      }
      await waitForBoard(doc, loadId, boardTries);
      if (verifyPresence(doc, text)) {
        return {
          ok: true, opener_strategy: last.opener_strategy || 'already_open', stage: 'verify',
          reopen_attempts: attempts, verify_reason: 'verified_via_scratch_scan'
        };
      }
      last = await openWorkspace(doc, loadId, {
        waitAttempts: 8,
        allow_search_submit: true,
        allow_load_url: true
      });
      last.reopen_attempts = attempts;
      if (last.ok) {
        for (let wait = 0; wait < 16; wait += 1) {
          if (verifyPresence(doc, text)) {
            return {
              ok: true, opener_strategy: last.opener_strategy, stage: 'verify',
              reopen_attempts: attempts, verify_reason: null
            };
          }
          if (!findScratch(doc) && wait > 2) break;
          await sleep(250);
        }
        if (verifyPresence(doc, text)) {
          return {
            ok: true, opener_strategy: last.opener_strategy, stage: 'verify',
            reopen_attempts: attempts, verify_reason: null
          };
        }
      }
      await sleep(backoff * (attempt + 1));
    }
    if (verifyPresence(doc, text)) {
      return {
        ok: true, opener_strategy: last.opener_strategy || 'already_open', stage: 'verify',
        reopen_attempts: attempts, verify_reason: 'verified_via_scratch_scan'
      };
    }
    return { ...last, ok: false, stage: 'reopen', reopen_attempts: attempts };
  }

  async function execute(doc, command) {
    if (doc.defaultView?.location?.origin !== ORIGIN && command?.origin !== ORIGIN) {
      return report({ error_code: 'ORIGIN_NOT_ALLOWLISTED', stage: 'origin', tab_hint: command?.tab_hint || null });
    }
    try {
      if (command.mode === 'verify') {
        const present = verifyPresence(doc, command.text);
        return report({
          ok: present, verified: present, note_present: present,
          error_code: present ? null : 'note_not_present',
          stage: 'verify',
          opener_strategy: 'already_open',
          tab_hint: command.tab_hint || null,
          verify_reason: present ? 'verified_via_scratch_scan' : null
        });
      }
      if (command.mode === 'reopen') {
        const reopened = await reopenAfterSave(doc, command.load_id, command.text, null, {
          backoff_ms: command.reopen_backoff_ms,
          board_attempts: command.wait_board_attempts
        });
        const present = verifyPresence(doc, command.text);
        return report({
          ok: present, verified: present, note_present: present,
          error_code: present ? null : (reopened.error_code || 'LOAD_OPENER_UNVERIFIED'),
          stage: present ? 'verify' : 'reopen',
          opener_strategy: reopened.opener_strategy || 'none',
          tab_hint: command.tab_hint || null,
          reopen_attempts: reopened.reopen_attempts || 0,
          verify_reason: present ? (reopened.verify_reason || 'verified_via_scratch_scan') : null
        });
      }
      let opened = await openWorkspace(doc, command.load_id, {
        forbid_searchbox: !!command.forbid_searchbox
      });
      const scratch = findScratch(doc);
      const alreadyTyped = !!(scratch && command.text &&
        String(scratch.value || scratch.el?.value || '').includes(command.text));
      if (!opened.ok) {
        if (scratch) {
          opened = {
            ok: true,
            opener_strategy: 'already_open',
            note_label: scratch.label || scratch.id || PRIVATE_NOTE_ID,
            stage: 'workspace'
          };
        } else {
          return report({
            error_code: opened.error_code,
            stage: opened.stage,
            opener_strategy: opened.opener_strategy,
            note_label: opened.note_label || null,
            tab_hint: command.tab_hint || null
          });
        }
      }
      const planned = inspect(scan(doc), command);
      if (!planned.ok) {
        return report({
          error_code: alreadyTyped ? 'typed_but_not_saved' : planned.code,
          stage: alreadyTyped ? 'commit' : 'inspect',
          opener_strategy: opened.opener_strategy,
          note_label: planned.note_label || opened.note_label || null,
          commit_kind: planned.commit_kind || null,
          save_variant: planned.save_variant || null,
          tab_hint: command.tab_hint || null,
          allow_whole_form_save: !!command.allow_whole_form_save
        });
      }
      if (isPublicNoteControl(planned.target) || String(planned.target.id || '') === PUBLIC_NOTE_ID) {
        return report({
          error_code: 'PUBLIC_NOTE_BLOCKED',
          stage: 'inspect',
          opener_strategy: opened.opener_strategy,
          tab_hint: command.tab_hint || null,
          allow_whole_form_save: !!command.allow_whole_form_save
        });
      }
      typeNote(planned.target.el, command.text);
      activate(planned.commit.el);
      let verifyOpener = opened.opener_strategy;
      let reopenAttempts = 0;
      let verifyReason = null;
      if (planned.commit_kind === 'WHOLE_FORM_SAVE') {
        if (planned.save_variant === 'SAVE_AND_EXIT' || !findScratch(doc)) {
          const reopened = await reopenAfterSave(doc, command.load_id, command.text, opened, {
            backoff_ms: command.reopen_backoff_ms,
            board_attempts: command.wait_board_attempts
          });
          reopenAttempts = reopened.reopen_attempts || 0;
          verifyReason = reopened.verify_reason || null;
          if (!reopened.ok && !verifyPresence(doc, command.text)) {
            return report({
              error_code: reopened.error_code || 'LOAD_OPENER_UNVERIFIED',
              stage: 'reopen',
              opener_strategy: reopened.opener_strategy || 'none',
              note_label: planned.note_label,
              commit_kind: planned.commit_kind,
              save_variant: planned.save_variant,
              tab_hint: command.tab_hint || null,
              reopen_attempts: reopenAttempts,
              verify_reason: verifyReason,
              allow_whole_form_save: true
            });
          }
          verifyOpener = reopened.opener_strategy || verifyOpener;
        } else {
          await settleWorkspace(doc, command.load_id);
        }
      }
      const notePresent = verifyPresence(doc, command.text);
      return report({
        ok: notePresent,
        verified: notePresent,
        note_present: notePresent,
        error_code: notePresent ? null : 'note_not_present',
        stage: 'verify',
        opener_strategy: verifyOpener,
        tab_hint: command.tab_hint || null,
        note_label: planned.note_label,
        commit_kind: planned.commit_kind,
        save_variant: planned.save_variant || null,
        reopen_attempts: reopenAttempts,
        verify_reason: notePresent ? (verifyReason || (planned.save_variant === 'SAVE_AND_EXIT' ? 'verified_via_scratch_scan' : null)) : null,
        allow_whole_form_save: !!command.allow_whole_form_save
      });
    } catch (error) {
      return report({
        error_code: error?.code || error?.message || 'NOTE_WRITE_FAILED',
        stage: 'execute',
        tab_hint: command.tab_hint || null
      });
    }
  }

  globalThis.FreightDeskPortableWriteNote = Object.freeze({
    action: ACTION,
    inspect,
    scan,
    execute,
    findScratch,
    probeWorkspace,
    reopenAfterSave,
    waitForBoard,
    looksLikeBoard,
    knownLoadHref,
    pickStaySave,
    planWorkspace,
    planOpener,
    planCommit,
    isPrivateNoteLabel,
    isPublicNoteLabel,
    isNoteCommitLabel,
    isForbiddenCommitLabel,
    isOwnerPathCommit,
    isLoadIdentityLabel,
    isPrivateNoteControl,
    isPublicNoteControl,
    classifyWholeFormSave,
    origin: ORIGIN
  });
})();
