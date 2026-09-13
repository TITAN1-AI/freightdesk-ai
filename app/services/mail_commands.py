import re
from typing import Literal

from app.models.domain import AuthorizedIdentity, Model, Role
from app.services.mail_sync import digest


class VerifiedSender(Model):
    tenant_id: str
    address: str
    message_id: str
    content_hash: str
    method: Literal["OWNER_REVIEW", "VERIFIED_GATEWAY", "SMIME"]
    verified: bool = False


def owner_command(event, proof: VerifiedSender, identities: dict[str, AuthorizedIdentity], read_handler):
    address = event.message.from_.emailAddress.address.casefold() if event.message.from_ else ""
    actor = identities.get(address)
    if (not proof.verified or proof.tenant_id != event.tenant_id or proof.address.casefold() != address
            or proof.message_id != event.message.id or proof.content_hash != digest(event.message.model_dump(mode="json"))
            or actor is None or actor.tenant_id != event.tenant_id
            or actor.role not in {Role.OWNER, Role.OPERATIONS_USER}):
        raise PermissionError("Verified sender identity and owner/operations authorization required")
    command = event.message.body.content.strip()
    # No mutations are dispatched by email, even for an owner.
    if not re.fullmatch(r"(?:status\s+\d+|at risk|missing pod|deliveries today|pickups tomorrow)", command, re.I):
        return {"action": "REVIEW_REQUIRED", "executed": False}
    return {"action": "READ_ONLY_COMMAND", "executed": True, "result": read_handler(actor, command)}
