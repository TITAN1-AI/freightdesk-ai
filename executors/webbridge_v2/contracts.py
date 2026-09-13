"""Strict, values-free graph boundary for the offline V2 implementation.

The caller supplies trusted expected bindings and vocabulary, never the browser payload.
These contracts do not authorize a provider action or validate operational field meanings.
"""
from collections import Counter
from typing import Annotated, Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

Ref = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,96}$")]
NodeRef = Annotated[str, Field(pattern=r"^g[1-9]\d*n[1-9]\d*$", max_length=64)]
KINDS = {"PARENT", "CONTROLS", "LABELLED_BY", "DESCRIBED_BY", "OWNS", "LABEL_FOR",
         "PROVIDER_TARGET", "FRAGMENT_TARGET", "GROUP_MEMBER", "SLOT_ASSIGNED"}
ATTRIBUTES = {"id", "role", "type", "aria-label", "aria-selected", "aria-current", "aria-expanded",
              "aria-controls", "aria-labelledby", "aria-describedby", "aria-owns", "for", "data-target",
              "data-bs-target", "href", "size", "multiple"}
TAGS = set("main section div span nav header footer aside form fieldset legend label input select textarea button a ul ol li h1 h2 h3 h4 h5 h6 dialog details summary table thead tbody tfoot tr th td iframe slot b strong em i OTHER".split())
ROLES = set("main region navigation banner contentinfo complementary form group heading tab tablist tabpanel button link menu menuitem checkbox radio textbox combobox listbox option dialog table grid treegrid row columnheader rowheader cell gridcell spinbutton slider searchbox rowgroup list listitem".split())
GAPS = {"PRIVATE_SUBTREE_EXCLUDED", "FRAME_UNOBSERVED", "SHADOW_AVAILABILITY_UNKNOWN",
        "RELATION_UNRESOLVED", "SLOT_TEXT_UNOBSERVED"}


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    @field_validator("*", mode="before")
    @classmethod
    def immutable_sequences(cls, value, info: ValidationInfo):
        annotation = cls.model_fields[info.field_name].annotation
        if get_origin(annotation) is Literal and all(type(v) is int for v in get_args(annotation)) and type(value) is not int:
            raise ValueError('V2_SCALAR_INVALID')
        if info.field_name in {"nodes", "relations", "unresolved", "attributes", "gaps", "source_nodes", "relation_refs", "evidence_refs", "candidates", "evidence", "resolutions", "deferred_domains", "recognized_section_labels", "target_relationship_kinds"} and type(value) is list:
            return tuple(value)
        return value


class Binding(Frozen):
    document_epoch: Ref
    realm: Ref
    lease_ref: Ref
    session_ref: Ref
    provider: Ref
    entity_type: Literal["LOAD"]
    entity_id: Annotated[str, Field(pattern=r"^\d{1,20}$")]


class MetadataName(Frozen):
    token: Annotated[str, Field(max_length=80)] | None
    classification: Literal["APPROVED_STATIC", "UNCLASSIFIED", "CONFLICTING"]
    source_nodes: Annotated[tuple[NodeRef, ...], Field(max_length=64)]
    relation_refs: Annotated[tuple[Ref, ...], Field(max_length=64)]
    evidence_refs: Annotated[tuple[Ref, ...], Field(max_length=64)]


class Visibility(Frozen):
    layout: Literal["VISIBLE", "HIDDEN"]
    accessibility: Literal["HIDDEN", "UNKNOWN"]
    viewport: Literal["INSIDE", "OUTSIDE", "UNKNOWN"]
    paint: Literal["UNAVAILABLE"]


