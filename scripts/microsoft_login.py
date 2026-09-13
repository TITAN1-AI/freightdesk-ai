"""Owner-run manual OAuth only, followed by exact mailbox verification."""
import asyncio

from app.core.runtime import RuntimePaths
from app.services.mail_view import graph_audit
from app.services.mail_settings import read_mailbox_settings
from app.services.store import Store
from integrations.outlook.adapter import MicrosoftGraphMailAdapter
from integrations.outlook.auth import MicrosoftAuth
from integrations.outlook.config import MicrosoftConfig


async def main():
    config = MicrosoftConfig.load()
    config.network_authorized = True  # Explicit execution of this private login helper is owner authorization.
    auth = MicrosoftAuth(config)
    token = await asyncio.to_thread(auth.login)
    store = Store(RuntimePaths.from_environment().path("Data", "booking-logistics", "mail.sqlite3"))
    try:
        async with MicrosoftGraphMailAdapter(config, lambda: token, graph_audit(store)) as adapter:
            await adapter.get_mailbox_profile()
            await read_mailbox_settings(adapter, store)
        with store.transaction():
            store.put("booking-logistics", "mail_connection", "microsoft",
                      {"status": "MAILBOX_VERIFIED", "profile_live_validated": True})
        print("Microsoft login succeeded; mailbox identity matched and settings read. No messages read or drafts created.")
    finally:
        store.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        raise SystemExit("Microsoft authentication stopped. Check registration, consent, mailbox type and manual sign-in.") from None
