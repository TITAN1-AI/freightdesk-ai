import os
from enum import StrEnum
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator

from app.models.domain import Model


class CredentialClass(StrEnum):
    AGENT = "agent"
    TENANT = "tenant"


class CarrierViewConfig(Model):
    api_token: SecretStr = Field(repr=False)
    base_url: str
    credential_class: CredentialClass = CredentialClass.AGENT
    tenant_id: str = "booking-logistics"
    elevation_reason: str | None = None
    origin_verified: bool = False
    network_reads_authorized: bool = False
    discovery_reads_authorized: bool = False
    discovery_provider_id: str | None = None
    timeout_seconds: float = Field(default=15, gt=0, le=30)
    max_response_bytes: int = Field(default=2_000_000, gt=0, le=10_000_000)

    @field_validator("base_url")
    @classmethod
    def https_origin(cls, value):
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in {"", "/"}
                or parsed.port not in {None, 443}):
            raise ValueError("CARRIERVIEW_BASE_URL must be the documented HTTPS origin without path or credentials")
        return value.rstrip("/")

    @classmethod
    def from_environment(cls, credential_class: CredentialClass = CredentialClass.AGENT,
                         elevation_reason: str | None = None):
        selected = CredentialClass(credential_class)
        variable = f"CARRIERVIEW_{selected.value.upper()}_API_TOKEN"
        token = os.getenv(variable, "")
        if not token:
            raise ValueError(f"{variable} required; use the private DPAPI helper")
        if selected == CredentialClass.TENANT and not elevation_reason:
            raise ValueError("Tenant credential requires an explicit elevation reason")
        return cls(api_token=SecretStr(token), base_url=os.getenv("CARRIERVIEW_BASE_URL", ""),
                   credential_class=selected, elevation_reason=elevation_reason,
                   origin_verified=os.getenv("CARRIERVIEW_ORIGIN_VERIFIED") == "true",
                   network_reads_authorized=os.getenv("CARRIERVIEW_READS_AUTHORIZED") == "true")
