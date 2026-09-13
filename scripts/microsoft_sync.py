"""Owner-run bounded delta polling. No registration, interactive login, drafts or sends."""
import asyncio

from app.core.runtime import RuntimePaths
from app.models.domain import Shipment
from app.services.mail_sync import MailSynchronizer
from app.services.mail_view import graph_audit
from app.services.store import Store
from integrations.outlook.adapter import MicrosoftGraphMailAdapter
from integrations.outlook.auth import MicrosoftAuth
from integrations.outlook.config import MicrosoftConfig


async def main():
    config = MicrosoftConfig.load()
    config.network_authorized = True
    paths = RuntimePaths.from_environment()
    mail = Store(paths.path('Data', 'booking-logistics', 'mail.sqlite3'))
    canonical = Store(paths.path('Data', 'booking-logistics', 'carrierview.sqlite3'))
    try:
        shipments = [Shipment.model_validate(row) for row in canonical.all('booking-logistics', 'shipment')]
        async with MicrosoftGraphMailAdapter(config, MicrosoftAuth(config).get_token, graph_audit(mail)) as adapter:
            result = await MailSynchronizer(mail).sync(adapter, shipments, max_pages=2)
        print(f"Delta pages bounded to 2; processed={result['processed']}; round_complete={result['round_complete']}.")
    finally:
        mail.close()
        canonical.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception:
        raise SystemExit('Bounded sync stopped. Check redacted audit; no automatic retry or cursor reset.') from None
