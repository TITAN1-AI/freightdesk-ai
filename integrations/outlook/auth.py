"""MSAL public-client OAuth and Windows DPAPI cache; no plaintext fallback."""
import os

from pydantic import SecretStr

from app.core.runtime import RuntimePaths
from integrations.outlook.config import SCOPES


def encrypted_cache(paths=None):
    from msal_extensions import FilePersistenceWithDataProtection, PersistedTokenCache
    if os.name != "nt":
        raise PermissionError("This deployment requires Windows DPAPI; plaintext fallback is disabled")
    paths = paths or RuntimePaths.from_environment()
    path = paths.path("Tokens", "Microsoft", "msal-cache.bin")
    paths.path("Tokens", "Microsoft", "msal-cache.bin.lockfile")
    path.parent.mkdir(parents=True, exist_ok=True)
    persistence = FilePersistenceWithDataProtection(str(path))
    if not persistence.is_encrypted:
        raise PermissionError("Encrypted token cache required")
    return PersistedTokenCache(persistence)


class MicrosoftAuth:
    def __init__(self, config):
        self.config = config
        self._app = None

    def application(self):
        if not self.config.network_authorized:
            raise PermissionError("Owner Microsoft authentication/network authorization required")
        if self._app is None:
            from msal import PublicClientApplication
            self._app = PublicClientApplication(str(self.config.client_id), authority=self.config.authority,
                                                token_cache=encrypted_cache(), enable_pii_log=False)
        return self._app

    def login(self):
        result = self.application().acquire_token_interactive(
            scopes=SCOPES, login_hint=self.config.mailbox, prompt="select_account", timeout=300)
        if "access_token" not in result:
            raise PermissionError("Microsoft interactive authentication did not complete")
        claims = result.get("id_token_claims", {})
        if str(claims.get("tid", "")).lower() != str(self.config.tenant_id).lower():
            raise PermissionError("Microsoft tenant mismatch")
        # /me verification is still required before mail reads; UPN may differ from mail.
        return SecretStr(result["access_token"])

    def get_token(self):
        app = self.application()
        accounts = [a for a in app.get_accounts() if
                    a.get("username", "").casefold() == self.config.mailbox.casefold()
                    and a.get("realm", "").casefold() == str(self.config.tenant_id).casefold()]
        if len(accounts) != 1:
            raise PermissionError("Manual login to the dedicated organizational mailbox is required")
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if not result or "access_token" not in result:
            raise PermissionError("Manual Microsoft reauthentication required")
        return SecretStr(result["access_token"])
