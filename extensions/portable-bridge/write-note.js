(() => {
  'use strict';
  const ORIGIN = 'https://ascendtms.com';
  const ACTION = 'ADD_INTERNAL_NOTE';
  const PRIVATE_LABELS = Object.freeze(['private notes', 'internal notes']);
  const PUBLIC_LABELS = Object.freeze(['notes', 'load posting notes', 'public load notes', 'public notes']);
  const NOTE_COMMIT = Object.freeze(['add note', 'save note', 'add internal note', 'save internal note',
    'add private note', 'save private note']);
  const FORBIDDEN_COMMIT = Object.freeze([
    'save load', 'save', 'submit', 'book it', 'new load', 'create load', 'assign', 'assign carrier',
    'update status', 'change status', 'rates', 'upload', 'send', 'delete', 'cancel load'
  ]);
  const FORBIDDEN_ACTIONS = Object.freeze([
    'ASCEND_SAVE', 'ASCEND_SAVE_LOAD', 'ASCEND_SET_DRIVER', 'ASCEND_ASSIGN', 'ASCEND_UPDATE_STATUS',
    'ASCEND_UPDATE_RATES', 'ASCEND_NEW_LOAD', 'ASCEND_UPLOAD', 'ASCEND_SEND', 'ADD_PUBLIC_NOTE'
  ]);

  function fail(code) {
    const error = new Error(code);
    error.code = code;
    throw error;
  }

  function norm(value) {
    return String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
  }

  function visible(el) {
    return !!el?.getClientRects?.().length && getComputedStyle(el).visibility !== 'hidden' &&
      !el.closest('[hidden],[aria-hidden="true"]');
  }

  function controlLabel(el) {
    const labeled = el.labels && el.labels.length === 1 ? el.labels[0].textContent : '';
    return norm(el.getAttribute('aria-label') || labeled || el.textContent);
  }

  function isPrivateNoteLabel(label) {
    return PRIVATE_LABELS.includes(norm(label));
  }

  function isPublicNoteLabel(label) {
    const key = norm(label);
    return PUBLIC_LABELS.includes(key) && !isPrivateNoteLabel(key);
  }

  function isNoteCommitLabel(label) {
    return NOTE_COMMIT.includes(norm(label));
  }

  function isForbiddenCommitLabel(label) {
    const key = norm(label);
    if (isNoteCommitLabel(key)) return false;
    return FORBIDDEN_COMMIT.includes(key) || /\b(assign|book it|new load|upload|send|rate|status)\b/.test(key);
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
    const privateNotes = (scan.textareas || []).filter((item) => item.visible && isPrivateNoteLabel(item.label));
    const publicNotes = (scan.textareas || []).filter((item) => item.visible && isPublicNoteLabel(item.label));
    if (publicNotes.length && !privateNotes.length) {
      return { ok: false, code: 'PUBLIC_NOTE_BLOCKED' };
    }
    if (privateNotes.length !== 1) {
      return { ok: false, code: privateNotes.length ? 'PRIVATE_NOTE_AMBIGUOUS' : 'PRIVATE_NOTE_NOT_FOUND' };
    }
    const commits = (scan.buttons || []).filter((item) => item.visible && isNoteCommitLabel(item.label));
    const forbidden = (scan.buttons || []).filter((item) => item.visible && isForbiddenCommitLabel(item.label));
    if (commits.length !== 1) {
      return { ok: false, code: 'NOTE_SAVE_CONTROL_UNVERIFIED', forbidden_visible: forbidden.length };
    }
    return { ok: true, target: privateNotes[0], commit: commits[0] };
  }

  function scan(doc) {
    const textareas = [...doc.querySelectorAll('textarea,[role="textbox"]')].map((el) => ({
      el, label: controlLabel(el), visible: visible(el), value: el.value || el.textContent || ''
    }));
    const buttons = [...doc.querySelectorAll('button,input[type="submit"],input[type="button"],[role="button"]')]
      .map((el) => ({ el, label: controlLabel(el), visible: visible(el) }));
    return { textareas, buttons };
  }

  function activate(el) {
    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  }

  function findLoadOpener(doc, loadId) {
    const rows = [...doc.querySelectorAll('tbody > tr,[role="row"]')].filter(visible);
    const matches = [];
    for (const row of rows) {
      const cells = [...row.querySelectorAll('td,[role="cell"],[role="gridcell"],a,button')];
      const identity = cells.find((cell) => norm(cell.textContent) === String(loadId));
      if (!identity) continue;
      matches.push(identity);
    }
    if (matches.length !== 1) return null;
    return matches[0];
  }

  function detailIdentityVisible(doc, loadId) {
    const headings = [...doc.querySelectorAll('h1,h2,h3,[role="heading"]')]
      .some((el) => visible(el) && norm(el.textContent).includes(String(loadId)));
    const notes = scan(doc).textareas.some((item) => item.visible && isPrivateNoteLabel(item.label));
    return headings && notes;
  }

  async function settleDetail(doc, loadId) {
    for (let attempt = 0; attempt < 20; attempt += 1) {
      if (detailIdentityVisible(doc, loadId)) return true;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    return detailIdentityVisible(doc, loadId);
  }

  function verifyPresence(doc, text) {
    const expected = String(text || '');
    const scanned = scan(doc);
    const privateNotes = scanned.textareas.filter((item) => item.visible && isPrivateNoteLabel(item.label));
    if (privateNotes.some((item) => String(item.value || '').includes(expected))) return true;
    const listed = [...doc.querySelectorAll('[data-note-kind="private"],[data-note-kind="internal"]')]
      .some((el) => visible(el) && String(el.textContent || '').includes(expected));
    return listed;
  }

  async function execute(doc, command) {
    if (doc.defaultView?.location?.origin !== ORIGIN && command?.origin !== ORIGIN) {
      return { ok: false, verified: false, note_present: false, error_code: 'ORIGIN_NOT_ALLOWLISTED' };
    }
    try {
      if (!detailIdentityVisible(doc, command.load_id)) {
        const opener = findLoadOpener(doc, command.load_id);
        if (!opener) return { ok: false, verified: false, note_present: false, error_code: 'LOAD_OPENER_UNVERIFIED' };
        activate(opener);
        if (!await settleDetail(doc, command.load_id)) {
          return { ok: false, verified: false, note_present: false, error_code: 'LOAD_DETAIL_UNVERIFIED' };
        }
      }
      const planned = inspect(scan(doc), command);
      if (!planned.ok) {
        return { ok: false, verified: false, note_present: false, error_code: planned.code };
      }
      const box = planned.target.el;
      box.focus();
      box.value = command.text;
      box.dispatchEvent(new Event('input', { bubbles: true }));
      box.dispatchEvent(new Event('change', { bubbles: true }));
      activate(planned.commit.el);
      const notePresent = verifyPresence(doc, command.text);
      return {
        ok: notePresent,
        verified: notePresent,
        note_present: notePresent,
        error_code: notePresent ? null : 'note_not_present',
        live_validated: false,
        production_writes: false
      };
    } catch (error) {
      return {
        ok: false,
        verified: false,
        note_present: false,
        error_code: error?.code || error?.message || 'NOTE_WRITE_FAILED',
        live_validated: false,
        production_writes: false
      };
    }
  }

  globalThis.FreightDeskPortableWriteNote = Object.freeze({
    action: ACTION,
    inspect,
    scan,
    execute,
    isPrivateNoteLabel,
    isPublicNoteLabel,
    isNoteCommitLabel,
    isForbiddenCommitLabel,
    origin: ORIGIN
  });
})();
