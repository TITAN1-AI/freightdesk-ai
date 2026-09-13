import os
from dataclasses import dataclass
from pathlib import Path

from app.core.config import ROOT

AUTHORIZED_RUNTIME = Path(r"C:\FreightDeskRuntime")
AREAS = {"Secrets", "Data", "Browser", "Documents", "Screenshots", "Logs", "Tokens"}


@dataclass(frozen=True)
class RuntimePaths:
    root: Path

    def __post_init__(self):
        if str(self.root.absolute()).casefold() != str(AUTHORIZED_RUNTIME.absolute()).casefold():
            raise ValueError("Runtime root must be the owner-authorized C:\\FreightDeskRuntime")
        if self.root.is_symlink() or self.root.is_junction():
            raise ValueError("Runtime root must not be a symlink or junction")
        root = self.root.resolve()
        if root.is_relative_to(ROOT.resolve()):
            raise ValueError("Runtime root cannot be inside source")
        if str(root).casefold() != str(AUTHORIZED_RUNTIME.absolute()).casefold():
            raise ValueError("Runtime root must not redirect outside the approved location")

    @classmethod
    def from_environment(cls):
        return cls(Path(os.getenv("FREIGHTDESK_RUNTIME_ROOT", str(AUTHORIZED_RUNTIME))))

    def path(self, area: str, *parts: str) -> Path:
        if area not in AREAS:
            raise ValueError("Unknown runtime area")
        if any(not part or part in {".", ".."} or "/" in part or "\\" in part or ":" in part for part in parts):
            raise ValueError("Invalid runtime path component")
        path = self.root.joinpath(area, *parts)
        current = self.root
        for component in (area, *parts):
            current = current / component
            if current.is_symlink() or current.is_junction():
                raise ValueError("Runtime paths must not follow symlinks or junctions")
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Runtime path escapes the approved root")
        return path

    def ensure(self):
        for area in AREAS:
            self.path(area).mkdir(parents=True, exist_ok=True)
        return self
