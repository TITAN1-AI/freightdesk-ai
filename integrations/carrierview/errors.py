from dataclasses import dataclass, field
from typing import Any

KNOWN_CODES = {
    "user_not_found", "company_not_found", "company_disabled", "load_not_found", "permission_denied",
    "required_fields_errors", "creation_error", "driver_opted_out", "sms_provider_failed", "internal_error",
}


@dataclass
class CarrierViewError(Exception):
    code: str
    http_status: int | None = None
    uncertain: bool = False
    retry_after_seconds: int | None = None
    errors: Any = field(default=None, repr=False)

    def __str__(self):
        return f"CarrierView request failed: {self.code}"

    def safe_result(self):
        return {"error_code": self.code, "http_status": self.http_status,
                "uncertain": self.uncertain, "retry_after_seconds": self.retry_after_seconds,
                "has_validation_errors": self.errors is not None}


class ScopeElevationRequired(CarrierViewError):
    """Explicit credential selection required; automatic tenant fallback is prohibited."""


class ContractMismatch(CarrierViewError):
    pass
