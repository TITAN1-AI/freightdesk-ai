# FreightDesk page model

These representative TypeScript-like schemas define the proposed contract, not production code. They belong to the [WebBridge V2 architecture](WEBBRIDGE_V2_ARCHITECTURE.md). The model distinguishes a document-local physical node, a business entity and a proposed logical control identity. It carries no operational field values.

## Shared identity, provenance and uncertainty

```typescript
type NodeId = string;        // opaque ID, unique only inside DocumentKey
type EvidenceId = string;
type ContractVersion = string;
type CanonicalToken = string; // must belong to a reviewed provider/static vocabulary
type ObservationId = string;

interface DocumentKey {
  sensorInstance: string;    // non-secret reference to verified X1 instance
  tabRef: string;
  frameRef: string;
  documentEpoch: number;
  contentRealmEpoch: number;
}
interface ObservationBinding {
  document: DocumentKey;
  observationId: ObservationId;
  commandRef: string;
  hostAuthorityRef: string;  // opaque reference, never a grant or MAC key
  sessionProofRef: EvidenceId;
  presenceProofRef: EvidenceId;
  sequenceStart: number;
  sequenceEnd: number;
  capturedAt: string;
}
interface MetadataName {
  token: CanonicalToken | null;
  classification: 'APPROVED_STATIC' | 'UNCLASSIFIED' | 'CONFLICTING';
  sourceNodes: NodeId[];
  relationships: EvidenceId[];
  // No rawText, originalLabel, nameValue, private-value hash or redactedValue.
}
interface Coverage {
  scope: 'VERIFIED_WORKSPACE' | 'CURRENT_VISIBLE_SECTION' | 'VISIBLE_BOARD';
  completeWithinDeclaredScope: boolean;
  gaps: Array<'NODE_BUDGET' | 'FRAME_INACCESSIBLE' | 'CLOSED_SHADOW_ROOT' |
    'VIRTUALIZED_ROWS' | 'PAGINATION_UNOBSERVED' | 'HIDDEN_REGION' |
    'RELATION_UNRESOLVED' | 'DOCUMENT_CHANGED'>;
  visitedNodes: number;
  emittedNodes: number;
  elapsedMs: number;
  payloadBytes: number;
}
interface EntityProof {
  provider: string;
  entityType: 'LOAD';        // milestone supports LOAD; future kinds need contracts
  entityId: string;          // only the separately authorized business identity
  tenantRef: string;
  tenantSource: 'OWNER_ATTESTED' | 'PROVIDER_VERIFIED';
  identityEvidence: EvidenceId[];
  workspaceRoot: NodeId;
  document: DocumentKey;
  status: 'VERIFIED';
}
```

Node IDs cannot be replayed after document/realm replacement. Business IDs are not permitted in arbitrary attributes or labels merely because an EntityProof exists. Provider verification and owner attestation remain separate. A host authority reference is meaningful only to existing host policy; copying it does not grant a browser command.

## Document, Region and Section

```typescript
interface Document {
  key: DocumentKey;
  providerRef: string;
  verifiedOrigin: string;      // configured allowed origin only
  safePathPattern: string;     // no query, fragment or arbitrary URL
  binding: ObservationBinding;
  root: NodeId;
  nodes: ReadonlyMap<NodeId, DocumentNode>;
  relations: ReadonlyArray<Relationship>;
  coverage: Coverage;
}
interface DocumentNode {
  id: NodeId;
  parent: NodeId | null;
  children: NodeId[];
  tag: string;                // normalized finite HTML/ARIA vocabulary
  role: string | null;
  name: MetadataName;
  visibility: {
    layout: 'VISIBLE' | 'HIDDEN' | 'UNKNOWN';
    accessibility: 'EXPOSED' | 'HIDDEN' | 'UNKNOWN';
    viewport: 'INSIDE' | 'OUTSIDE' | 'UNKNOWN';
    pointerEligible: boolean | null;
  };
  geometryBucket?: {x: number; y: number; width: number; height: number};
  frameBoundary?: 'SAME_DOCUMENT' | 'UNOBSERVED_FRAME';
  shadowBoundary?: 'OPEN_OBSERVED' | 'CLOSED_UNOBSERVED';
  attributeKinds: CanonicalToken[]; // approved names/shapes, not arbitrary values
  evidence: EvidenceId[];
}
interface Relationship {
  from: NodeId;
  to: NodeId;
  kind: 'PARENT' | 'LABEL_FOR' | 'LABELLED_BY' | 'DESCRIBED_BY' | 'OWNS' |
    'CONTROLS' | 'FRAGMENT_TARGET' | 'PROVIDER_TARGET' | 'HEADING_FOR' |
    'SIBLING_FORM_REGION' | 'GROUP_MEMBER' | 'SLOT_ASSIGNED';
  status: 'OBSERVED' | 'CANDIDATE' | 'CONTRADICTED';
  evidence: EvidenceId[];
}
interface Region {
  id: NodeId;
  kind: 'DIALOG' | 'TABPANEL' | 'REGION' | 'FORM_REGION' | 'WORKSPACE' | 'UNKNOWN';
  memberRoots: NodeId[];
  name: MetadataName;
  ownerWorkspace: NodeId;
  ownershipEvidence: EvidenceId[]; // exact entity proof required for outside-shell portals
  relationships: EvidenceId[];
  competingRegionIds: NodeId[];
}
interface Section {
  id: string;
  root: NodeId;
  region: Region;
  canonicalName: CanonicalToken | null;
  workspaceProof: EntityProof;
  selectedControl: NodeId | null;
  formIds: string[];
  tableIds: string[];
  membershipEvidence: EvidenceId[];
  status: 'OBSERVED' | 'CANDIDATE' | 'UNKNOWN';
  coverage: Coverage;
}
```

