from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.runtime import RuntimePaths
from app.models.domain import Model

# Owner-reported registration metadata only; NEVER use this list to acquire tokens.
ENTRA_CONFIGURED_PERMISSIONS = ("User.Read", "Mail.ReadWrite", "MailboxSettings.Read", "Mail.Send")
# Explicit current-session allowlist. No .default or registration-derived scope expansion.
SCOPES = ["User.Read", "Mail.ReadWrite", "MailboxSettings.Read"]
# MSAL also adds openid/profile/offline_access. Neither scopes nor provisioning grant ActionPolicy approval.


class MicrosoftConfig(Model):
    tenant_id: UUID = Field(repr=False)
    client_id: UUID = Field(repr=False)
    mailbox: Literal["info@bookinglogistic.com"] = "info@bookinglogistic.com"
    redirect_uri: Literal["http://localhost"] = "http://localhost"
    network_authorized: bool = False
    drafts_authorized: bool = False

    @property
    def authority(self):
        return "https://login.microsoftonline.com/" + str(self.tenant_id)

    @classmethod
    def config_path(cls):
        return RuntimePaths.from_environment().path("Data", "booking-logistics", "microsoft-config.json")

    @classmethod
    def load(cls):
        return cls.model_validate_json(cls.config_path().read_text(encoding="utf-8-sig"))
