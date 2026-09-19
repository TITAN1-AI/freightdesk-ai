import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.config import Settings
from app.models.domain import AuthorizedIdentity, Role
from app.services.control_plane import ControlPlane
from app.services.store import Store


@pytest.fixture(autouse=True)
def no_production_credentials_in_tests(monkeypatch):
    for variable in ["CARRIERVIEW_API_TOKEN", "CARRIERVIEW_AGENT_API_TOKEN", "CARRIERVIEW_TENANT_API_TOKEN",
                     "CARRIERVIEW_BASE_URL", "CARRIERVIEW_ORIGIN_VERIFIED", "CARRIERVIEW_READS_AUTHORIZED",
                     "FREIGHTDESK_LIVE_VIEW_TOKEN", "FREIGHTDESK_AGENT_TOKEN"]:
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def plane(tmp_path):
    store = Store(tmp_path / "test.sqlite3")
    control = ControlPlane(store, Settings())
    yield control
    store.close()


@pytest.fixture
def owner():
    return AuthorizedIdentity(id="test-owner", tenant_id="booking-logistics", role=Role.OWNER)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "api.sqlite3", token="test-only-token", run_scheduler=False)) as client:
        client.headers["Authorization"] = "Bearer test-only-token"
        yield client