DocumentGraph is the Document plus its indexed relationships. ControlGraph and SchemaGraph are views referencing these nodes, not independently serialized alternative trees. The compact AI view may omit generic nodes; it must retain a back-reference to every omitted relation-bearing node. Geometry is optional, coarse and weak evidence; it is not identity or an action target by itself.

## Control, Field and Form

```typescript
interface Control {
  node: NodeId;
  kind: 'TAB' | 'BUTTON' | 'LINK' | 'MENU' | 'ACCORDION' | 'INPUT' |
    'SELECT' | 'TEXTAREA' | 'CHECKBOX' | 'RADIO' | 'CUSTOM' | 'UNKNOWN';
  name: MetadataName;
  disabled: boolean | null;
  readOnlyAttribute: boolean | null; // HTML property, NOT ActionPolicy classification
  navigationState?: {selected: boolean | null; expanded: boolean | null};
  targetCandidates: Candidate<NodeId>[];
  locatorCandidates: Candidate<Locator>[];
  actionEffect: 'UNKNOWN' | 'READ_ONLY_NAVIGATION' | 'MUTATION';
  effectEvidence: EvidenceId[];
}
interface Field {
  id: string;
  control: NodeId;
  formId: string | null;
  groupIds: NodeId[];
  sectionId: string;
  canonicalField: CanonicalToken | null;
  label: MetadataName;
  controlType: Control['kind'];
  required: boolean | null;
  editable: boolean | null;
  validationShape: {
    requiredAttribute: boolean;
    patternPresent: boolean;
    minConstraintPresent: boolean;
    maxConstraintPresent: boolean;
  };
  units: {token: CanonicalToken | null; status: 'PROPOSED' | 'UNKNOWN'};
  optionality: 'UNKNOWN' | 'CONDITIONAL_CANDIDATE' | 'REVIEWED_OPTIONAL';
  presence: 'VISIBLE' | 'HIDDEN' | 'NOT_OBSERVED';
  locatorCandidates: Candidate<Locator>[];
  evidence: EvidenceId[];
  semanticStatus: 'PROPOSED' | 'UNKNOWN';
  // Intentionally absent: value, checked value, selected option text, validation message.
}
interface Form {
  id: string;
  root: NodeId;
  sectionId: string;
  groups: Array<{node: NodeId; parentGroup: NodeId | null; legend: MetadataName}>;
  fields: Field[];
  actionControlNodes: NodeId[]; // structural inventory; no submission action
  evidence: EvidenceId[];
}
```

A field's validation *state* or detailed constraint may disclose business information; the initial metadata contract captures constraint presence only. Extending it needs an explicit privacy decision. Navigation selection and an operational checkbox value are not interchangeable “state.” Unknown units, timezone and conditional business rules remain unknown.

## Table and Column

