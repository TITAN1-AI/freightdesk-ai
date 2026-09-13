from app.models.domain import AuditEvent


class CarrierViewAudit:
    def __init__(self, store, tenant, actor_id):
        self.store, self.tenant, self.actor_id = store, tenant, actor_id

    def __call__(self, entry):
        if entry["tenant_id"] != self.tenant:
            raise PermissionError("CarrierView audit tenant mismatch")
        with self.store.transaction():
            self.store.audit(AuditEvent(tenant_id=self.tenant, actor_id=self.actor_id,
                source="carrierview", event=entry["event"],
                explanation="CarrierView operation metadata recorded; provider content omitted",
                credential_class=entry["credential_class"],
                external_action_id=entry.get("external_action_id"), duration_ms=entry.get("duration_ms"),
                error_code=entry.get("error_code"),
                facts={key: entry[key] for key in ["operation", "fixture", "http_status", "elevated",
                        "uncertain", "has_validation_errors", "retry_after_seconds"] if key in entry}))
