"""Fixed read intents and provenance-tagged, exact-load field proposals. No generated actions."""
import asyncio
import re
import time
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, Field

from app.models.domain import Model, utcnow
from app.services.mail_sync import digest
from integrations.ascend.adapter import normalize_field
from integrations.ascend.identity import IdentityConfig, observe_session
from integrations.ascend.models import AscendError, ComparisonEvidence

ORIGIN = 'https://ascendtms.com'
# Vocabulary is candidate semantics, not a pre-verified selector contract. Only observed exact labels
# qualify for a proposal; acceptance additionally requires an unambiguous local evidence match.
LABELS = {
    'Load Number':'load_number', 'Load #':'load_number', 'Load No.':'load_number', 'Load ID':'load_number',
    'Customer':'customer', 'Customer Name':'customer', 'Customer Reference':'customer_reference',
    'Status':'status', 'Load Status':'status', 'Origin':'origin', 'Destination':'destination',
    'Pickup Facility':'pickup_facility', 'Delivery Facility':'delivery_facility',
    'Pickup Appointment':'pickup_appointment', 'Delivery Appointment':'delivery_appointment',
    'Equipment':'equipment', 'Equipment Type':'equipment', 'Commodity':'commodity', 'Weight':'weight',
    'Carrier':'carrier', 'Carrier Name':'carrier', 'MC Number':'carrier_mc', 'DOT Number':'carrier_dot',
    'Driver':'driver', 'Driver Name':'driver', 'Truck':'truck', 'Truck Number':'truck',
    'Trailer':'trailer', 'Trailer Number':'trailer', 'Total Income':'customer_revenue',
    'Customer Revenue':'customer_revenue', 'Total Expenses':'total_expenses',
    'Gross Profit/Loss':'gross_profit', 'Gross Profit':'gross_profit', 'Gross Margin':'gross_margin',
}
TABS = ('General', 'Load Details', 'Details', 'Stops', 'Pickup', 'Delivery', 'Carrier', 'Financials')
FORBIDDEN = re.compile(r'\b(save|submit|create|delete|assign|update|change|edit|send|upload|note|pay|approve)\b', re.I)


class FieldProposal(Model):
    field: str | None = None
    section: str
    label: str
    control_type: str
    value_present: bool
    id_present: bool = False
    name_present: bool = False
    aria_label_present: bool = False
    selector: dict | None = None
    state: Literal['UNKNOWN', 'RECONCILED_FOR_1752'] = 'UNKNOWN'
    reason: str = 'no_unique_supported_mapping'
    evidence_references: list[str] = Field(default_factory=list)
    raw_vs_derived: Literal['FreightDesk-derived mapping of observed provider field'] = 'FreightDesk-derived mapping of observed provider field'


class AscendFieldContract(Model):
    provider: Literal['AscendTMS'] = 'AscendTMS'
    source: Literal['live browser DOM'] = 'live browser DOM'
    validation_load: Literal['1752'] = '1752'
    observed_at: AwareDatetime = Field(default_factory=utcnow)
    version: str
    tenant_identity: Literal['Booking Logistics'] = 'Booking Logistics'
    tenant_identity_source: Literal['OWNER_ATTESTED'] = 'OWNER_ATTESTED'
    fields: list[FieldProposal]
    observed_sections: list[str]
    unknown_control_count: int
    contract_state: Literal['PROPOSAL_SCOPED_TO_1752'] = 'PROPOSAL_SCOPED_TO_1752'
    live_validated: bool = False
    cross_process_session_reuse: bool = False


# Unknown labels and identifiers never leave the DOM. Values are returned only for approved field
# candidates, used privately in memory, then discarded; no HTML, notes, phone/password/hidden inputs.
SCAN = r'''({labels, identityOnly}) => {
    const visible = e => !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden';
    const output = [];
    const nodes = [...document.querySelectorAll('input:not([type="hidden"]):not([type="password"]),select,textarea,[role="textbox"],dt')];
    if (nodes.length > 250) return {overflow:true, fields:[]};
    for (const e of nodes) {
        if (!visible(e)) continue;
        const type = e.tagName === 'INPUT' ? (e.type || 'text') : e.tagName.toLowerCase();
        if (['submit','button','reset','file','password','hidden','checkbox','radio'].includes(type)) continue;
        let label = (e.getAttribute('aria-label') || (e.labels?.length === 1 ? e.labels[0].textContent : '') || '').trim();
        let valueNode = e;
        if (e.tagName === 'DT') { label = e.textContent.trim(); valueNode = e.nextElementSibling; }
        if (!valueNode || !visible(valueNode)) continue;
        const approved = Object.hasOwn(labels, label);
        if (identityOnly && (!approved || labels[label] !== 'load_number')) continue;
        const raw = valueNode.tagName === 'SELECT' ? valueNode.selectedOptions[0]?.textContent || '' :
            ('value' in valueNode ? valueNode.value : valueNode.textContent || '');
        output.push({label:approved ? label : '[unmapped label]', field:approved ? labels[label] : null,
            control_type:['text','number','email','tel','date','datetime-local','time','select','textarea','dt','div','span'].includes(type) ? type : 'other',
            value_present:!!raw.trim(), raw:approved && raw.length <= 2048 ? raw : null,
            id_present:e.hasAttribute('id'), name_present:e.hasAttribute('name'),
            aria_label_present:e.hasAttribute('aria-label'), accessible_label:approved && e.tagName !== 'DT'});
    }
    return {overflow:false, fields:output};
}'''