```typescript
interface Table {
  id: string;
  root: NodeId;
  kind: 'HTML_TABLE' | 'ARIA_GRID' | 'ARIA_TREEGRID';
  columns: Column[];
  observedRowCount: number;
  reportedRowCount: number | null; // provider claim, not a completeness guarantee
  logicalSlots: Array<{row: number; column: number; cell: NodeId}>;
  rowGroups: Array<{id: NodeId; firstRow: number; observedRows: number}>;
  cloneGroup: string | null;
  cloneStatus: 'DATA_BEARING' | 'HEADER_ONLY' | 'CANDIDATE_CLONE' | 'AMBIGUOUS';
  pagination: {pageSize: number | null; nextAvailable: boolean | null};
  virtualization: 'OBSERVED' | 'NOT_OBSERVED' | 'UNKNOWN';
  schemaFingerprint: string;
  evidence: EvidenceId[];
  coverage: Coverage;
  // No cell text, customer data, row business IDs or operational values in metadata mode.
}
interface Column {
  id: string;
  logicalIndex: number;
  domIndex: number | null;
  visibleIndex: number | null;
  headerNodes: NodeId[];
  headerPath: MetadataName[];
  canonicalField: CanonicalToken | null;
  hidden: boolean | null;
  mappingStatus: 'PROPOSED' | 'UNKNOWN' | 'AMBIGUOUS';
  evidence: EvidenceId[];
}
```

Slot occupancy is structural. Rowspan=0 is confined to its row group. Bound logical slots, span sizes and index ranges before allocation. Gaps in ARIA indices remain gaps; duplicate headers and overlap errors are not repaired by shifting data. Clone grouping proposes structural equivalence; provider view and data-bearing identity are still independently required. “Next disabled” and a finite aria-rowcount cannot by themselves prove whole-account coverage.

## Locator, Evidence and Candidate

```typescript
interface Locator {
  root: NodeId;
  document: DocumentKey;
  strategy: 'ROLE_NAME' | 'LABEL_RELATION' | 'APPROVED_ATTRIBUTE' |
    'RELATIVE_STRUCTURE' | 'CSS_STRUCTURAL' | 'PHYSICAL_HANDLE';
  operands: ReadonlyArray<CanonicalToken | number>; // validated grammar, no arbitrary script
  sourceNode: NodeId;
  expectedSignature: string;
  uniqueness: {matchedCount: number; verifiedAt: ObservationId};
  cost: number;                 // ranking cost, not confidence probability
  fragility: Array<'ORDINAL' | 'DYNAMIC_ATTRIBUTE' | 'GEOMETRY' | 'UNREVIEWED_NAME'>;
  evidence: EvidenceId[];
}
interface Evidence {
  id: EvidenceId;
  binding: ObservationBinding;
  source: 'PROVIDER_DOM' | 'COMPUTED_STATE' | 'BROWSER_EVENT' |
    'OWNER_ATTESTATION' | 'DERIVED' | 'MODEL_PROPOSAL' | 'VISUAL_PROPOSAL';
  claim: CanonicalToken;
  subjectNodes: NodeId[];
  relationKind: Relationship['kind'] | null;
  algorithmId: string;
  algorithmVersion: string;
  providerContractVersion: ContractVersion;
  dependsOn: EvidenceId[];
  conflictsWith: EvidenceId[];
  observedAt: string;
  safePredicate: CanonicalToken | null;
  safeMeasurements: Record<CanonicalToken, number | boolean>;
  valuesIncluded: false;
}
interface Candidate<T> {
  proposed: T;
  status: 'PROPOSED' | 'UNKNOWN' | 'CONTRADICTED';
  rank: number;
  score: number;                  // heuristic only; may not waive hard gates
  featureContributions: Array<{family: CanonicalToken; contribution: number}>;
  runnerUpMargin: number | null;
  independentEvidenceFamilies: CanonicalToken[];
  support: EvidenceId[];
  contradiction: EvidenceId[];
  missingProof: CanonicalToken[];
}
```

A generated CSS candidate is compiled locally by fixed code from validated operands. This schema does not create a public “execute selector” command. An arbitrary page/model string cannot become a locator. Schema validation rejects unknown fields, invalid numbers, overlong arrays and mismatched document bindings. Scoring reproducibility requires the feature schema, version and candidate set, not a bare confidence number.

## NavigationEdge and StateTransition

