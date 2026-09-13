"""Typed fields from the owner-supplied contract.

Response nesting and some field sub-shapes are not supplied. Unknown provider fields
are retained (including explicit nulls); the transport exposes a raw envelope alongside
typed data. Fixture payloads are engineering examples, not captured vendor responses.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.models.domain import Model


class ProviderRecord(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)


class Profile(ProviderRecord):
    id: str | int | None = None
    user_id: str | int | None = None
    company_id: str | int | None = None


class Position(ProviderRecord):
    # Position field names/sub-shapes require account response verification.
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timestamp: str | int | float | None = None
    city: str | None = None
    state: str | None = None


class TrackDriver(ProviderRecord):
    app_status: str | int | None = None
    last_request_time_utc: str | int | float | None = None


class Location(ProviderRecord):
    type: str | None = None
    address: str | None = None
    dateFrom: str | None = None
    dateTo: str | None = None
    arrived: bool | str | None = None
    departed: bool | str | None = None


class CarrierViewLoad(ProviderRecord):
    id: str | int | None = None
    load_id: str | int | None = None
    integration_type: str | None = None
    driver_phone: str | None = None
    route_started: bool | None = None
    track_driver: TrackDriver | None = None
    driver_is_late: bool | None = None
    time_left_sec: int | float | None = Field(default=None, ge=0)
    distance_left_meters: int | float | None = Field(default=None, ge=0)
    delivery_arrived: bool | str | None = None
    delivery_departed: bool | str | None = None
    statuses: Any = None
    locations: list[Location] | None = None
    last_position: Position | None = None
    tracking_number_url: str | None = None
    client_url: str | None = None


class ProviderEnvelope(ProviderRecord):
    success: StrictBool
    error_code: str | None = None
    errors: Any = None


class CreateLocation(Model):
    type: Literal["pickup", "destination"]
    address: str = Field(min_length=1, max_length=1000)
    dateFrom: str | None = None
    dateTo: str | None = None


class CreateTrackingLoad(Model):
    integration_type: Literal["carrier_view"] = "carrier_view"
    driver_phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    load_id: str = Field(min_length=1, max_length=100)
    locations: list[CreateLocation] = Field(min_length=2, max_length=100)
    starts_active: bool | None = None
    emails: list[str] | None = None
    dispatchers: list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def both_stops(self):
        if not {"pickup", "destination"} <= {s.type for s in self.locations}:
            raise ValueError("Tracking creation requires pickup and destination")
        return self


class EditLoad(Model):
    driver_phone: str | None = Field(default=None, pattern=r"^\+[1-9]\d{7,14}$")
    load_id: str | None = None
    locations: list[CreateLocation] | None = None
    starts_active: bool | None = None
    emails: list[str] | None = None
    dispatchers: list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def not_empty(self):
        if not self.model_fields_set:
            raise ValueError("Edit payload cannot be empty")
        return self


class DriverTextMessage(Model):
    message_type: Literal["welcome", "assigned_load", "one_time_ping_request", "installation_guide", "custom"]
    message: str | None = Field(default=None, min_length=1, max_length=480)

    @model_validator(mode="after")
    def custom_message(self):
        if self.message_type == "custom" and (not self.message or not self.message.strip()):
            raise ValueError("Custom SMS requires a nonempty message of at most 480 characters")
        return self


class DriverChatMessage(Model):
    message: str = Field(min_length=1, max_length=10_000)


class WebhookConfiguration(Model):
    event: Literal["new-position-sent", "chat-message-created-by-driver", "load-status-changed"]
    url: str

    @model_validator(mode="after")
    def public_https_only(self):
        from urllib.parse import urlsplit
        parsed = urlsplit(self.url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.fragment or parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
            raise ValueError("Future webhook target requires a dedicated verified HTTPS ingress")
        return self


def aware_timestamp(value: str | int | float | None) -> datetime | None:
    # Numeric timestamps have unspecified units; don't guess seconds vs milliseconds.
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo and result.utcoffset() is not None else None
    except ValueError:
        return None
