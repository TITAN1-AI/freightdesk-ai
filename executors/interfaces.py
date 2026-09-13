from typing import Protocol

from app.models.domain import BrowserExecution, ExecutionResult


class BrowserExecutor(Protocol):
    """DOM primitives. Provider identity, policy and operation semantics belong to adapters/services."""
    url: str
    status: str

    async def navigate(self, url: str) -> None: ...
    async def read(self, field) -> str | None: ...
    async def wait_ready(self, field) -> None: ...


class BrowserJobExecutor(Protocol):
    async def execute(self, job: BrowserExecution) -> ExecutionResult:
        """Verify identity and expected state, enforce authorization, execute, reread and verify."""
        ...


class TypedBrowserReadExecutor(BrowserExecutor, Protocol):
    """Optional bounded-read capability; generic DOM primitives remain independently restricted."""
    async def execute_read(self, command) -> dict: ...


class ComputerExecutor(Protocol):
    async def execute(self, job: BrowserExecution) -> ExecutionResult: ...


class AgentWorker(Protocol):
    name: str

    async def run(self, job: BrowserExecution) -> ExecutionResult:
        """Bounded jobs only; control plane retains policy, state, scheduling and audit ownership."""
        ...