```typescript
interface ApplicationState {
  id: string;
  entity: EntityProof;
  view: CanonicalToken | null;
  section: CanonicalToken | null;
  document: DocumentKey;
  structureVersion: ContractVersion;
  observedAt: string;
  evidence: EvidenceId[];
}
interface NavigationEdge {
  id: string;
  fromState: string;
  toStateTemplate: string;
  controlSignature: string;
  locatorContract: ContractVersion;
  action: 'NAVIGATE_VERIFIED_SECTION';
  classification: 'UNKNOWN' | 'READ_ONLY_NAVIGATION' | 'MUTATION';
  approval: 'NOT_REVIEWED' | 'REVIEWED_PROVIDER_CONTRACT';
  preconditions: Array<'FRESH_SESSION' | 'OWNER_PRESENT' | 'LEASE_VALID' |
    'SAME_DOCUMENT' | 'EXACT_ENTITY' | 'UNIQUE_CONTROL' | 'TARGET_SECTION_VERIFIED'>;
  expectedPostconditions: CanonicalToken[];
  returnEdge: string | null;
  evidence: EvidenceId[];
  liveValidation: 'NOT_VALIDATED' | 'SCOPED_VALIDATION_RECEIPT';
}
interface StateTransition {
  id: string;
  from: ApplicationState;
  to: ApplicationState | null;
  trigger: 'OWNER_NAVIGATION' | 'AUTHORIZED_X1_COMMAND' | 'UNATTRIBUTED_CHANGE';
  commandRef: string | null;
  beforeSequence: number;
  afterSequence: number;
  added: NodeId[];
  removed: NodeId[];
  moved: NodeId[];
  visibilityChanged: NodeId[];
  selectionChanged: NodeId[];
  causalStatus: 'CORRELATED' | 'PROVIDER_BOUND' | 'CONFLICTING' | 'UNKNOWN';
  concurrentTriggerObserved: boolean;
  outcome: 'EXPECTED' | 'UNEXPECTED' | 'UNKNOWN';
  evidence: EvidenceId[];
}
```

Classification is separate from executable authority. Even a reviewed READ_ONLY_NAVIGATION edge requires the current host lease/action policy and fresh proofs. OBSERVE never traverses it. AUTO_MAP can use it only under a separately authorized and qualified mode. Provider navigation can itself have application effects; button role, HTTP method or absence of a Save label is not proof of read-only behavior.

## ProviderMap and persistence

```typescript
interface ProviderMap {
  schemaVersion: 2;
  provider: string;
  mapVersion: ContractVersion;
  binding: ObservationBinding;
  entity: EntityProof;
  sections: Section[];
  forms: Form[];
  tables: Table[];
  navigationCandidates: Candidate<NavigationEdge>[];
  evidence: Evidence[];
  schemaFingerprint: string;
  changeKind: 'FIRST_OBSERVATION' | 'UNCHANGED' | 'CROSS_LOAD_VARIATION' |
    'STRUCTURAL_DRIFT' | 'IDENTITY_CONFLICT';
  coverage: Coverage;
  activation: 'CANDIDATE_ONLY';
  valuesIncluded: false;
  productionWrites: false;
  semanticReadValidation: 'NOT_VALIDATED';
}
```

Keep physical node handles in extension memory; serialize only metadata records bound to their observation epoch. Persist candidate maps/evidence append-only under RuntimePaths. Schema fingerprints exclude business IDs, timestamps, field values and merely conditional presence; identity/navigation changes are evaluated separately and fail closed. Store the fingerprint schema version so future normalization cannot reinterpret old hashes.

No-op detection compares the same verified workspace/section and compatible schema version. A changed optional field on another independently verified load records variation, never silently overwrites the prior contract. A changed identity/nav relation remains a safety event even if the field schema hash is unchanged.

Fingerprint equality is not an acceptance shortcut. Required fields in a reviewed provider contract are checked independently; a candidate variation cannot waive them. Distinguish optional instance presence from changes to field type, meaning or ownership. Unknown absence remains unverified until evidence establishes whether it is conditional or drift.

Accepted locator exemplars and candidate signatures have distinct namespaces/statuses. Atomic map/evidence/receipt persistence uses an observation ID and verified digest for idempotency. A failed commit does not authorize another browser action or make a staged candidate accepted. Coordinator recovery reads committed evidence rather than replaying provider execution.

The existing `AscendLoadContextAssembler` continues to require trusted read-mapping validations plus fresh separately authorized provider observations before producing operational values. ProviderMapV2 alone cannot make those values VERIFIED. Historical source facts, owner attestation, derived classifications and model proposals remain distinguishable throughout the handoff.

## Representative result

For the already observed Load 1763 / Load Basics shape, a future V2 map could represent one selected current-route control, one agreeing heading, a unique later form region, 19 field metadata candidates and exact LOAD identity evidence. That is an illustrative translation of existing evidence, not a V2 execution result. No additional observation occurred, no field meaning is promoted, and no navigation edge is approved by writing these types.
