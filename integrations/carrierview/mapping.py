from datetime import datetime

from pydantic import AwareDatetime, Field

from app.models.domain import Model, Shipment, TrackingState
from integrations.carrierview.config import CredentialClass
from integrations.carrierview.errors import ContractMismatch
from integrations.carrierview.schemas import CarrierViewLoad, Position, aware_timestamp


class IdentityExpectation(Model):
    """Owner-provided UI identity comparison, never inferred from a matching load number alone."""
    provider_id: str
    booking_load_id: str
    origin_address: str
    destination_address: str
    pickup_appointment_raw: str
    delivery_appointment_raw: str
    pickup_appointment_utc: AwareDatetime
    delivery_appointment_utc: AwareDatetime
    driver_phone: str | None = None
    reviewed_by: str = Field(min_length=1)
    reviewed_at: AwareDatetime


def normalized(value):
    return " ".join(str(value).casefold().split())


def verify_load_identity(load: CarrierViewLoad, expected: IdentityExpectation) -> None:
    if load.id is None or str(load.id) != expected.provider_id:
        raise ContractMismatch("provider_load_identity_mismatch")
    if load.load_id is None or str(load.load_id) != expected.booking_load_id:
        raise ContractMismatch("booking_load_identity_mismatch")
    if expected.driver_phone is not None and load.driver_phone != expected.driver_phone:
        raise ContractMismatch("driver_identity_mismatch")
    pickups = [stop for stop in load.locations or [] if stop.type == "pickup"]
    destinations = [stop for stop in load.locations or [] if stop.type == "destination"]
    if len(pickups) != 1 or len(destinations) != 1:
        raise ContractMismatch("stop_identity_requires_manual_review")
    comparisons = [
        (pickups[0].address, expected.origin_address),
        (destinations[0].address, expected.destination_address),
        (pickups[0].dateFrom, expected.pickup_appointment_raw),
        (destinations[0].dateFrom, expected.delivery_appointment_raw),
    ]
    if any(actual is None or normalized(actual) != normalized(wanted) for actual, wanted in comparisons):
        raise ContractMismatch("stop_or_appointment_identity_mismatch")


def to_tracking(load: CarrierViewLoad, *, observed_at: datetime, credential_class: CredentialClass,
                last_position: Position | None = None, position_was_read: bool = False) -> TrackingState:
    # An explicit null from the dedicated endpoint supersedes a cached load position.
    position = last_position if position_was_read else load.last_position
    timestamp = aware_timestamp(position.timestamp) if position else None
    request_time = aware_timestamp(load.track_driver.last_request_time_utc) if load.track_driver else None
    parts = [part for part in [position.city, position.state] if part] if position else []
    metadata = {
        "provider_id": str(load.id) if load.id is not None else None,
        "booking_load_id": str(load.load_id) if load.load_id is not None else None,
        "integration_type": load.integration_type,
        "route_started": load.route_started,
        "app_status": load.track_driver.app_status if load.track_driver else None,
        "last_request_time_utc": load.track_driver.last_request_time_utc if load.track_driver else None,
        "driver_is_late": load.driver_is_late,
        "time_left_sec": load.time_left_sec,
        "distance_left_meters": load.distance_left_meters,
        "delivery_arrived": load.delivery_arrived,
        "delivery_departed": load.delivery_departed,
        "statuses": load.statuses,
        "locations": [location.model_dump(exclude_unset=True) for location in load.locations]
                     if load.locations is not None else None,
        "tracking_number_url": load.tracking_number_url,
        "client_url": load.client_url,
        "credential_class": credential_class.value,
        "last_sync_at": observed_at.isoformat(),
        "raw_load": load.model_dump(exclude_unset=True),
        "raw_position": position.model_dump(exclude_unset=True) if position else None,
        "position_timestamp_interpreted": timestamp is not None,
        "acceptance_semantics_verified": False,
    }
    return TrackingState(
        # No app status code/acceptance semantics were supplied. Do not equate route_started
        # or possession of a tracking URL with app acceptance or fresh tracking.
        status="UNKNOWN", requested=True if request_time else None, accepted=None,
        last_position_at=timestamp, location=", ".join(parts) if parts else None,
        latitude=position.latitude if position else None, longitude=position.longitude if position else None,
        eta=None, share_link=load.client_url, source="carrierview", verified_at=observed_at,
        provider_metadata=metadata,
    )


def to_shipment(load: CarrierViewLoad, canonical: Shipment, expected: IdentityExpectation, *,
                observed_at: datetime, credential_class: CredentialClass,
                last_position: Position | None = None, position_was_read=False) -> Shipment:
    verify_load_identity(load, expected)
    if canonical.demo:
        raise ValueError("A live import requires an owner-verified canonical record, not a demo template")
    if (canonical.booking_load_id != expected.booking_load_id
            or normalized(canonical.origin.location) != normalized(expected.origin_address)
            or normalized(canonical.destination.location) != normalized(expected.destination_address)):
        raise ContractMismatch("canonical_identity_mismatch")
    if (canonical.origin.appointment != expected.pickup_appointment_utc
            or canonical.destination.appointment != expected.delivery_appointment_utc):
        raise ContractMismatch("canonical_appointment_identity_mismatch")
    result = canonical.model_copy(deep=True)
    result.carrierview_load_id = expected.provider_id
    result.booking_load_id = expected.booking_load_id
    result.tracking = to_tracking(load, observed_at=observed_at, credential_class=credential_class,
                                  last_position=last_position, position_was_read=position_was_read)
    result.provider_metadata["carrierview"] = {
        "provider_id": expected.provider_id, "booking_load_id": expected.booking_load_id,
        "tracking_number_url": load.tracking_number_url, "client_url": load.client_url,
        "credential_class": credential_class.value, "last_sync_at": observed_at.isoformat(),
        "identity_reviewed_by": expected.reviewed_by, "identity_reviewed_at": expected.reviewed_at.isoformat(),
        "documents_capability": "UNSUPPORTED_UNKNOWN", "pod_capability": "UNSUPPORTED_UNKNOWN",
    }
    # CarrierView status enums/stop semantics are not yet mapped to the canonical lifecycle.
    # Keep the owner's verified canonical status rather than fabricating DELIVERED/POD/BILLING.
    result.version += 1
    result.last_action = "Verified CarrierView read imported"
    return result