def propose_fields(rows: list[dict], section: str, evidence: list[ComparisonEvidence]) -> list[FieldProposal]:
    result = []
    for row in rows:
        field = row['field']
        proposal = FieldProposal(**{k:row[k] for k in ('field','label','control_type','value_present',
            'id_present','name_present','aria_label_present')}, section=section)
        if field is not None and row['accessible_label'] and sum(r['label'] == row['label'] for r in rows) == 1:
            proposal.selector = {'kind':'label', 'value':row['label'], 'exact':True}
        candidates = [r for r in rows if r['field'] == field]
        if field is None or len(candidates) != 1 or row['raw'] is None:
            result.append(proposal)
            continue
        normalized = normalize_field(field, row['raw'], 'observed detail DOM', section, utcnow()).normalized
        references = [e for e in evidence if e.load_number == '1752' and e.identity_reconciled and
                      e.source in {'Ascend history', 'CarrierView'} and e.fields.get(field) is not None]
        values = {e.fields[field] for e in references}
        if normalized and len(values) == 1 and normalized in values:
            proposal.state = 'RECONCILED_FOR_1752'
            proposal.reason = 'observed_label_and_value_match_existing_evidence_only'
            proposal.evidence_references = [e.evidence_reference for e in references]
        elif references:
            proposal.reason = 'existing_evidence_conflict_or_value_differs'
        else:
            proposal.reason = 'no_independent_value_evidence'
        result.append(proposal)
    return result


