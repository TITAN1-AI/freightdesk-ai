from datetime import timedelta

from app.models.domain import (
    Carrier, Customer, Dispatcher, Document, Driver, Shipment, Status, Stop, TrackingState, utcnow,
)


def demo_shipments(tenant: str) -> list[Shipment]:
    now = utcnow()
    result = []
    for i, (origin, destination, age, late, status) in enumerate([
        ("Dallas, TX", "Memphis, TN", 6, -47, Status.IN_TRANSIT),
        ("Chicago, IL", "Atlanta, GA", 8, 22, Status.EN_ROUTE_DELIVERY),
        ("Houston, TX", "San Antonio, TX", 64, -30, Status.IN_TRANSIT),
        ("Phoenix, AZ", "Las Vegas, NV", 12, -20, Status.POD_PENDING),
    ]):
        appointment = now + timedelta(hours=3 + i)
        result.append(Shipment(
            id=f"DEMO-{1847 + i}", tenant_id=tenant, customer_reference=f"DEMO-REF-{i + 1}",
            customer=Customer(id=f"demo-customer-{i % 2}", name=["Demo Fresh Foods", "Demo Industrial Supply"][i % 2]),
            carrier=Carrier(id=f"demo-carrier-{i}", name=f"Demo Carrier {i + 1}", approved=True, setup_complete=True),
            driver=Driver(name=f"Demo Driver {i + 1}", phone="+15550100000", truck="D101", trailer="D201"),
            dispatcher=Dispatcher(name="Demo Dispatch", email="dispatch@example.invalid"),
            origin=Stop(kind="pickup", location=origin, appointment=now - timedelta(hours=6)),
            destination=Stop(kind="delivery", location=destination, appointment=appointment),
            status=status,
            tracking=TrackingState(status="ACTIVE", requested=True, accepted=True,
                last_position_at=now - timedelta(minutes=age), location=["Little Rock, AR", "Dalton, GA",
                "Columbus, TX", "Las Vegas, NV"][i], eta=appointment + timedelta(minutes=late),
                source="demo_fixture", verified_at=now),
            documents=[Document(kind="BOL", source="demo_fixture", verified=True),
                       Document(kind="SIGNED_RC", source="demo_fixture", verified=True)],
        ))
    return result
