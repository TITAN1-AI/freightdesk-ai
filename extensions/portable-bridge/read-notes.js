(() => {
  'use strict';
  const ORIGIN = 'https://ascendtms.com';
  const ACTION = 'READ_LOAD_NOTES';
  const BRIDGE_VERSION = '0.1.13';

  function notes() {
    return globalThis.FreightDeskPortableWriteNote;
  }

  function report(partial) {
    return {
      ok: false,
      verified: false,
      note_present: false,
      private_note_present: false,
      public_note_present: false,
      private_note: null,
      public_note: null,
      error_code: null,
      live_validated: false,
      production_writes: false,
      silent_save_forbidden: true,
      stage: null,
      opener_strategy: null,
      note_label: null,
      commit_kind: 'READ_ONLY',
      save_variant: 'NONE',
      allow_whole_form_save: false,
      tab_hint: null,
      reopen_attempts: 0,
      verify_reason: null,
      bridge_version: BRIDGE_VERSION,
      ...partial
    };
  }

  function controlValue(item) {
    if (!item) return '';
    return String(item.value || item.el?.value || '');
  }

  function capture(doc) {
    const W = notes();
    const scratch = W.findScratch ? W.findScratch(doc) : null;
    const publicNote = W.findPublicNote ? W.findPublicNote(doc) : null;
    return {
      private_control: !!scratch,
      public_control: !!publicNote,
      private_note: scratch ? controlValue(scratch) : null,
      public_note: publicNote ? controlValue(publicNote) : null,
      note_label: (scratch && (scratch.label || scratch.id)) ||
        (publicNote && (publicNote.label || publicNote.id)) || null
    };
  }

  function captureReport(doc, command, opener) {
    const found = capture(doc);
    const verified = !!(found.private_control || found.public_control);
    let verifyReason = null;
    if (found.private_control && found.public_control) verifyReason = 'verified_via_note_controls';
    else if (found.private_control) verifyReason = 'verified_via_scratch_scan';
    else if (found.public_control) verifyReason = 'verified_via_public_notes';
    return report({
      ok: verified,
      verified,
      note_present: found.private_control,
      private_note_present: found.private_control,
      public_note_present: found.public_control,
      private_note: found.private_note,
      public_note: found.public_note,
      error_code: verified ? null : 'NOTE_CONTROLS_NOT_FOUND',
      stage: 'verify',
      opener_strategy: opener || 'already_open',
      note_label: found.note_label,
      tab_hint: command.tab_hint || null,
      verify_reason: verifyReason
    });
  }

  async function execute(doc, command) {
    const W = notes();
    if (!W || typeof W.openWorkspace !== 'function') {
      return report({ error_code: 'CONTENT_UNAVAILABLE', stage: 'content' });
    }
    if (command.origin && command.origin !== ORIGIN) {
      return report({ error_code: 'ORIGIN_NOT_ALLOWLISTED', stage: 'origin' });
    }
    const mode = command.mode || 'read';
    if (mode === 'verify') {
      return captureReport(doc, command, command.opener_strategy || 'already_open');
    }
    try {
      const opened = await W.openWorkspace(doc, command.load_id, {
        forbid_searchbox: !!command.forbid_searchbox,
        allow_search_submit: !!command.allow_search_submit,
        allow_load_url: !!command.allow_load_url,
        waitAttempts: command.wait_scratch_attempts
      });
      if (!opened?.ok) {
        const late = capture(doc);
        if (late.private_control || late.public_control) {
          return captureReport(doc, command, opened?.opener_strategy || 'already_open');
        }
        return report({
          error_code: opened?.error_code || 'LOAD_OPENER_UNVERIFIED',
          stage: opened?.stage || 'opener',
          opener_strategy: opened?.opener_strategy || 'none',
          tab_hint: command.tab_hint || null
        });
      }
      return captureReport(doc, command, opened.opener_strategy || 'already_open');
    } catch (error) {
      return report({
        error_code: error?.code || error?.message || 'NOTE_READ_FAILED',
        stage: 'execute',
        tab_hint: command.tab_hint || null
      });
    }
  }

  globalThis.FreightDeskPortableReadNotes = Object.freeze({
    action: ACTION,
    version: BRIDGE_VERSION,
    execute,
    capture,
    origin: ORIGIN
  });
})();