class ReadOnly1752Executor:
    """Closed operation surface: no generic click/submit/fill/script action supplied by a model/page."""
    def __init__(self, page, running, *, load_number='1752', authorized_loads=('1752',)):
        if not re.fullmatch(r'\d{1,20}', load_number) or load_number not in authorized_loads:
            raise AscendError('load_outside_discovered_scope')
        self._page = page
        self._running = running
        self._opened = False
        self.load_number = load_number

    async def guard(self):
        if not self._running():
            raise AscendError('discovery_policy_pause_or_expiry')
        if not (await observe_session(self._page, IdentityConfig(origin=ORIGIN))).session_authenticated:
            raise AscendError('discovery_session_not_authenticated')

    def frames(self):
        return [f for f in self._page.frames if f.url.split('?')[0].split('#')[0].startswith(ORIGIN+'/')]

    async def navigate_loads(self):
        await self.guard()
        await self._page.goto(ORIGIN+'/loads', wait_until='domcontentloaded', timeout=20000)
        deadline = time.monotonic()+15
        while time.monotonic() < deadline:
            if not self._running() or urlsplit(self._page.url).path.lower() == '/login.html':
                raise AscendError('discovery_session_not_authenticated')
            if (await observe_session(self._page, IdentityConfig(origin=ORIGIN))).session_authenticated:
                return
            await asyncio.sleep(0.25)  # Observe hydration only; never reload or retry a browser action.
        raise AscendError('discovery_session_not_authenticated')

    async def exact_matches(self):
        result = []
        for frame in self.frames():
            found = frame.get_by_text(self.load_number, exact=True)
            for i in range(await found.count()):
                if await found.nth(i).is_visible():
                    result.append(found.nth(i))
        return result

    async def find_1752(self):
        await self.guard()
        found = await self.exact_matches()
        if not found:
            # Only an observed list-search control may be filled. No Enter or submit action.
            searches = []
            for frame in self.frames():
                search = frame.get_by_role('searchbox')
                if await search.count() == 1 and await search.is_visible():
                    searches.append(search)
            if len(searches) == 1:
                await searches[0].fill(self.load_number)
                for frame in self.frames():
                    try:
                        await frame.get_by_text(self.load_number, exact=True).first.wait_for(state='visible', timeout=5000)
                    except Exception:
                        pass
                found = await self.exact_matches()
        if len(found) != 1:
            raise AscendError('exact_load_discovery_ambiguous_or_missing')
        return found[0]

    async def open_1752(self, before_open=None, *, inspect_control=None, before_click=None):
        await self.guard()
        target = await self.find_1752()
        opener = target.locator('xpath=ancestor-or-self::*[self::a or self::button or @role="link" or @role="button"][1]')
        if await opener.count() != 1:
            row = target.locator('xpath=ancestor::*[self::tr or @role="row"][1]')
            if await row.count() != 1:
                raise AscendError('exact_load_read_control_unknown')
            opener = row.get_by_role('link', name=re.compile(r'^(View|Details|Open|'+re.escape(self.load_number)+r')$'))
        if await opener.count() != 1:
            raise AscendError('exact_load_read_control_ambiguous')
        if inspect_control:
            await inspect_control(opener, target)
        info = await opener.evaluate('''e => ({tag:e.tagName, type:e.getAttribute('type'),
            inForm:!!e.closest('form'), name:(e.getAttribute('aria-label') || e.textContent || '').trim(),
            href:e.getAttribute('href')})''')
        if (info['name'] not in {self.load_number,'View','Details','Open'} or FORBIDDEN.search(info['name']) or
                info['type'] in {'submit','reset'} or (info['tag'] == 'BUTTON' and info['inForm'] and info['type'] != 'button')):
            raise AscendError('non_read_load_control_blocked')
        if info['href'] and not info['href'].startswith('#'):
            from urllib.parse import urljoin
            url = urlsplit(urljoin(self._page.url, info['href']))
            if (url.scheme+'://'+url.netloc != ORIGIN or url.username or url.password or
                    re.search(r'save|submit|create|delete|assign|update|change|send|upload|note|pay|approve',
                              url.path+' '+url.query, re.I)):
                raise AscendError('non_read_load_destination_blocked')
        if before_open:
            attributes = await opener.evaluate('''e => ({id_present:e.hasAttribute('id'),
                name_present:e.hasAttribute('name'),data_attribute_count:[...e.attributes].filter(a=>a.name.startsWith('data-')).length})''')
            before_open(info | attributes)
        if before_click:
            await before_click()
        await opener.click(timeout=5000)
        self._opened = True
        await self.guard()

    async def detail_identity(self):
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            await self.guard()
            identities = []
            for frame in self.frames():
                found = await frame.evaluate(SCAN, {'labels':LABELS, 'identityOnly':True})
                if found['overflow']:
                    raise AscendError('field_discovery_bound_exceeded')
                identities.extend((frame, r) for r in found['fields'])
            if identities:
                if len(identities) != 1 or identities[0][1]['raw'] is None or identities[0][1]['raw'].strip() != self.load_number:
                    raise AscendError('detail_load_identity_unverified')
                return identities[0]
            await asyncio.sleep(0.25)  # Allow lazy detail rendering; no second click or navigation.
        raise AscendError('detail_load_identity_unverified')

    async def scan(self, section):
        await self.guard()
        if not self._opened:
            raise AscendError('detail_not_opened')
        frame, identity = await self.detail_identity()
        # No non-identity values are read until the detail identity gate passes. Inspect only the
        # frame containing that identity, not other same-origin app/customer frames.
        found = await frame.evaluate(SCAN, {'labels':LABELS, 'identityOnly':False})
        if found['overflow']:
            raise AscendError('field_discovery_bound_exceeded')
        numbers = [r for r in found['fields'] if r['field'] == 'load_number']
        if len(numbers) != 1 or numbers[0]['raw'] != identity['raw']:
            raise AscendError('detail_identity_changed_during_scan')
        reread = await frame.evaluate(SCAN, {'labels':LABELS, 'identityOnly':False})
        if reread != found:
            raise AscendError('detail_fields_changed_during_scan')
        return found['fields']

    async def sections(self):
        result = []
        for frame in self.frames():
            for name in TABS:
                tab = frame.get_by_role('tab', name=name, exact=True)
                if await tab.count() > 1:
                    raise AscendError('ambiguous_read_tab')
                if await tab.count() == 1 and await tab.is_visible():
                    result.append((name, tab))
        if len(result) > 8:
            raise AscendError('read_section_bound_exceeded')
        return result

    async def inspect_section(self, name, tab):
        await self.guard()
        if name not in TABS:
            raise AscendError('section_action_not_allowed')
        safe = await tab.evaluate('''e => e.getAttribute('role') === 'tab' &&
            e.getAttribute('type') !== 'submit' && e.getAttribute('type') !== 'reset' &&
            !(e.tagName === 'BUTTON' && e.closest('form') && e.getAttribute('type') !== 'button') &&
            (!e.hasAttribute('href') || (e.getAttribute('href') || '').startsWith('#'))''')
        if not safe:
            raise AscendError('section_control_not_read_only')
        await tab.click(timeout=5000)
        return await self.scan(name)


async def discover_1752(page, evidence, *, running):
    executor = ReadOnly1752Executor(page, running)
    await executor.navigate_loads()
    await executor.open_1752()
    sections = ['Current detail']
    rows = await executor.scan(sections[0])
    fields = propose_fields(rows, sections[0], evidence)
    for name, tab in await executor.sections():
        if await tab.get_attribute('aria-selected') == 'true':
            continue
        rows = await executor.inspect_section(name, tab)
        sections.append(name)
        fields.extend(propose_fields(rows, name, evidence))
    await executor.guard()
    # Repeated field candidates across tabs are not silently merged or accepted as a reusable mapping.
    for field in fields:
        peers = [f for f in fields if f.field is not None and f.field == field.field]
        if len(peers) > 1:
            field.state = 'UNKNOWN'
            field.reason = 'multiple_observed_candidates_across_sections'
    stamp = utcnow()
    return AscendFieldContract(observed_at=stamp,
        version='observed-1752-'+digest({'at':stamp.isoformat(), 'fields':[f.model_dump() for f in fields]})[:16],
        fields=fields, observed_sections=sections, unknown_control_count=sum(f.field is None for f in fields))
