"""Explicit TestRuns-only adapter into the existing runtime-owned transaction.

No production switch, CLI, network transport, lease or enrollment is added.
The outer RuntimeController still owns authentication, replay, policy and completion.
"""
import hashlib
import json
from typing import Literal

from pydantic import Field

from app.core.runtime import RuntimePaths
from executors.ascend_extension.mapping_store import persist_map
from executors.ascend_extension.workspace_contracts import AscendProviderMap, MAP_OPERATION, SCOPE
from executors.webbridge_v2.contracts import Binding, Frozen, NodeRef, Ref, validate_graph


class SectionDiagnostic(Frozen):
    selected_candidate_count: int = Field(ge=0, le=512)
    recognized_section_labels: tuple[str, ...] = Field(max_length=32)
    target_relationship_kinds: tuple[Literal["CONTROLS", "FRAGMENT_TARGET", "PROVIDER_TARGET"], ...] = Field(max_length=3)
    visible_target_count: int = Field(ge=0, le=512)
    heading_root_count: int = Field(ge=0, le=512)
    unique_candidate_count: Literal[1]


class DerivedRelation(Frozen):
    source: NodeRef = Field(alias="from")
    to: NodeRef
    kind: Literal["SIBLING_FORM_REGION"]


class SectionProof(Frozen):
    status: Literal["VERIFIED"]
    source: Literal["PROVIDER_DOM"]
    section: str
    root: NodeRef
    control: NodeRef
    evidence: tuple[Ref, ...]
    derived_relation: DerivedRelation | None
    diagnostic: SectionDiagnostic
    action_effect: Literal["UNKNOWN"]


def _guard(access):
    paths = RuntimePaths.from_environment()
    try:
        relative = access.path.absolute().relative_to(paths.path("Data", "TestRuns").absolute())
        checked = paths.path("Data", "TestRuns", *relative.parts)
        if checked.suffix != ".sqlite3":
            raise ValueError()
    except ValueError:
        raise PermissionError("V2_OFFLINE_STORE_ONLY") from None


def _section_relationship(graph, proof):
    """Recompute the limited generic relationship from the accepted graph, never a score."""
    nodes = {n.id: n for n in graph.nodes}
    control, root = nodes[proof.control], nodes[proof.root]
    def within(node, ancestor):
        while node is not None:
            if node.id == ancestor:
                return True
            node = nodes.get(node.parent)
        return False
    if within(control, root.id):
        raise ValueError()
    headings = [n for n in graph.nodes if n.visible and n.role == 'heading' and n.name == proof.section]
    edges = [r for r in graph.relations if r.from_ == control.id and r.kind in {'CONTROLS', 'FRAGMENT_TARGET', 'PROVIDER_TARGET'}]
    if any(r.from_ == control.id and r.kind in {'CONTROLS', 'FRAGMENT_TARGET', 'PROVIDER_TARGET'} for r in graph.unresolved):
        raise ValueError()
    if not proof.derived_relation:
        if {r.to for r in edges if nodes[r.to].visible} != {root.id} or not (root.name == proof.section or any(within(h, root.id) for h in headings)):
            raise ValueError()
        return
    if edges or len(headings) != 1 or proof.derived_relation.source != headings[0].id:
        raise ValueError()
    order = {n.id: i for i, n in enumerate(graph.nodes)}
    def branch(node, ancestor):
        while node.parent != ancestor:
            node = nodes[node.parent]
        return node
    heading = headings[0]
    parent = nodes.get(heading.parent)
    while parent:
        if within(control, parent.id):
            forms = [n for n in graph.nodes if n.visible and n.tag == 'form' and within(n, parent.id)]
            if forms:
                h, c = branch(heading, parent.id), branch(control, parent.id)
                regions = {branch(f, parent.id).id for f in forms}
                if regions != {root.id} or root.id in {h.id, c.id} or order[root.id] <= order[h.id]:
                    raise ValueError()
                if any(within(n, f.id) and (n.control and n.name in SCOPE['sections'] or n.role == 'heading' and n.name in SCOPE['sections']) for f in forms for n in graph.nodes):
                    raise ValueError()
                return
        parent = nodes.get(parent.parent)
    raise ValueError()


