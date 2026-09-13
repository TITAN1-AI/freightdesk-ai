"""Store mailbox preferences as timestamp-interpretation context, never shipment facts."""
from app.models.domain import utcnow


async def read_mailbox_settings(adapter, store, tenant="booking-logistics"):
    settings = await adapter.get_mailbox_settings()
    record = {"mailbox": adapter.config.mailbox, "source": "microsoft_graph",
              "source_operation": "GET /me/mailboxSettings", "observed_at": utcnow().isoformat(),
              "settings": settings.model_dump(mode="json"), "fixture": adapter.fixture,
              "live_validated": not adapter.fixture,
              "interpretation": "MAILBOX_PREFERENCES_ONLY; freight timezone/date/AM-PM require source evidence"}
    with store.transaction():
        store.put(tenant, "mail_settings", "microsoft", record)
    return record
