import asyncio

from app.services.control_plane import ControlPlane


async def scheduler_loop(control: ControlPlane):
    """Bounded 30-second wakeup with persisted due times; no vendor polling."""
    while True:
        await asyncio.sleep(30)
        try:
            control.run_due()
        except Exception:
            # Do not log raw exceptions/credentials. Keep scheduler alive and expose failure in audit.
            with control.store.transaction():
                agent = control.agent()
                agent.status = "ERROR"
                control.store.put(control.tenant, "agent", "avery", agent)
                control.audit("SCHEDULER_ERROR", "Scheduler paused after internal failure",
                              error_code="SCHEDULER_ERROR")