class OfflineRuntimeBridge:
    def __init__(self, access):
        _guard(access)
        self.access = access
        self.before_completion = None  # Offline fault injection only.

    def persist(self, db, state, lease, pending, raw, now):
        _guard(self.access)
        if pending["command"]["operation"] != MAP_OPERATION or lease["mapping"]["operation_mode"] != "OBSERVE":
            raise PermissionError("MAPPING_NOT_ENABLED")
        try:
            if len(json.dumps(raw, separators=(",", ":")).encode()) > 45000:
                raise ValueError()
            legacy = {k: v for k, v in raw.items() if k != "webbridge_v2"}
            mapped = AscendProviderMap.model_validate(legacy)
            bundle = raw["webbridge_v2"]
            if set(bundle) != {"compatibility_version", "graph", "section"} or type(bundle["compatibility_version"]) is not int or bundle["compatibility_version"] != 2:
                raise ValueError()
            command = pending["command"]
            expected = Binding(document_epoch=pending["route"]["document_id"],
                realm=str(pending["document_handshake"]["document_generation"]),
                lease_ref=f'lease-{int(command["lease_expires_at"] * 1000)}',
                session_ref='dispatch-' + command["request_id"], provider="AscendTMS",
                entity_type="LOAD", entity_id=mapped.workspace.load_id)
            vocabulary = frozenset(SCOPE["sections"] + list(SCOPE["fields"]) + SCOPE["actions"])
            graph = validate_graph(bundle["graph"], expected_binding=expected, vocabulary=vocabulary)
            proof = SectionProof.model_validate(bundle["section"])
            nodes = {n.id: n for n in graph.nodes}
            control, root = nodes[proof.control], nodes[proof.root]
            if (graph.observation_id != command["request_id"] or graph.entity_proof.tenant_source != "OWNER_ATTESTED"
                    or proof.section != mapped.section.section or proof.section not in SCOPE["sections"]
                    or not control.selected or not control.visible or control.name != proof.section or not root.visible
                    or proof.diagnostic.selected_candidate_count != 1
                    or proof.diagnostic.recognized_section_labels != (proof.section,)):
                raise ValueError()
            selected = [n for n in graph.nodes if n.control and n.visible and n.selected and n.name in SCOPE["sections"]]
            if len(selected) != 1 or selected[0].id != control.id:
                raise ValueError()
            if proof.derived_relation:
                heading = nodes[proof.derived_relation.source]
                if not control.current_route or root.tag not in {"div", "form", "section"} or heading.name != proof.section or heading.role != "heading" or not heading.visible or proof.derived_relation.to != root.id or proof.evidence:
                    raise ValueError()
            elif not proof.evidence or any(not any(e.id == ref and e.from_ == control.id and e.to == root.id and e.kind in {"CONTROLS", "FRAGMENT_TARGET", "PROVIDER_TARGET"} for e in graph.relations) for ref in proof.evidence):
                raise ValueError()
            _section_relationship(graph, proof)
            body = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
        except (ValueError, TypeError, KeyError, AttributeError):
            raise PermissionError("MAPPING_CONTRACT_INVALID") from None
        # Integrity covers the entire accepted compatibility payload, including legacy metadata.
        digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        # execute, not executescript: never implicitly commit the owning runtime transaction.
        db.execute("CREATE TABLE IF NOT EXISTS runtime_v2_observations (observation_id TEXT PRIMARY KEY, digest TEXT NOT NULL, body TEXT NOT NULL, completion TEXT NOT NULL)")
        prior = db.execute("SELECT digest FROM runtime_v2_observations WHERE observation_id=?", (graph.observation_id,)).fetchone()
        if prior:
            if prior[0] != digest:
                raise PermissionError("MAPPING_CONTRACT_INVALID")
            return None
        record = persist_map(db, state, lease, pending, legacy, now)
        if self.before_completion:
            self.before_completion()
        completion = json.dumps({"status": "MAP_PERSISTED", "compatibility_version": 2,
            "observation_id": graph.observation_id, "digest": digest, "map_disposition": "NEW" if record else "NO_OP",
            "activation": "CANDIDATE_ONLY", "values_included": False, "production_writes": False})
        db.execute("INSERT INTO runtime_v2_observations VALUES (?,?,?,?)", (graph.observation_id, digest, body, completion))
        return record


def install_offline(access):
    adapter = OfflineRuntimeBridge(access)
    access._offline_v2_adapter = adapter
    return adapter
