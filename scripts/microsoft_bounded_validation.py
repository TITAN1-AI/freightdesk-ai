"""Run only after owner OAuth confirmation: 5 messages, at most 1 file, optional 1 unsent draft."""
import argparse
import asyncio

from app.core.runtime import RuntimePaths
from app.models.domain import ActionPolicy, AuthorizedIdentity, Role, Shipment
from app.services.mail_documents import ingest_attachment
from app.services.mail_drafts import create_durable_draft, grounded_draft
from app.services.mail_sync import MailSynchronizer
from app.services.mail_settings import read_mailbox_settings
from app.services.mail_view import graph_audit
from app.services.store import Store
from integrations.outlook.adapter import MicrosoftGraphMailAdapter
from integrations.outlook.auth import MicrosoftAuth
from integrations.outlook.config import MicrosoftConfig


async def main(create_draft=False):
    config = MicrosoftConfig.load()
    config.network_authorized = True
    config.drafts_authorized = create_draft
    paths = RuntimePaths.from_environment()
    store = Store(paths.path("Data", "booking-logistics", "mail.sqlite3"))
    canonical = Store(paths.path("Data", "booking-logistics", "carrierview.sqlite3"))
    try:
        shipments = [Shipment.model_validate(row) for row in canonical.all("booking-logistics", "shipment")]
        async with MicrosoftGraphMailAdapter(config, MicrosoftAuth(config).get_token, graph_audit(store)) as adapter:
            await adapter.get_mailbox_profile()
            await read_mailbox_settings(adapter, store)
            messages, _ = await adapter.list_recent_messages(5)
            count = await MailSynchronizer(store).ingest_recent(messages, shipments)
            files = 0
            for message in messages:
                if not message.hasAttachments:
                    continue
                attachments, _ = await adapter.get_attachments(message.id)
                eligible = [a for a in attachments if a.odata_type == "#microsoft.graph.fileAttachment"
                            and not a.isInline and a.size <= 10_000_000]
                if eligible:
                    content = await adapter.download_attachment(message.id, eligible[0])
                    ingest_attachment(store, message, eligible[0], content)
                    files = 1
                break
            state = "NOT_REQUESTED"
            if create_draft:
                actor = AuthorizedIdentity(id="owner", tenant_id="booking-logistics", role=Role.OWNER)
                result = await create_durable_draft(store, adapter, actor, ActionPolicy.ALLOW,
                    "microsoft-first-unsent-draft", grounded_draft(config.mailbox))
                state = result["state"]
            print(f"Mailbox verified; discovered/processed: {count}; attachments stored: {files}; unsent draft: {state}. No send.")
    finally:
        store.close()
        canonical.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-unsent-draft", action="store_true")
    options = parser.parse_args()
    try:
        asyncio.run(main(options.create_unsent_draft))
    except Exception:
        raise SystemExit("Bounded Microsoft validation stopped; consult redacted local audit. No automatic retry.") from None
