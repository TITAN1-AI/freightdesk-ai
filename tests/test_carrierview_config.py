import pytest

from integrations.carrierview.config import CarrierViewConfig


def test_missing_token_fails_without_network(monkeypatch):
    monkeypatch.delenv("CARRIERVIEW_AGENT_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="CARRIERVIEW_AGENT_API_TOKEN required"):
        CarrierViewConfig.from_environment()


@pytest.mark.parametrize("url", ["http://example.invalid", "https://secret@example.invalid",
                                "https://example.invalid?token=secret", ""])
def test_base_origin_requires_documented_https_without_credentials(monkeypatch, url):
    monkeypatch.setenv("CARRIERVIEW_AGENT_API_TOKEN", "fixture-not-a-real-token")
    monkeypatch.setenv("CARRIERVIEW_BASE_URL", url)
    with pytest.raises(ValueError):
        CarrierViewConfig.from_environment()


def test_secret_is_redacted(monkeypatch):
    monkeypatch.setenv("CARRIERVIEW_AGENT_API_TOKEN", "fixture-not-a-real-token")
    monkeypatch.setenv("CARRIERVIEW_BASE_URL", "https://example.invalid")
    config = CarrierViewConfig.from_environment()
    assert "fixture-not-a-real-token" not in repr(config)
    assert "fixture-not-a-real-token" not in config.model_dump_json()
