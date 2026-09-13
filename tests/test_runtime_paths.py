from pathlib import Path

import pytest

from app.core.config import ROOT
from app.core.runtime import RuntimePaths


def test_runtime_defaults_to_authorized_non_source_root(monkeypatch):
    monkeypatch.delenv("FREIGHTDESK_RUNTIME_ROOT", raising=False)
    paths = RuntimePaths.from_environment()
    assert paths.root == Path(r"C:\FreightDeskRuntime")
    assert paths.path("Secrets", "carrierview-agent-token.dpapi").parent == paths.root / "Secrets"
    assert paths.path("Data", "booking-logistics", "carrierview.sqlite3").is_relative_to(paths.root)


@pytest.mark.parametrize("root", [ROOT, ROOT / "runtime", Path(r"C:\UnrelatedRuntime")])
def test_unapproved_runtime_roots_rejected(root):
    with pytest.raises(ValueError):
        RuntimePaths(root)


@pytest.mark.parametrize("parts", [("..",), ("../../escape",), ("C:\\escape",), ("nested/file",)])
def test_runtime_paths_cannot_escape(parts):
    with pytest.raises(ValueError):
        RuntimePaths.from_environment().path("Data", *parts)
