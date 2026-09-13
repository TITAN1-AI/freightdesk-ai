"""Owner-executed, single-open DOM relationship diagnostic; no operational field reader."""
import asyncio
import time
from datetime import date
from pathlib import Path
from uuid import uuid4

from app.core.runtime import RuntimePaths
from app.models.domain import utcnow
from app.services.live_ops_carrierview import validate_reconciliation_scope
from app.services.multi_phase_progress import safe_failure
from app.services.store import Store
from integrations.ascend.detail_identity_diagnostic import APPROVED, path_metadata
from integrations.ascend.field_discovery import ReadOnly1752Executor
from integrations.ascend.isolated_diagnostic import LocalSession, load_manifest
from integrations.ascend.ops_discovery import board_candidates

ATTEMPT = 'owner-ascend-final-identity-1755-20260911-01'
TARGET = '1755'
LIVE_EXECUTION_PREPARED = False  # Final attempt consumed; Playwright detail identity experiments CLOSED.
SCAN = Path(__file__).with_name('causal_identity.js').read_text(encoding='utf-8')
SAFE_CODES = {'causal_scan_bound', 'causal_frame_set_changed', 'causal_row_binding_missing',
    'causal_dom_unstable', 'causal_opener_changed', 'causal_identity_origin_mismatch', 'targeted_causal_bound_exceeded'}


class TargetedReadExecutor(ReadOnly1752Executor):
    """Resolve identity cells only; never search page text or fill a search box."""
    def __init__(self, *args, observe=lambda *a: None, **kwargs):
        super().__init__(*args, **kwargs)
        self.observe = observe

    def bound(self, category, measured, maximum):
        if measured > maximum:
            self.observe('TARGETED_BOUND_EXCEEDED', {'scan_phase': 'exact_row',
                'bound': {'category': category, 'measured': measured, 'maximum': maximum}})
            raise ValueError('targeted_causal_bound_exceeded')

    async def find_1752(self):
        await self.guard()
        matches = []
        for frame in self.frames():
            tables = frame.locator('table,[role="grid"],[role="table"]')
            self.bound('board_tables', await tables.count(), 8)
            for index in range(await tables.count()):
                table = tables.nth(index)
                header = await table.evaluate('''t => {
                    const h=[...t.querySelectorAll('thead th,[role="columnheader"]')];
                    const indices=h.map((e,i)=>['load id','load #','load number'].includes(e.textContent.trim().toLowerCase())?i:-1).filter(i=>i>=0);
                    return {count:h.length,index:indices.length===1?indices[0]:null};
                }''')
                self.bound('row_headers', header['count'], 64)
                if header['index'] is None:
                    continue
                rows = table.locator('tbody > tr,[role="row"]')
                self.bound('board_rows', await rows.count(), 100)
                for i in range(await rows.count()):
                    cells = rows.nth(i).locator(':scope > td,:scope > [role="cell"],:scope > [role="gridcell"]')
                    if await cells.count() <= header['index']:
                        continue
                    cell = cells.nth(header['index'])
                    if await cell.is_visible() and await cell.evaluate('(e,n)=>e.textContent.trim()===n', TARGET):
                        matches.append(cell)
        if len(matches) != 1:
            raise ValueError('exact_load_discovery_ambiguous_or_missing')
        return matches[0]


def differential(before: list[dict], after: list[dict]) -> list[dict]:
    old = {(f['frame'], c['node']): c for f in before for c in f['containers']}
    changes = []
    for frame in after:
        for c in frame['containers']:
            previous = old.get((frame['frame'], c['node']))
            kind = (('newly_visible' if c.get('previously_existed') else 'newly_created') if previous is None else 'newly_visible' if
                c['visible'] and not previous['visible'] else 'materially_changed' if
                c.get('fingerprint', c) != previous.get('fingerprint', previous) else None)
            if kind:
                changes.append(dict(c, frame=frame['frame'], change_type=kind))
    return changes