class Node(Frozen):
    id: NodeRef
    parent: NodeRef | None
    tag: str
    role: str | None
    name: Annotated[str, Field(max_length=80)] | None
    name_conflict: bool
    current_route: bool
    visible: bool
    visibility: Visibility
    metadata_name: MetadataName
    selected: bool | None
    expanded: bool | None
    control: bool
    action_effect: Literal["UNKNOWN"]
    attributes: Annotated[tuple[str, ...], Field(max_length=24)]

    @model_validator(mode="after")
    def vocabulary(self, info: ValidationInfo):
        if (self.tag not in TAGS or self.role is not None and self.role not in ROLES
            or not set(self.attributes) <= ATTRIBUTES or len(self.attributes) != len(set(self.attributes))
            or self.name is not None and self.name not in (info.context or {}).get("vocabulary", ())
            or self.name_conflict and self.name is not None
            or self.role not in {"tab", "button", "link"} and (self.selected is not None or self.expanded is not None)
            or self.metadata_name.token != self.name
            or self.visible != (self.visibility.layout == "VISIBLE")
            or self.metadata_name.classification != ("CONFLICTING" if self.name_conflict else "APPROVED_STATIC" if self.name else "UNCLASSIFIED")):
            raise ValueError("V2_METADATA_INVALID")
        return self


class Relation(Frozen):
    id: Annotated[str, Field(pattern=r"^r[1-9]\d*$", max_length=32)]
    from_: NodeRef = Field(alias="from")
    to: NodeRef
    kind: str

    @field_validator("kind")
    @classmethod
    def kind_known(cls, value):
        if value not in KINDS:
            raise ValueError("V2_RELATION_INVALID")
        return value


class Unresolved(Frozen):
    from_: NodeRef = Field(alias="from")
    kind: Literal["CONTROLS", "LABELLED_BY", "DESCRIBED_BY", "OWNS", "LABEL_FOR", "PROVIDER_TARGET", "FRAGMENT_TARGET"]
    status: Literal["AMBIGUOUS", "MISSING_OR_OUT_OF_SCOPE"]
    candidate_count: Annotated[int, Field(ge=0, le=512)]


class Coverage(Frozen):
    scope: Literal["VERIFIED_WORKSPACE"]
    gaps: Annotated[tuple[str, ...], Field(max_length=8)]
    complete: bool

    @model_validator(mode="after")
    def coverage_known(self):
        if not set(self.gaps) <= GAPS or self.complete != (not self.gaps) or len(self.gaps) != len(set(self.gaps)):
            raise ValueError("V2_COVERAGE_INVALID")
        return self


class ReferenceResolution(Frozen):
    from_: NodeRef = Field(alias="from")
    kind: Literal["CONTROLS", "LABELLED_BY", "DESCRIBED_BY", "OWNS", "LABEL_FOR", "PROVIDER_TARGET", "FRAGMENT_TARGET"]
    status: Literal["UNDECLARED", "RESOLVED", "AMBIGUOUS", "UNRESOLVED", "DANGLING", "OUT_OF_SCOPE", "INACCESSIBLE"]
    candidates: Annotated[tuple[NodeRef, ...], Field(max_length=512)]
    candidate_count: Annotated[int, Field(ge=0, le=512)]

    @model_validator(mode="after")
    def cardinality(self):
        if self.candidate_count != len(set(self.candidates)) or len(self.candidates) != self.candidate_count:
            raise ValueError("V2_REFERENCE_INVALID")
        if (self.status == "RESOLVED" and self.candidate_count != 1
            or self.status == "AMBIGUOUS" and self.candidate_count < 2
            or self.status not in {"RESOLVED", "AMBIGUOUS"} and self.candidate_count):
            raise ValueError("V2_REFERENCE_INVALID")
        return self


class Evidence(Frozen):
    id: Ref
    source: Literal["PROVIDER_DOM"]
    claim: Literal["NODE_METADATA"]
    nodes: Annotated[tuple[NodeRef, ...], Field(min_length=1, max_length=1)]
    algorithm: Literal["metadata-projector-2"]
    observation_id: Ref


