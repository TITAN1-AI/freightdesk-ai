from typing import Protocol

from app.models.domain import ExecutionResult


class VoiceProvider(Protocol):
    async def call(self, authorization_id: str, tenant_id: str, shipment_id: str,
                   purpose: str, contact_reference: str) -> ExecutionResult:
        """Future only; approved contact, legal review and bounded scope are required."""
        ...