def decide(before: list[dict], after: list[dict], expected: str = TARGET) -> dict:
    changes = differential(before, after)
    controls = [f['control'] for f in before if f['control']]
    current = [f['control'] for f in after if f['control']]
    def unknown(code):
        return {'state': 'UNKNOWN', 'error_code': code}
    if len(controls) != 1 or not controls[0]['exact_row_bound']:
        return unknown('causal_row_binding_missing')
    opener = controls[0]
    visible = [c for c in changes if c['detail'] and c['visible']]
    visible = [c for c in visible if c['surface'] or not any(
        a['surface'] and a['frame'] == c['frame'] and c['node'] in a['ancestors'] for a in visible)]
    # A modal containing a changed form is one detail surface, not two independent panels.
    roots = [c for c in visible if not any(a['frame'] == c['frame'] and a['node'] in c['ancestors'] for a in visible)]
    signals = opener['identity_signals'] + opener['row_identity_signals']
    signals += [s for f in after for c in f['containers'] if c['visible'] for s in c['identity_signals']]
    signals += [s for c in current for s in c['identity_signals'] + c['row_identity_signals']]
    if any(s['unapproved_value'] or (s['value'] and s['value'] != expected) for s in signals):
        return unknown('CONFLICT')
    if len(roots) > 1:
        return unknown('AMBIGUOUS_DETAIL_CONTAINER')
    if not roots:
        return unknown('provider_binding_missing')
    panel = roots[0]
    base = {'state': 'VERIFIED', 'provider_observed_load_id': expected,
        'panel': {'frame': panel['frame'], 'selector': panel['selector'], 'node': panel['node']},
        'opener': {'selector': opener['selector'], 'node': opener['node'], 'row_node': opener['row_node']}}
    explicit = [s for s in panel['identity_signals'] if s['value'] == expected]
    if explicit:
        return dict(base, strategy_type='PROVIDER_DETAIL_FIELD', evidence_categories=sorted({s['category'] for s in explicit}),
            identity_selectors=sorted({s['selector'] for s in explicit}))
    opener_frame = next(f['frame'] for f in before if f['control'])
    if panel['frame'] != opener_frame or not panel['bindings']:
        return unknown('provider_binding_missing')
    bound = dict(base, relationships=panel['bindings'])
    opener_ids = [s for s in opener['identity_signals'] if s['value'] == expected]
    if opener_ids:
        return dict(bound, strategy_type='PROVIDER_OPENER_IDENTITY',
            evidence_categories=sorted({s['category'] for s in opener_ids} | {'stable_dom_binding', 'unique_changed_panel'}))
    if len(current) == 1 and current[0]['exact_row_bound'] and (current[0]['row_selected'] or current[0]['control_selected']):
        if not (opener['row_selected'] or opener['control_selected']):
            return dict(bound, strategy_type='PROVIDER_SELECTED_ROW_BINDING',
                evidence_categories=['exact_row_identity', 'provider_selection_transition', 'stable_dom_binding', 'unique_changed_panel'])
    return unknown('provider_binding_missing')


class CausalObserver:
    def __init__(self, page, guard, observe):
        self.page, self.guard, self.observe = page, guard, observe
        self.frames = []
        self.before = None

    async def prepare(self, opener, target):
        control, match = await opener.element_handle(), await target.element_handle()
        owner_frame = await control.owner_frame()
        if not owner_frame or not path_metadata(owner_frame.url)['same_origin']:
            raise ValueError('causal_identity_origin_mismatch')
        frames = [owner_frame]
        for i, frame in enumerate(frames):
            state = await frame.evaluate_handle('() => ({nodes:new WeakMap(),next:0,baseline:new Map(),known:new WeakSet()})')
            self.frames.append((frame, {'state': state, 'approved': sorted(APPROVED),
                'opener': control if frame == owner_frame else None,
                'target': match if frame == owner_frame else None}, i))
        self.observe('OPENER_IDENTIFIED', {'unique_opener_resolved': True, 'target_load_id': TARGET})
        initial = await self.snapshot(mode='opener')
        controls = [f['control'] for f in initial if f['control']]
        self.observe('OPENER_STRUCTURE', {'opener_structure': controls})
        if len(controls) != 1 or not controls[0]['exact_row_bound']:
            raise ValueError('causal_row_binding_missing')
        self.initial_control = controls[0]

    async def snapshot(self, mode='after') -> list[dict]:
        if not path_metadata(self.page.url)['same_origin']:
            raise PermissionError('causal_identity_origin_mismatch')
        result = []
        for frame, args, i in self.frames:
            if frame.is_detached() or not path_metadata(frame.url)['same_origin']:
                raise ValueError('causal_frame_set_changed')
            data = await asyncio.wait_for(frame.evaluate(SCAN, dict(args, mode=mode)), 3)
            if data['overflow']:
                self.observe('TARGETED_BOUND_EXCEEDED', {'bound': data['bound'], 'scan_phase': mode})
                raise ValueError('targeted_causal_bound_exceeded')
            result.append(dict(data, frame=i, path=path_metadata(frame.url)['path']))
        return result

    async def before_click(self):
        await self.guard()
        self.before = await self.snapshot(mode='before')
        controls = [f['control'] for f in self.before if f['control']]
        if controls != [self.initial_control]:
            raise ValueError('causal_opener_changed')
        self.observe('BEFORE_DETAIL_OPEN', {'before_structure': self.before})

    async def finish(self, timeout: float = 10) -> dict:
        start, stable, previous = time.monotonic(), 0, None
        stable_since = start
        while time.monotonic() - start < timeout:
            # Includes guard and all frames in a single remaining-time budget.
            remaining = timeout - (time.monotonic() - start)
            async def sample():
                await self.guard()
                return await self.snapshot()
            try:
                after = await asyncio.wait_for(sample(), max(.001, remaining))
            except TimeoutError:
                break
            decision = decide(self.before, after)
            changes = differential(self.before, after)
            if after != previous:
                stable_since = time.monotonic()
            stable = stable + 1 if after == previous else 0
            previous = after
            self.observe('AFTER_DETAIL_OPEN', {'after_structure': after, 'container_changes': changes,
                'decision': decision, 'render_wait_elapsed': round(time.monotonic() - start, 3)})
            if decision.get('error_code') == 'CONFLICT':
                return decision
            if stable >= 2 and time.monotonic() - stable_since >= 1 and decision.get('error_code') != 'provider_binding_missing':
                return decision
            await asyncio.sleep(min(.25, max(0, timeout - (time.monotonic() - start))))
        if previous is not None and stable >= 2:
            result = decide(self.before, previous)
            if result['state'] == 'UNKNOWN':
                return result
        return {'state': 'UNKNOWN', 'error_code': 'causal_dom_unstable'}


