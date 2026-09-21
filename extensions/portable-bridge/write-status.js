(() => {
  'use strict';
  const ORIGIN = 'https://ascendtms.com';
  const ACTION = 'CHANGE_LOAD_STATUS';
  const BRIDGE_VERSION = '0.1.12';
  const STATUS_LABELS = Object.freeze(['load status', 'status']);
  const WRITE_STATUSES = Object.freeze([
    'Active', 'Available', 'Assigned', 'Booked', 'Dispatched',
    'In Transit', 'Delivered', 'Completed', 'To Be Billed', 'Driver Assigned'
  ]);
  const FORBIDDEN_ACTIONS = Object.freeze([
    'ASCEND_SAVE', 'ASCEND_SAVE_LOAD', 'ASCEND_SET_DRIVER', 'ASCEND_ASSIGN',
    'ASCEND_UPDATE_RATES', 'ASCEND_NEW_LOAD', 'ASCEND_UPLOAD', 'ASCEND_SEND',
    'ADD_PUBLIC_NOTE', 'ADD_INTERNAL_NOTE'
  ]);

  function notes() {
    return globalThis.FreightDeskPortableWriteNote;
  }

  function fail(code) {
    const error = new Error(code);
    error.code = code;
    throw error;
  }

  function norm(value) {
    return String(value || '').replace(/\s+/g, ' ').trim().toLowerCase().replace(/[:*]+$/, '');
  }

  function catalogStatus(value) {
    const key = norm(value);
    return WRITE_STATUSES.find((item) => norm(item) === key) || null;
  }

  function isStatusLabel(label) {
    const key = norm(label);
    return STATUS_LABELS.includes(key);
  }

  function report(partial) {
    return {
      ok: false,
      verified: false,
      status_matched: false,
      requested_status: null,
      observed_status: null,
      error_code: null,
      live_validated: false,
      production_writes: false,
      stage: null,
      opener_strategy: null,
      commit_kind: null,
      save_variant: null,
      allow_whole_form_save: false,
      tab_hint: null,
      reopen_attempts: 0,
      verify_reason: null,
      bridge_version: BRIDGE_VERSION,
      ...partial
    };
  }

  function scan(doc) {
    return notes().scan(doc);
  }

  function statusCandidates(scanResult) {
    const out = [];
    const seen = new Set();
    const push = (item, source) => {
      if (!item || seen.has(item.el || item)) return;
      const label = item.label || '';
      if (!isStatusLabel(label)) return;
      seen.add(item.el || item);
      out.push({ ...item, source });
    };
    for (const item of scanResult.inputs || []) push(item, item.tag === 'select' ? 'select' : 'input');
    for (const item of scanResult.labeled || []) {
      if (!isStatusLabel(item.label)) continue;
      const el = item.el;
      const control = el?.control || (el?.htmlFor && el.ownerDocument?.getElementById?.(el.htmlFor));
      if (control) {
        push({
          el: control,
          label: item.label,
          visible: item.visible !== false,
          value: String(control.value || control.textContent || '').trim(),
          tag: String(control.tagName || '').toLowerCase(),
          role: control.getAttribute?.('role') || ''
        }, String(control.tagName || '').toLowerCase() === 'select' ? 'select' : 'labeled');
      } else if (item.value) {
        out.push({
          el: item.el,
          label: item.label,
          visible: item.visible !== false,
          value: item.value,
          tag: 'label',
          role: '',
          source: 'labeled'
        });
      }
    }
    return out.filter((item) => item.visible !== false);
  }

  function pickStatusControl(scanResult) {
    const found = statusCandidates(scanResult);
    if (!found.length) return { ok: false, code: 'STATUS_CONTROL_NOT_FOUND' };
    const selects = found.filter((item) => item.tag === 'select' || item.role === 'combobox' ||
      item.role === 'listbox');
    const pool = selects.length ? selects : found;
    if (pool.length > 1) return { ok: false, code: 'STATUS_CONTROL_AMBIGUOUS' };
    return { ok: true, target: pool[0] };
  }

  function readStatus(target) {
    if (!target) return null;
    const el = target.el;
    if (el && String(el.tagName || '').toLowerCase() === 'select' && el.options) {
      const selected = el.options[el.selectedIndex];
      const raw = selected ? (selected.text || selected.value || el.value) : el.value;
      return catalogStatus(raw) || String(raw || '').trim() || null;
    }
    const raw = target.value || el?.value || el?.textContent || '';
    return catalogStatus(raw) || String(raw || '').trim() || null;
  }

  function matchOption(el, requested) {
    const want = catalogStatus(requested);
    if (!want || !el?.options) return null;
    const hits = [...el.options].filter((opt) => catalogStatus(opt.text) === want ||
      catalogStatus(opt.value) === want || norm(opt.text) === norm(want) ||
      norm(opt.value) === norm(want));
    if (hits.length === 1) return hits[0];
    return null;
  }

  function setStatus(target, requested) {
    const want = catalogStatus(requested);
    if (!want || !target?.el) fail('STATUS_OPTION_NOT_FOUND');
    const el = target.el;
    if (String(el.tagName || '').toLowerCase() === 'select') {
      const option = matchOption(el, want);
      if (!option) fail('STATUS_OPTION_NOT_FOUND');
      if (typeof el.focus === 'function') el.focus();
      el.value = option.value;
      const index = [...el.options].indexOf(option);
      if (index >= 0) el.selectedIndex = index;
      for (const item of el.options) item.selected = item === option;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return want;
    }
    if (typeof el.focus === 'function') el.focus();
    el.value = want;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return want;
  }

  function planCommit(scanResult, options) {
    const W = notes();
    const allow = !!(options && options.allow_whole_form_save);
    const controls = [];
    const seen = new Set();
    for (const item of [...(scanResult.buttons || []), ...(scanResult.links || [])]) {
      const key = item.el || item.label;
      if (seen.has(key)) continue;
      seen.add(key);
      controls.push(item);
    }
    const stayAll = controls.filter((item) => W.classifyWholeFormSave(item.label) === 'SAVE_STAY');
    const stayVisible = stayAll.filter((item) => item.visible);
    const stay = stayVisible.length ? stayVisible : stayAll;
    const exit = controls.filter((item) => item.visible && W.classifyWholeFormSave(item.label) === 'SAVE_AND_EXIT');
    const stayChosen = W.pickStaySave(stay);
    if (stayChosen) {
      if (!allow) {
        return {
          ok: false, code: 'STATUS_COMMIT_REQUIRES_OWNER_PATH',
          commit_kind: 'WHOLE_FORM_SAVE', save_variant: 'SAVE_STAY'
        };
      }
      return {
        ok: true, commit: stayChosen, commit_kind: 'WHOLE_FORM_SAVE', save_variant: 'SAVE_STAY'
      };
    }
    if (exit.length > 1) {
      return { ok: false, code: 'STATUS_SAVE_CONTROL_UNVERIFIED', commit_kind: 'AMBIGUOUS' };
    }
    if (exit.length === 1) {
      if (!allow) {
        return {
          ok: false, code: 'STATUS_COMMIT_REQUIRES_OWNER_PATH',
          commit_kind: 'WHOLE_FORM_SAVE', save_variant: 'SAVE_AND_EXIT'
        };
      }
      return {
        ok: true, commit: exit[0], commit_kind: 'WHOLE_FORM_SAVE', save_variant: 'SAVE_AND_EXIT'
      };
    }
    return { ok: false, code: 'STATUS_SAVE_CONTROL_UNVERIFIED', commit_kind: 'MISSING' };
  }

  function inspect(scanResult, command) {
    if (!command || FORBIDDEN_ACTIONS.includes(command.action) || command.action !== ACTION) {
      return { ok: false, code: 'WRITE_ACTION_FORBIDDEN' };
    }
    if (command.change_status === false || command.assign || command.rates || command.new_load ||
        command.send) {
      return { ok: false, code: 'WRITE_ACTION_FORBIDDEN' };
    }
    const requested = catalogStatus(command.status || command.requested_status);
    if (!requested) return { ok: false, code: 'STATUS_NOT_ALLOWED' };
    const found = pickStatusControl(scanResult);
    if (!found.ok) return found;
    const commit = planCommit(scanResult, command);
    if (!commit.ok) {
      return {
        ok: false,
        code: commit.code,
        commit_kind: commit.commit_kind,
        save_variant: commit.save_variant || null,
        target: found.target,
        requested_status: requested,
        observed_status: readStatus(found.target)
      };
    }
    return {
      ok: true,
      target: found.target,
      commit: commit.commit,
      commit_kind: commit.commit_kind,
      save_variant: commit.save_variant,
      requested_status: requested,
      observed_status: readStatus(found.target)
    };
  }

  function activate(el) {
    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  }

  function verifyStatus(doc, requested) {
    const want = catalogStatus(requested);
    const found = pickStatusControl(scan(doc));
    if (!found.ok) return { matched: false, observed: null };
    const observed = readStatus(found.target);
    return { matched: !!(want && catalogStatus(observed) === want), observed, target: found.target };
  }

  function probeWorkspace(doc, loadId, requested) {
    const W = notes();
    const scratch = W.findScratch ? W.findScratch(doc) : null;
    const found = pickStatusControl(scan(doc));
    const observed = found.ok ? readStatus(found.target) : null;
    const want = catalogStatus(requested);
    return {
      status_control: found.ok,
      already_open: !!(found.ok || scratch),
      observed_status: observed,
      status_matched: !!(want && catalogStatus(observed) === want),
      scratch: !!scratch
    };
  }

  async function openWorkspace(doc, loadId, options) {
    const immediate = pickStatusControl(scan(doc));
    if (immediate.ok) {
      return { ok: true, opener_strategy: 'already_open', stage: 'workspace' };
    }
    const opened = await notes().openWorkspace(doc, loadId, options);
    const after = pickStatusControl(scan(doc));
    if (after.ok) {
      return {
        ok: true,
        opener_strategy: opened.ok ? (opened.opener_strategy || 'already_open') : 'already_open',
        stage: 'workspace'
      };
    }
    if (opened.ok && notes().findScratch(doc)) {
      return { ok: true, opener_strategy: opened.opener_strategy || 'already_open', stage: 'workspace' };
    }
    return opened.ok
      ? { ok: false, error_code: 'STATUS_CONTROL_NOT_FOUND', opener_strategy: opened.opener_strategy,
        stage: 'inspect' }
      : opened;
  }

  async function reopenAfterSave(doc, loadId, requested, prior, options) {
    const backoff = options && options.backoff_ms != null ? options.backoff_ms : 1000;
    let attempts = 0;
    let last = { ok: false, error_code: 'LOAD_OPENER_UNVERIFIED', opener_strategy: 'none', stage: 'reopen' };
    const first = verifyStatus(doc, requested);
    if (first.matched) {
      return {
        ok: true, opener_strategy: prior?.opener_strategy || 'already_open', stage: 'verify',
        reopen_attempts: 0, verify_reason: 'verified_via_status_readback', observed: first.observed
      };
    }
    for (let attempt = 0; attempt < 3; attempt += 1) {
      attempts += 1;
      const check = verifyStatus(doc, requested);
      if (check.matched) {
        return {
          ok: true, opener_strategy: last.opener_strategy || 'already_open', stage: 'verify',
          reopen_attempts: attempts, verify_reason: 'verified_via_status_readback',
          observed: check.observed
        };
      }
      await notes().waitForBoard(doc, loadId, options && options.board_attempts);
      last = await openWorkspace(doc, loadId, {
        waitAttempts: 8,
        allow_search_submit: true,
        allow_load_url: true
      });
      last.reopen_attempts = attempts;
      if (last.ok) {
        const after = verifyStatus(doc, requested);
        if (after.matched) {
          return {
            ok: true, opener_strategy: last.opener_strategy, stage: 'verify',
            reopen_attempts: attempts, verify_reason: null, observed: after.observed
          };
        }
      }
      await new Promise((resolve) => setTimeout(resolve, backoff * (attempt + 1)));
    }
    const finalCheck = verifyStatus(doc, requested);
    if (finalCheck.matched) {
      return {
        ok: true, opener_strategy: last.opener_strategy || 'already_open', stage: 'verify',
        reopen_attempts: attempts, verify_reason: 'verified_via_status_readback',
        observed: finalCheck.observed
      };
    }
    return { ...last, ok: false, stage: 'reopen', reopen_attempts: attempts, observed: finalCheck.observed };
  }

  async function execute(doc, command) {
    const requested = catalogStatus(command?.status || command?.requested_status);
    if (doc.defaultView?.location?.origin !== ORIGIN && command?.origin !== ORIGIN) {
      return report({
        error_code: 'ORIGIN_NOT_ALLOWLISTED', stage: 'origin',
        tab_hint: command?.tab_hint || null, requested_status: requested
      });
    }
    try {
      if (!requested) {
        return report({
          error_code: 'STATUS_NOT_ALLOWED', stage: 'inspect',
          tab_hint: command?.tab_hint || null
        });
      }
      if (command.mode === 'verify') {
        const check = verifyStatus(doc, requested);
        return report({
          ok: check.matched, verified: check.matched, status_matched: check.matched,
          requested_status: requested, observed_status: check.observed,
          error_code: check.matched ? null : 'status_not_matched',
          stage: 'verify', opener_strategy: 'already_open',
          tab_hint: command.tab_hint || null,
          verify_reason: check.matched ? 'verified_via_status_readback' : null
        });
      }
      if (command.mode === 'reopen') {
        const reopened = await reopenAfterSave(doc, command.load_id, requested, null, {
          backoff_ms: command.reopen_backoff_ms,
          board_attempts: command.wait_board_attempts
        });
        const check = verifyStatus(doc, requested);
        return report({
          ok: check.matched, verified: check.matched, status_matched: check.matched,
          requested_status: requested, observed_status: check.observed || reopened.observed,
          error_code: check.matched ? null : (reopened.error_code || 'LOAD_OPENER_UNVERIFIED'),
          stage: check.matched ? 'verify' : 'reopen',
          opener_strategy: reopened.opener_strategy || 'none',
          tab_hint: command.tab_hint || null,
          reopen_attempts: reopened.reopen_attempts || 0,
          verify_reason: check.matched ? (reopened.verify_reason || 'verified_via_status_readback') : null
        });
      }
      let opened = await openWorkspace(doc, command.load_id, {
        forbid_searchbox: !!command.forbid_searchbox
      });
      const present = pickStatusControl(scan(doc));
      if (!opened.ok) {
        if (present.ok) {
          opened = { ok: true, opener_strategy: 'already_open', stage: 'workspace' };
        } else {
          return report({
            error_code: opened.error_code,
            stage: opened.stage,
            opener_strategy: opened.opener_strategy,
            requested_status: requested,
            tab_hint: command.tab_hint || null
          });
        }
      }
      const planned = inspect(scan(doc), { ...command, action: ACTION, status: requested });
      if (!planned.ok) {
        return report({
          error_code: planned.code,
          stage: 'inspect',
          opener_strategy: opened.opener_strategy,
          commit_kind: planned.commit_kind || null,
          save_variant: planned.save_variant || null,
          requested_status: requested,
          observed_status: planned.observed_status || (present.ok ? readStatus(present.target) : null),
          tab_hint: command.tab_hint || null,
          allow_whole_form_save: !!command.allow_whole_form_save
        });
      }
      setStatus(planned.target, requested);
      activate(planned.commit.el);
      let verifyOpener = opened.opener_strategy;
      let reopenAttempts = 0;
      let verifyReason = null;
      if (planned.commit_kind === 'WHOLE_FORM_SAVE') {
        if (planned.save_variant === 'SAVE_AND_EXIT' || !pickStatusControl(scan(doc)).ok) {
          const reopened = await reopenAfterSave(doc, command.load_id, requested, opened, {
            backoff_ms: command.reopen_backoff_ms,
            board_attempts: command.wait_board_attempts
          });
          reopenAttempts = reopened.reopen_attempts || 0;
          verifyReason = reopened.verify_reason || null;
          if (!reopened.ok && !verifyStatus(doc, requested).matched) {
            return report({
              error_code: reopened.error_code || 'LOAD_OPENER_UNVERIFIED',
              stage: 'reopen',
              opener_strategy: reopened.opener_strategy || 'none',
              commit_kind: planned.commit_kind,
              save_variant: planned.save_variant,
              requested_status: requested,
              observed_status: reopened.observed || null,
              tab_hint: command.tab_hint || null,
              reopen_attempts: reopenAttempts,
              verify_reason: verifyReason,
              allow_whole_form_save: true
            });
          }
          verifyOpener = reopened.opener_strategy || verifyOpener;
        }
      }
      const check = verifyStatus(doc, requested);
      return report({
        ok: check.matched,
        verified: check.matched,
        status_matched: check.matched,
        requested_status: requested,
        observed_status: check.observed,
        error_code: check.matched ? null : 'status_not_matched',
        stage: 'verify',
        opener_strategy: verifyOpener,
        tab_hint: command.tab_hint || null,
        commit_kind: planned.commit_kind,
        save_variant: planned.save_variant || null,
        reopen_attempts: reopenAttempts,
        verify_reason: check.matched ? (verifyReason || 'verified_via_status_readback') : null,
        allow_whole_form_save: !!command.allow_whole_form_save
      });
    } catch (error) {
      return report({
        error_code: error?.code || error?.message || 'STATUS_WRITE_FAILED',
        stage: 'execute',
        requested_status: requested,
        tab_hint: command.tab_hint || null
      });
    }
  }

  globalThis.FreightDeskPortableWriteStatus = Object.freeze({
    action: ACTION,
    version: BRIDGE_VERSION,
    inspect,
    scan,
    execute,
    probeWorkspace,
    pickStatusControl,
    readStatus,
    setStatus,
    catalogStatus,
    isStatusLabel,
    planCommit,
    verifyStatus,
    WRITE_STATUSES,
    origin: ORIGIN
  });
})();
