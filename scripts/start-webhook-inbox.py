"""Local normalized-event inbox only. No public bind or provider registration."""
import os

import uvicorn
from pydantic import SecretStr

from app.events.carrierview_webhooks import create_webhook_app

if __name__ == "__main__":
    if not all(os.getenv(name) for name in [
        "FREIGHTDESK_LOCAL_INGRESS_KEY", "CARRIERVIEW_EXPECTED_USER_ID", "CARRIERVIEW_EXPECTED_COMPANY_ID"
    ]):
        raise SystemExit("Configure the local ingress key and verified account association first.")
    app = create_webhook_app(local_test_key=SecretStr(os.environ["FREIGHTDESK_LOCAL_INGRESS_KEY"]),
        tenant="booking-logistics", provider_user_id=os.environ["CARRIERVIEW_EXPECTED_USER_ID"],
        provider_company_id=os.environ["CARRIERVIEW_EXPECTED_COMPANY_ID"])
    uvicorn.run(app, host="127.0.0.1", port=8788, access_log=False)
