import json
from pathlib import Path

from app.models.domain import ActionPolicy


class PolicyEngine:
    def __init__(self, path: Path):
        self.rules = {key: ActionPolicy(value) for key, value in json.loads(path.read_text()).items()}

    def evaluate(self, action: str, overrides: dict | None = None) -> ActionPolicy:
        if action not in self.rules:
            return ActionPolicy.FORBIDDEN
        return ActionPolicy((overrides or {}).get(action, self.rules[action]))
