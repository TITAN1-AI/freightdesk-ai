from app.models.domain import AuthorizedIdentity, Role, Shipment


def authorize(identity: AuthorizedIdentity, tenant: str, permission: str, shipment: Shipment | None = None):
    if identity.tenant_id != tenant:
        raise PermissionError("Tenant access denied")
    if shipment and shipment.tenant_id != tenant:
        raise PermissionError("Shipment tenant mismatch")
    if identity.role == Role.OWNER:
        return
    if identity.role == Role.OPERATIONS_USER and permission in {"read", "review", "pause", "request_action"}:
        return
    if identity.role == Role.SYSTEM and permission in {"read", "review", "transition", "request_action"}:
        return
    # Participant access is scoped. Public participant API projections are not enabled yet.
    if permission == "read" and shipment:
        if identity.role == Role.CUSTOMER and shipment.customer and identity.customer_id == shipment.customer.id:
            return
        if identity.role in {Role.DRIVER, Role.CARRIER_DISPATCHER} and shipment.id in identity.shipment_ids:
            return
    raise PermissionError("Role is not authorized for this operation")
