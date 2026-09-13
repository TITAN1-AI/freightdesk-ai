# Incremental workflow ownership

FreightDesk owns workflow execution. The typed state machine models the full lifecycle.

| Workflow | Gates | Current execution |
|---|---|---|
| BOOK IT | Selected carrier, vetting/setup, driver info | Design only |
| Tracking | Approved carrier, driver, tracking accepted before RC | Gate only |
| RC | Setup/driver/tracking gate, signed document | State/document gates |
| Pickup | Arrival/loading evidence, BOL/photos/seal | State model |
| Transit | Verified position/ETA, freshness, appointment | Scheduled demo review |
| Delivery/POD | Arrival/delivery evidence, verified POD | State/document gates |
| Billing | Required documents, resolved exceptions | Transition gate |
