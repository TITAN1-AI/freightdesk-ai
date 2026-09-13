"""Read-context interface. Mapping mode does not collect or persist these private values."""

from dataclasses import dataclass
from math import isfinite
from typing import Protocol, Sequence

from executors.ascend_extension.workspace_contracts import AscendFieldContract, AscendProviderMap

DOMAINS = ("identity", "status", "references", "customer", "carrier", "driver", "assets", "equipment",
           "commodity", "stops", "appointments", "tracking", "documents", "load_log", "financials")

# Application-owned meanings, never selected by a browser observation's domain string.
FIELD_DOMAINS = {field: domain for domain, fields in {
    'status': ('status',), 'references': ('reference', 'customer_reference', 'carrier_reference'),
    'customer': ('customer', 'bill_to'), 'carrier': ('carrier', 'dispatcher', 'dispatcher_contact'),
    'driver': ('driver', 'driver_contact'), 'assets': ('truck', 'trailer'), 'equipment': ('equipment',),
    'commodity': ('commodity', 'weight', 'pieces', 'quantity'),
    'stops': ('pickup', 'delivery', 'facility', 'address', 'city', 'state', 'postal_code'),
    'appointments': ('appointment', 'appointment_date', 'appointment_time', 'arrival', 'departure'),
    'tracking': ('tracking', 'tracking_status'), 'documents': ('document_type', 'document_status'),
    'load_log': ('load_log',), 'financials': ('total_income', 'total_expenses', 'gross_profit', 'currency'),
}.items() for field in fields}


def _finite_number(value):
    return type(value) in (int, float) and isfinite(value)


@dataclass(frozen=True)
class ReadMappingValidation:
    contract_fingerprint: str
    evidence_reference: str
    evidence_level: str

    @classmethod
    def controlled_comparison(cls, field: AscendFieldContract, evidence_reference: str, *, matched=False, owner_authorized=False):
        if (owner_authorized is not True or matched is not True or field.evidence_level not in {"LEVEL_1", "LEVEL_2"}
            or field.field_name_candidate == "UNKNOWN" or not evidence_reference):
            raise PermissionError("READ_MAPPING_UNVERIFIED")
        # Trusted application interface only, not exposed to extension messages or mapping artifacts.
        return cls(field.contract_fingerprint, evidence_reference, field.evidence_level)


@dataclass(frozen=True)
class VerifiedProviderObservation:
    load_id: str
    domain: str
    field: str
    contract_fingerprint: str
    value: str | int | float | bool | None
    observed_at: float
    source: str = "AscendTMS provider DOM"


class AscendLoadContextAssembler(Protocol):
    def assemble(self, current: AscendProviderMap, sections: Sequence[AscendProviderMap],
                 observations: Sequence[VerifiedProviderObservation], validations: Sequence[ReadMappingValidation],
                 *, now: float, max_age_seconds: float = 300) -> dict: ...


class VerifiedAscendLoadContextAssembler:
    def assemble(self, current, sections, observations, validations, *, now, max_age_seconds=300):
        current = AscendProviderMap.model_validate(current)
        if not _finite_number(now) or not _finite_number(max_age_seconds) or not 0 < max_age_seconds <= 3600:
            raise ValueError("CONTEXT_FRESHNESS_INVALID")
        output = {d: {"value": None, "source": None, "observed_at": None, "freshness": "UNKNOWN",
                      "evidence_level": None, "confidence": "UNKNOWN"} for d in DOMAINS}
        if not 0 <= now - current.workspace.observed_at <= max_age_seconds:
            return output
        output["identity"] = {"value": current.workspace.load_id, "source": "AscendTMS provider DOM",
            "observed_at": current.workspace.observed_at, "freshness": "FRESH", "evidence_level": "LEVEL_1", "confidence": "VERIFIED"}
        latest = {}
        for raw in [*sections, current]:
            m = AscendProviderMap.model_validate(raw)
            if (m.workspace.load_id != current.workspace.load_id
                or m.workspace.shell_fingerprint != current.workspace.shell_fingerprint
                or not 0 <= now - m.workspace.observed_at <= max_age_seconds):
                continue
            previous = latest.get(m.section.section)
            if previous is None or previous.workspace.observed_at <= m.workspace.observed_at:
                latest[m.section.section] = m
        fields = {f.contract_fingerprint: f for m in latest.values() for f in m.section.fields}
        approved = {v.contract_fingerprint: v for v in validations}
        grouped = {}
        for o in observations:
            if (not isinstance(o, VerifiedProviderObservation) or type(o.field) is not str or type(o.domain) is not str
                or type(o.contract_fingerprint) is not str or not _finite_number(o.observed_at)
                or type(o.value) not in (str, int, float, bool) or type(o.value) is float and not isfinite(o.value)):
                continue
            f, v = fields.get(o.contract_fingerprint), approved.get(o.contract_fingerprint)
            if (o.load_id != current.workspace.load_id or o.domain not in DOMAINS or o.domain == "identity"
                or FIELD_DOMAINS.get(o.field) != o.domain
                or o.source != "AscendTMS provider DOM" or f is None or v is None or f.field_name_candidate != o.field
                or v.evidence_level not in {"LEVEL_1", "LEVEL_2"} or v.evidence_level != f.evidence_level
                or not v.evidence_reference
                or not 0 <= now - o.observed_at <= max_age_seconds):
                continue
            grouped.setdefault(o.domain, []).append(o)
        for domain, items in grouped.items():
            # Conflicting values for a field remain UNKNOWN; never pick a convenient source silently.
            if len({o.field for o in items}) != len(items):
                continue
            output[domain] = {"value": {o.field: o.value for o in items}, "source": "AscendTMS provider DOM",
                "observed_at": min(o.observed_at for o in items), "freshness": "FRESH",
                "evidence_level": "LEVEL_2" if any(approved[o.contract_fingerprint].evidence_level == "LEVEL_2" for o in items) else "LEVEL_1",
                "confidence": "VERIFIED"}
        return output