async def run(paths=None, session_factory=LocalSession, observer_factory=CausalObserver):
    if not LIVE_EXECUTION_PREPARED:
        return {'status': 'STOPPED_CAUSAL_IDENTITY_DIAGNOSTIC', 'execution_stage': 'PREFLIGHT',
            'error_code': 'targeted_live_attempt_not_prepared', 'production_writes': False,
            'reason': 'No new live attempt is prepared. Do not reuse the consumed attempt.'}
    paths = paths or RuntimePaths.from_environment()
    store = Store(paths.path('Data', 'booking-logistics', 'ascend', 'causal-identity-diagnostics.sqlite3'))
    state = {'attempt_id': ATTEMPT, 'target_load_id': TARGET, 'execution_stage': 'PREFLIGHT',
        'production_writes': False, 'operational_extraction': False, 'live_validated': False,
        'tenant_identity': 'Booking Logistics', 'tenant_identity_source': 'OWNER_ATTESTED'}
    session = None
    final_grant_consumed = False

    def observe(stage, metadata):
        state.update(execution_stage=stage)
        if 'bound' in metadata:
            state['bound'] = metadata['bound']
        store.put('booking-logistics', 'causal_checkpoint', ATTEMPT + ':' + uuid4().hex,
            dict(state, **metadata, observed_at=utcnow().isoformat()))

    try:
        manifest = load_manifest(paths)
        with store.transaction():
            if store.all('booking-logistics', 'final_causal_grant'):
                raise PermissionError('one_use_phase_consumed_no_retry')
            store.put('booking-logistics', 'final_causal_grant', ATTEMPT, {'id': ATTEMPT, 'consumed': True, 'final_attempt': True})
        final_grant_consumed = True
        observe('BROWSER_OWNER_CONFIRMATION', {})
        session = session_factory(paths)
        await session.confirm()
        session.observe_board = lambda m: observe('BOARD_NORMALIZATION', m)
        board = await session.board(lambda: observe('ACTIVE_LOADS_SELECTED', {}))
        validate_reconciliation_scope(manifest, board_candidates(board, date(2026, 9, 11), 'US', ATTEMPT))
        observe('BOARD_RECONCILED', {'exact_scope_reconciled': True})
        executor = TargetedReadExecutor(session.page, session.running, load_number=TARGET, authorized_loads=(TARGET,), observe=observe)
        observer = observer_factory(session.page, executor.guard, observe)
        await executor.open_1752(inspect_control=observer.prepare, before_click=observer.before_click)
        decision = await observer.finish()
        if decision['state'] == 'VERIFIED':
            contract = {'contract_type': 'AscendLoadDetailIdentityContract', 'version': 1,
                'provider': 'AscendTMS', 'observed_target': TARGET, 'observed_at': utcnow().isoformat(),
                'source': 'live browser DOM', 'confidence': 'VERIFIED', 'strategy': decision,
                'scope': 'OBSERVED_LOAD_1755_ONLY', 'automatic_reader_activation': False, 'write_activation': False}
            store.put('booking-logistics', 'causal_identity_contract', ATTEMPT, contract)
            state.update(status='CAUSAL_IDENTITY_DIAGNOSTIC_COMPLETE', strategy_type=decision['strategy_type'])
            observe('CONTRACT_OBSERVED', {'contract': contract})
        else:
            state.update(status='STOPPED_CAUSAL_IDENTITY_DIAGNOSTIC', error_code=decision['error_code'])
            observe('IDENTITY_UNVERIFIED', {'decision': decision})
    except Exception as error:
        code, reason = safe_failure(error)
        if len(error.args) == 1 and isinstance(error.args[0], str) and error.args[0] in SAFE_CODES:
            code, reason = error.args[0], 'A bounded DOM identity diagnostic gate stopped; no retry.'
        state.update(status='STOPPED_CAUSAL_IDENTITY_DIAGNOSTIC', error_code=code, reason=reason)
        observe(state['execution_stage'], {})
    finally:
        if session:
            try:
                await session.close()
            except Exception:
                if state.get('status') != 'STOPPED_CAUSAL_IDENTITY_DIAGNOSTIC':
                    state.update(status='STOPPED_CAUSAL_IDENTITY_DIAGNOSTIC', error_code='causal_cleanup_failed')
                    observe('CLEANUP', {})
        if final_grant_consumed and state.get('status') == 'STOPPED_CAUSAL_IDENTITY_DIAGNOSTIC':
            state['pivot_required'] = True
            observe(state['execution_stage'], {'next_step': 'Stop Playwright identity experiments; assess extension bridge or owner-approved row-bound evidence.'})
        store.close()
    return state
