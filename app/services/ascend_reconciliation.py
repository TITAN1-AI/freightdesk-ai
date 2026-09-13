"""Comparison is derived evidence, never an instruction to modify canonical state."""
from datetime import timedelta

from app.models.domain import utcnow
from integrations.ascend.models import FIELDS, AscendObservation, ComparisonEvidence


def reconcile(observation: AscendObservation, sources: list[ComparisonEvidence], now=None):
    now = now or utcnow()
    rows = []
    for source_name in ['canonical', 'CarrierView', 'Outlook', 'Ascend history']:
        matches = [s for s in sources if s.source == source_name and s.load_number == observation.load_number
                   and s.identity_reconciled]
        source = matches[0] if len(matches) == 1 else None
        for field in FIELDS:
            live = observation.fields[field]
            other = source.fields.get(field) if source else None
            stale = bool(source and (source_name == 'Ascend history' or not source.observed_at or
                now-source.observed_at > timedelta(hours=24) or source.observed_at > now))
            if not source or live.availability == 'UNAVAILABLE':
                status = 'UNAVAILABLE'
            elif live.normalized is None or other is None:
                status = 'UNKNOWN'
            elif stale or now-observation.observed_at > timedelta(hours=24):
                status = 'STALE'
            elif live.normalized == other:
                status = 'MATCH'
            else:
                status = 'DIFFERENT'
            rows.append({'field': field, 'comparison_source': source_name, 'status': status,
                'evidence_reference': source.evidence_reference if source else None,
                'comparison_observed_at': source.observed_at.isoformat() if source and source.observed_at else None,
                'live_observed_at': observation.observed_at.isoformat(), 'calculated_at': now.isoformat(),
                'raw_vs_derived': 'FreightDesk-derived comparison; provider values retained separately',
                'staleness_rule': 'historical evidence or older than 24 hours is not current-state proof'})
    return rows
