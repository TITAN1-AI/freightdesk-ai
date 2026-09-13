from typing import Literal, Protocol

from app.models.domain import Model, ModelInvocation


class LanguageRequest(Model):
    tenant_id: str
    purpose: Literal["classification", "extraction", "draft", "exception_analysis", "owner_command"]
    verified_facts: dict
    untrusted_text: str
    output_schema: dict
    max_output_tokens: int = 1000


class LanguageResult(Model):
    structured_output: dict
    invocation: ModelInvocation


class ModelProvider(Protocol):
    async def generate(self, request: LanguageRequest) -> LanguageResult:
        """Schema-validate output; never treat model output as verified shipment facts."""
        ...


def route(task: str, routine: str, balanced: str, strong: str) -> str | None:
    if task in {"risk", "transition", "scheduling", "policy", "billing_gate"}:
        return None
    if task in {"classification", "draft"}:
        return routine
    if task in {"exception_analysis", "ambiguous"}:
        return strong
    return balanced
