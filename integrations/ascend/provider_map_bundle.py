"""Metadata handoff to the existing assembler, not a shipment execution interface."""
from dataclasses import dataclass
from typing import Literal, Sequence
from executors.ascend_extension.workspace_contracts import AscendProviderMap
from integrations.ascend.context_assembler import AscendLoadContextAssembler, ReadMappingValidation, VerifiedProviderObservation

ProviderMapMaturity = Literal['UNKNOWN', 'OBSERVED', 'REVIEWED_NAVIGATION', 'AUTO_MAP_VALIDATED', 'READ_MAPPING_VALIDATED', 'WRITE_MAPPING_VALIDATED']


@dataclass(frozen=True)
class ProviderMapBundle:
    maps: tuple[AscendProviderMap, ...]
    maturity: ProviderMapMaturity
    provider: Literal['AscendTMS'] = 'AscendTMS'

    def __post_init__(self):
        if self.maturity not in {'UNKNOWN','OBSERVED','REVIEWED_NAVIGATION','AUTO_MAP_VALIDATED'}:
            raise PermissionError('READ_MAPPING_UNVERIFIED')
        for m in self.maps:
            AscendProviderMap.model_validate(m)

    def assemble(self, load_id: str, assembler: AscendLoadContextAssembler, *, now: float,
                 observations: Sequence[VerifiedProviderObservation] = (), validations: Sequence[ReadMappingValidation] = ()) -> dict:
        matches = [m for m in self.maps if m.workspace.load_id == load_id]
        if not matches:
            raise PermissionError('WORKSPACE_IDENTITY_MISSING')
        current = max(matches, key=lambda m: m.workspace.observed_at)
        return assembler.assemble(current, matches, observations, validations, now=now)
