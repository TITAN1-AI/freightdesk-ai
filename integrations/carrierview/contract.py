from typing import Literal

from pydantic import Field

from app.models.domain import Model
from integrations.carrierview.errors import ContractMismatch

ReadCapability = Literal["profile", "integration_types", "loads", "load", "last_position", "positions_history"]


class ResponseContract(Model):
    """Explicit response selectors avoid guessing undocumented response envelope nesting.

    Fill from the full official reference. Fixture contracts must remain labeled as fixtures.
    Selectors name object keys only; empty tuple selects the entire success envelope.
    """
    source_reference: str = Field(min_length=1)
    verified_for_network: bool = False
    selectors: dict[ReadCapability, tuple[str, ...]]
    create_result_selector: tuple[str, ...] | None = None

    def extract(self, capability: str, envelope: dict):
        if capability not in self.selectors:
            raise ContractMismatch("response_selector_missing")
        value = envelope
        for key in self.selectors[capability]:
            if not isinstance(value, dict) or key not in value:
                raise ContractMismatch("response_shape_mismatch")
            value = value[key]
        return value

    def created_record(self, envelope):
        if self.create_result_selector is None:
            raise ContractMismatch("creation_response_selector_missing", uncertain=True)
        value = envelope
        for key in self.create_result_selector:
            if not isinstance(value, dict) or key not in value:
                raise ContractMismatch("creation_response_shape_mismatch", uncertain=True)
            value = value[key]
        if not isinstance(value, dict) or not isinstance(value.get("id"), (str, int)):
            raise ContractMismatch("created_provider_id_missing", uncertain=True)
        return value
