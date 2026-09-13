import os
import re
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    tenant: str = "booking-logistics"
    mode: str = "demo"
    timezone: str = "America/Guatemala"
    stale_minutes: int = 30
    escalation_minutes: int = 60
    model_provider: str = "openai"
    model: str = "gpt-5.6-sol"

    def __post_init__(self):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", self.tenant):
            raise ValueError("Invalid tenant identifier")
        if self.mode != "demo":
            raise ValueError("This milestone only supports demo mode; live connectors are not enabled")
        ZoneInfo(self.timezone)

    @classmethod
    def from_env(cls):
        return cls(tenant=os.getenv("FREIGHTDESK_TENANT", "booking-logistics"),
                   mode=os.getenv("FREIGHTDESK_MODE", "demo"),
                   timezone=os.getenv("FREIGHTDESK_TIMEZONE", "America/Guatemala"),
                   model_provider=os.getenv("FREIGHTDESK_MODEL_PROVIDER", "openai"),
                   model=os.getenv("FREIGHTDESK_MODEL", "gpt-5.6-sol"))
