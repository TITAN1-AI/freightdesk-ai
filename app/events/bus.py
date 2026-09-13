from typing import Protocol

from app.models.domain import AuthorizedIdentity, ExternalEvent


class EventBus(Protocol):
    """Accept trusted normalized events; inbound vendor webhooks need signature verification first."""

    def process_event(self, identity: AuthorizedIdentity, event: ExternalEvent) -> dict: ...
