"""Dedicated live-owner boundary for local mapping orchestration, never provider writes."""
import asyncio
import logging
from typing import Literal
from fastapi import HTTPException, Request
from pydantic import Field
from executors.ascend_extension.controller import Strict
from executors.ascend_extension.mapping_orchestrator import MappingIntent, MappingOrchestrator
from app.api.x1_runtime import runtime_access


def mapping_orchestrator():
    return MappingOrchestrator(runtime_access())


class MappingControl(Strict):
    action: Literal["start", "cancel", "pause", "resume", "review"]
    intent: MappingIntent | None = None
    sections: list[str] = Field(default_factory=list, max_length=8)


def install_routes(api, owner_boundary):
    def boundary(request):
        owner_boundary(request)
        if request.method != "GET" and request.headers.get("x-freightdesk-local") != "1":
            raise HTTPException(403, "Explicit local owner action required")

    @api.get("/api/ascend/mapping/status")
    def status(request: Request):
        boundary(request)
        try:
            return mapping_orchestrator().status()
        except Exception:
            raise HTTPException(409, "Local mapping status unavailable.") from None

    @api.get("/api/ascend/mapping/report")
    def report(request: Request):
        boundary(request)
        try:
            return mapping_orchestrator().report()
        except Exception:
            raise HTTPException(409, "Local mapping report unavailable.") from None

    @api.post("/api/ascend/mapping/control")
    def control(body: MappingControl, request: Request):
        boundary(request)
        orchestrator = None
        try:
            orchestrator = mapping_orchestrator()
            if body.action == "start":
                return orchestrator.start(body.intent, owner_authorized=True)
            if body.action == "review":
                return orchestrator.review(body.sections, owner_authorized=True)
            return orchestrator.control(body.action, owner_authorized=True)
        except PermissionError:
            raise HTTPException(409, "Mapping could not continue. Review the preserved report.") from None
        except Exception:
            if orchestrator is not None:
                try:
                    return orchestrator.coordinator_failed()
                except Exception:
                    logging.getLogger(__name__).error("MAPPING_COORDINATOR_FAILURE_RECEIPT_UNAVAILABLE")
            raise HTTPException(409, "Mapping could not continue. Review the preserved report.") from None


async def mapping_loop_step():
    orchestrator = None
    try:
        orchestrator = mapping_orchestrator()
        return await asyncio.to_thread(orchestrator.tick)
    except Exception:
        if orchestrator is not None:
            try:
                return await asyncio.to_thread(orchestrator.coordinator_failed)
            except Exception:
                pass
        # A missing local store cannot receive a receipt. Emit only a fixed safe storage code.
        logging.getLogger(__name__).error("MAPPING_COORDINATOR_FAILURE_RECEIPT_UNAVAILABLE")
        return {"status": "STOPPED", "safe_stop_code": "COORDINATOR_FAILED", "cleanup_state": "UNKNOWN", "production_writes": False}


async def mapping_loop():
    # Inert unless an explicitly authorized durable job exists. No browser/network APIs here.
    while True:
        await mapping_loop_step()
        await asyncio.sleep(2)