class EntityProof(Frozen):
    entity_type: Literal["LOAD"]
    entity_id: Annotated[str, Field(pattern=r"^\d{1,20}$")]
    provider: Ref
    root: NodeRef
    tenant_source: Literal["OWNER_ATTESTED", "PROVIDER_VERIFIED"]
    identity_source: Literal["VERIFIED_X1_ADAPTER"]
    evidence_refs: Annotated[tuple[Ref, ...], Field(min_length=1, max_length=8)]


class DocumentKey(Frozen):
    document_epoch: Ref
    content_realm_epoch: Ref
    frame_ref: Literal["TOP_FRAME"]
    sensor_module: Literal["X1"]


class ObservationBinding(Frozen):
    observation_id: Ref
    authority_ref: Ref
    session_proof_ref: Ref
    mutation_revision: Literal[0]


class DocumentGraph(Frozen):
    schema_version: Literal[2]
    observation_id: Ref
    binding: Binding
    root: NodeRef
    nodes: Annotated[tuple[Node, ...], Field(min_length=1, max_length=512)]
    relations: Annotated[tuple[Relation, ...], Field(max_length=1024)]
    unresolved: Annotated[tuple[Unresolved, ...], Field(max_length=1024)]
    resolutions: Annotated[tuple[ReferenceResolution, ...], Field(max_length=1024)]
    evidence: Annotated[tuple[Evidence, ...], Field(max_length=512)]
    entity_proof: EntityProof
    document_key: DocumentKey
    observation_binding: ObservationBinding
    semantic_read_validation: Literal["NOT_VALIDATED"]
    deferred_domains: tuple[Literal["FIELDS", "TABLES", "NAVIGATION_ACTIVATION", "OPERATIONAL_VALUES"], ...]
    coverage: Coverage
    activation: Literal["CANDIDATE_ONLY"]
    values_included: Literal[False]
    production_writes: Literal[False]

    @field_validator("values_included", "production_writes", mode="before")
    @classmethod
    def literal_false(cls, value):
        if value is not False:
            raise ValueError("V2_FLAGS_INVALID")
        return value

    @model_validator(mode="after")
    def graph_integrity(self, info: ValidationInfo):
        context = info.context or {}
        if self.binding.model_dump() != context.get("expected_binding"):
            raise ValueError("V2_BINDING_MISMATCH")
        nodes = {n.id: n for n in self.nodes}
        if len(nodes) != len(self.nodes) or self.root not in nodes:
            raise ValueError("V2_NODE_INVALID")
        if [n.id for n in self.nodes if n.parent is None] != [self.root]:
            raise ValueError("V2_ROOT_INVALID")
        for node in self.nodes:
            seen = set()
            current = node
            while current.parent is not None:
                if current.id in seen or current.parent not in nodes:
                    raise ValueError("V2_OWNERSHIP_INVALID")
                seen.add(current.id)
                current = nodes[current.parent]
        if len({r.id for r in self.relations}) != len(self.relations):
            raise ValueError("V2_RELATION_INVALID")
        tuples = {(r.from_, r.to, r.kind) for r in self.relations}
        if len(tuples) != len(self.relations):
            raise ValueError("V2_RELATION_INVALID")
        for r in self.relations:
            if r.from_ not in nodes or r.to not in nodes or r.from_ == r.to:
                raise ValueError("V2_RELATION_INVALID")
            if r.kind == "PARENT" and nodes[r.to].parent != r.from_:
                raise ValueError("V2_OWNERSHIP_INVALID")
        for n in self.nodes:
            if n.parent is not None and (n.parent, n.id, "PARENT") not in tuples:
                raise ValueError("V2_OWNERSHIP_INVALID")
        if any(r.from_ not in nodes for r in self.unresolved):
            raise ValueError("V2_RELATION_INVALID")
        if self.unresolved and "RELATION_UNRESOLVED" not in self.coverage.gaps:
            raise ValueError("V2_COVERAGE_INVALID")
        evidence = {e.id: e for e in self.evidence}
        if len(evidence) != len(self.evidence) or any(e.observation_id != self.observation_id or any(n not in nodes for n in e.nodes) for e in self.evidence):
            raise ValueError("V2_EVIDENCE_INVALID")
        relation_ids = {r.id for r in self.relations}
        for n in self.nodes:
            if (any(x not in nodes for x in n.metadata_name.source_nodes)
                or any(x not in relation_ids for x in n.metadata_name.relation_refs)
                or any(x not in evidence for x in n.metadata_name.evidence_refs)):
                raise ValueError("V2_EVIDENCE_INVALID")
        for resolution in self.resolutions:
            if resolution.from_ not in nodes or any(n not in nodes for n in resolution.candidates):
                raise ValueError("V2_REFERENCE_INVALID")
            if resolution.status == "RESOLVED" and (resolution.from_, resolution.candidates[0], resolution.kind) not in tuples:
                raise ValueError("V2_REFERENCE_INVALID")
        resolved = {(r.from_, r.candidates[0], r.kind) for r in self.resolutions if r.status == 'RESOLVED'}
        expected_unresolved = Counter((r.from_, r.kind, 'AMBIGUOUS' if r.status == 'AMBIGUOUS' else 'MISSING_OR_OUT_OF_SCOPE', r.candidate_count)
            for r in self.resolutions if r.status not in {'RESOLVED', 'UNDECLARED'})
        if expected_unresolved != Counter((r.from_, r.kind, r.status, r.candidate_count) for r in self.unresolved):
            raise ValueError('V2_REFERENCE_INVALID')
        reference_kinds = {'CONTROLS', 'LABELLED_BY', 'DESCRIBED_BY', 'OWNS', 'PROVIDER_TARGET', 'FRAGMENT_TARGET'}
        for relation in self.relations:
            if relation.kind in reference_kinds and (relation.from_, relation.to, relation.kind) not in resolved:
                raise ValueError('V2_REFERENCE_INVALID')
            if relation.kind == 'LABEL_FOR' and (relation.from_, relation.to, relation.kind) not in resolved:
                ancestor = nodes[relation.to]
                while ancestor.parent is not None and ancestor.id != relation.from_:
                    ancestor = nodes[ancestor.parent]
                if ancestor.id != relation.from_ or nodes[relation.from_].tag != 'label':
                    raise ValueError('V2_REFERENCE_INVALID')
        for r in self.resolutions:
            if r.status == 'UNDECLARED' and any(other.from_ == r.from_ and other.kind == r.kind and other.status != 'UNDECLARED' for other in self.resolutions):
                raise ValueError('V2_REFERENCE_INVALID')
        for node in self.nodes:
            if not node.metadata_name.evidence_refs or any(node.id not in evidence[e].nodes for e in node.metadata_name.evidence_refs):
                raise ValueError('V2_EVIDENCE_INVALID')
        if (self.entity_proof.entity_id != self.binding.entity_id or self.entity_proof.provider != self.binding.provider
            or self.entity_proof.root != self.root or any(e not in evidence for e in self.entity_proof.evidence_refs)
            or self.document_key.document_epoch != self.binding.document_epoch or self.document_key.content_realm_epoch != self.binding.realm
            or self.observation_binding.observation_id != self.observation_id or self.observation_binding.authority_ref != self.binding.lease_ref
            or self.observation_binding.session_proof_ref != self.binding.session_ref
            or set(self.deferred_domains) != {"FIELDS", "TABLES", "NAVIGATION_ACTIVATION", "OPERATIONAL_VALUES"}):
            raise ValueError("V2_BINDING_MISMATCH")
        return self


def validate_graph(raw: dict, *, expected_binding: Binding, vocabulary: frozenset[str]) -> DocumentGraph:
    return DocumentGraph.model_validate(raw, context={"expected_binding": expected_binding.model_dump(), "vocabulary": vocabulary})
