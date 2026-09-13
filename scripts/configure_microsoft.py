"""Owner-run non-secret Entra registration configuration. Makes no network request."""
import warnings
from getpass import GetPassWarning, getpass
from app.core.runtime import RuntimePaths
from integrations.outlook.config import MicrosoftConfig

try:
    # Fail instead of falling back to echoed input when no secure console is available.
    with warnings.catch_warnings():
        warnings.simplefilter("error", GetPassWarning)
        config = MicrosoftConfig(tenant_id=getpass("Directory (tenant) ID (hidden local input): ").strip(),
                                 client_id=getpass("Application (client) ID (hidden local input): ").strip())
    path = RuntimePaths.from_environment().path("Data", "booking-logistics", "microsoft-config.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    print("Non-secret Microsoft configuration saved under the approved runtime. No login or network request occurred.")
except Exception:
    raise SystemExit("Microsoft configuration not saved; use a private interactive console and valid registration identifiers.") from None
