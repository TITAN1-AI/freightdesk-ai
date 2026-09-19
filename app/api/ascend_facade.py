"""Read facade over portable UI harvest. Not an Ascend retail API and not LIVE_VALIDATED."""

from __future__ import annotations

from fastapi import Depends, Request

from app.api.portable_leases import bearer_token
from app.models.domain import AuthorizedIdentity, Role
from app.services.portable_leases import PortableLeaseService


def install_ascend_facade_routes(api, identity):
    def service(request: Request) -> PortableLeaseService:
        return request.app.state.portable

    def facade_reader(request: Request) -> AuthorizedIdentity:
        """Owner dashboard session or a portable device token may read harvest evidence."""
        token = bearer_token(request)
        portable = service(request)
        if portable.has_device_session(token):
            return AuthorizedIdentity(id="portable-device", tenant_id=portable.tenant, role=Role.OWNER)
        return identity(request)

    @api.get("/v1/ascend/status")
    def ascend_facade_status(request: Request, _actor=Depends(facade_reader)):
        """Lease/harvest/actuator health for the portable UI harvest, not X1 native host.

        Empty harvest returns harvest_available=false. Writes are out of scope.
        Evidence class is always CANDIDATE. live_validated is always false.
        """
        return service(request).facade_status()

    @api.get("/v1/ascend/loads")
    def ascend_facade_loads(request: Request, _actor=Depends(facade_reader)):
        """Latest harvested Active Loads board as a stable facade JSON shape.

        This is a facade over VISIBLE_BOARD_ONLY UI harvest, not an Ascend retail API.
        Missing harvest returns loads=[] with load_count=0 (never 500).
        Each load is CANDIDATE_ONLY identity plus raw candidate fields. No writes.
        """
        return service(request).facade_loads()
