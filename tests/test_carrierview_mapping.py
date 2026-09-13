import pytest

from app.models.domain import utcnow
from integrations.carrierview.config import CredentialClass
from integrations.carrierview.errors import ContractMismatch
from integrations.carrierview.mapping import to_shipment, to_tracking, verify_load_identity
from tests.carrierview_fixtures import plan_parts


def test_mapping_preserves_provider_id_booking_id_null_and_timestamps():
    load, canonical, expected = plan_parts()
    result = to_shipment(load, canonical, expected, observed_at=utcnow(), credential_class=CredentialClass.AGENT)
    assert result.carrierview_load_id == expected.provider_id
    assert result.booking_load_id == "TEST-1847"
    assert result.tracking.provider_metadata["raw_load"]["future_null_field"] is None
    assert result.tracking.provider_metadata["raw_position"]["unknown_field"] is None
    assert result.tracking.last_position_at.isoformat() == load.last_position.timestamp
    assert result.tracking.eta is None
    assert result.tracking.accepted is None and result.tracking.status == "UNKNOWN"
    assert result.status == canonical.status


def test_request_timestamp_is_not_tracking_freshness():
    load, _, _ = plan_parts()
    load.last_position.timestamp = "2026-09-07 12:00:00"  # no supplied timezone semantics
    result = to_tracking(load, observed_at=utcnow(), credential_class=CredentialClass.AGENT)
    assert result.last_position_at is None
    assert result.provider_metadata["raw_position"]["timestamp"] == "2026-09-07 12:00:00"


def test_explicit_null_position_does_not_fall_back_to_cached_position():
    load, _, _ = plan_parts()
    result = to_tracking(load, observed_at=utcnow(), credential_class=CredentialClass.AGENT,
                         last_position=None, position_was_read=True)
    assert result.location is None and result.last_position_at is None


@pytest.mark.parametrize("field", ["id", "load_id", "driver_phone"])
def test_identity_mismatch_rejected(field):
    load, _, expected = plan_parts()
    setattr(load, field, "wrong")
    with pytest.raises(ContractMismatch):
        verify_load_identity(load, expected)


def test_appointment_mismatch_rejected():
    load, _, expected = plan_parts()
    load.locations[1].dateFrom = "wrong"
    with pytest.raises(ContractMismatch):
        verify_load_identity(load, expected)


def test_demo_template_cannot_be_imported_as_live():
    load, canonical, expected = plan_parts()
    canonical.demo = True
    with pytest.raises(ValueError, match="not a demo"):
        to_shipment(load, canonical, expected, observed_at=utcnow(), credential_class=CredentialClass.AGENT)
