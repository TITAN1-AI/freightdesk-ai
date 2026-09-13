from datetime import timedelta

from pydantic import SecretStr

from app.models.domain import utcnow
from app.services.demo import demo_shipments
from integrations.carrierview.config import CarrierViewConfig
from integrations.carrierview.contract import ResponseContract
from integrations.carrierview.mapping import IdentityExpectation
from integrations.carrierview.schemas import CarrierViewLoad

PROVIDER_ID = "fixture-provider-001"


def config(**kwargs):
    return CarrierViewConfig(api_token=SecretStr("SYNTHETIC-AGENT-TOKEN"),
                             base_url="https://carrierview.example.invalid", **kwargs)


def contract():
    return ResponseContract(source_reference="SYNTHETIC FIXTURE; envelope is not vendor-verified",
        selectors={key: ("data",) for key in ["profile", "integration_types", "loads", "load",
                                             "last_position", "positions_history"]},
        create_result_selector=("data",))


def provider_load():
    now = utcnow()
    return {
        "id": PROVIDER_ID, "load_id": "TEST-1847", "integration_type": "carrier_view",
        "driver_phone": "+15550100000", "route_started": True,
        "track_driver": {"app_status": "fixture_unknown_code", "last_request_time_utc": now.isoformat()},
        "driver_is_late": False, "time_left_sec": 3600, "distance_left_meters": 80000,
        "delivery_arrived": None, "delivery_departed": False, "statuses": {"opaque": None},
        "locations": [
            {"type": "pickup", "address": "Fixture origin", "dateFrom": (now - timedelta(hours=3)).isoformat()},
            {"type": "destination", "address": "Fixture destination", "dateFrom": (now + timedelta(hours=3)).isoformat()},
        ],
        "last_position": {"latitude": 33.1, "longitude": -95.2, "city": "Fixture City", "state": "TX",
                          "timestamp": (now - timedelta(minutes=5)).isoformat(), "unknown_field": None},
        "tracking_number_url": "https://example.invalid/driver-link",
        "client_url": "https://example.invalid/client-link", "future_null_field": None,
    }


def plan_parts():
    value = provider_load()
    load = CarrierViewLoad.model_validate(value)
    canonical = demo_shipments("booking-logistics")[0]
    canonical.id, canonical.demo, canonical.booking_load_id = "fixture-canonical-001", False, "TEST-1847"
    canonical.origin.location, canonical.destination.location = "Fixture origin", "Fixture destination"
    from datetime import datetime
    canonical.origin.appointment = datetime.fromisoformat(value["locations"][0]["dateFrom"])
    canonical.destination.appointment = datetime.fromisoformat(value["locations"][1]["dateFrom"])
    expectation = IdentityExpectation(
        provider_id=PROVIDER_ID, booking_load_id="TEST-1847", origin_address="Fixture origin",
        destination_address="Fixture destination", pickup_appointment_raw=value["locations"][0]["dateFrom"],
        delivery_appointment_raw=value["locations"][1]["dateFrom"],
        pickup_appointment_utc=canonical.origin.appointment, delivery_appointment_utc=canonical.destination.appointment,
        driver_phone="+15550100000", reviewed_by="fixture-owner", reviewed_at=utcnow())
    return load, canonical, expectation
