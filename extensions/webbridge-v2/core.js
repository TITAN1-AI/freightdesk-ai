/* FreightDesk original implementation. Provenance: third_party/webbridge-v2-implementation.json.
 * Offline-only: deliberately absent from X1's manifest/imports. No messaging, navigation or mutation API.
 */
(() => {
  'use strict';
  const VERSION = 2;
  const STAGES = ['PREFLIGHT', 'BOUNDARY_VERIFIED', 'GRAPH_CAPTURED', 'RELATIONSHIPS_RESOLVED', 'SECTION_VERIFIED'];
  const DEFAULTS = Object.freeze({visited:1024, emitted:512, depth:32, attributes:32,
    attributeBytes:256, relations:1024, references:16, labelNodes:32, labelDepth:4, geometry:1024, frontier:128,
    labelBytes:128, payloadBytes:262144, elapsedMs:1500, batch:32});
  const TAGS = new Set('main section div span nav header footer aside form fieldset legend label input select textarea button a ul ol li h1 h2 h3 h4 h5 h6 dialog details summary table thead tbody tfoot tr th td iframe slot b strong em i'.split(' '));
  const ROLES = new Set('main region navigation banner contentinfo complementary form group heading tab tablist tabpanel button link menu menuitem checkbox radio textbox combobox listbox option dialog table grid treegrid row columnheader rowheader cell gridcell spinbutton slider searchbox rowgroup list listitem'.split(' '));
  const PRIVATE = new Set(['input', 'textarea', 'select', 'option', 'script', 'style', 'template']);
  const CONTROLS = new Set(['tab','button','link','menu','menuitem','checkbox','radio','textbox','combobox','listbox','spinbutton','slider','searchbox']);
  const REFS = {'aria-controls':'CONTROLS','aria-labelledby':'LABELLED_BY','aria-describedby':'DESCRIBED_BY',
    'aria-owns':'OWNS',for:'LABEL_FOR','data-target':'PROVIDER_TARGET','data-bs-target':'PROVIDER_TARGET',href:'FRAGMENT_TARGET'};
  const safeRef = x => typeof x === 'string' && /^[A-Za-z0-9_.:-]{1,96}$/.test(x);
  const norm = x => x.replace(/\s+/g,' ').trim();
  function frozen(x) { if (x && typeof x === 'object') { for (const v of Object.values(x)) frozen(v); Object.freeze(x); } return x; }
  class Stop extends Error { constructor(code, predicate=code) { super(code); this.code=code; this.predicate=predicate; } }
  class NodeLedger {
    constructor() { this.generation=0; this.epoch=null; this.realm=null; this.doc=null; }
    bind(doc, epoch, realm) {
      if (this.doc!==doc || this.epoch!==epoch || this.realm!==realm) {
        this.doc=doc; this.epoch=epoch; this.realm=realm; this.ids=new WeakMap(); this.next=0; this.generation++;
      }
    }
    id(node) { if (!this.ids.has(node)) this.ids.set(node,`g${this.generation}n${++this.next}`); return this.ids.get(node); }
    close() { this.doc=null; this.ids=new WeakMap(); this.epoch=null; this.realm=null; }
  }
  function createOfflineHarness(options) {
    if (options?.mode!=='OFFLINE' || typeof options.readProof!=='function') throw new Stop('V2_OFFLINE_ONLY');
    const {readProof}=options;
    const semantics=globalThis.FreightDeskV2Semantics;
    if(!semantics)throw new Stop('V2_CONFIGURATION_INVALID');
    const clock=options.clock || (()=>performance.now());
    const pause=options.yieldControl || (()=>new Promise(resolve=>setTimeout(resolve,0)));
    const allowed=new Set(options.vocabulary || []), sections=new Set(options.sections || []);
    if (allowed.size>128 || sections.size>32 || [...allowed].some(s=>typeof s!=='string'||!s.length||s.length>80||norm(s)!==s)
      || [...sections].some(s=>!allowed.has(s))) throw new Stop('V2_CONFIGURATION_INVALID');
    const limits={...DEFAULTS,...options.limits};
    if (Object.keys(limits).some(k=>!(k in DEFAULTS)||!Number.isInteger(limits[k])||limits[k]<1||limits[k]>DEFAULTS[k])) throw new Stop('V2_CONFIGURATION_INVALID');
    const stateClasses=new Set(options.stateClasses || []);
    if ([...stateClasses].some(s=>!['active','selected'].includes(s))) throw new Stop('V2_CONFIGURATION_INVALID');
    const ledger=new NodeLedger();
    let closed=false, busy=false,lastHandles=new Map(),lastObservation=null;
    const attributes=['id','role','type','size','multiple','aria-label','aria-selected','aria-current','aria-expanded',...Object.keys(REFS)];
    function boundary() {
      if (closed) throw new Stop('V2_CLOSED');
      const p=readProof();
      if (p?.schemaVersion!==VERSION) throw new Stop('V2_PROTOCOL_MISMATCH');
      if (p.revoked!==false || p.leaseValid!==true) throw new Stop('V2_AUTHORITY_UNAVAILABLE');
      if (p.sessionVerified!==true) throw new Stop('V2_SESSION_UNVERIFIED');
      if (p.ownerPresent!==true || p.foreground!==true) throw new Stop('WAITING_FOR_OWNER_WORKSPACE');
      if (p.identityVerified!==true || p.entityType!=='LOAD' || typeof p.entityId!=='string' || !/^\d{1,20}$/.test(p.entityId)) throw new Stop('V2_IDENTITY_UNVERIFIED');
      if (!p.root?.isConnected || p.root.ownerDocument!==p.document || p.document.documentElement===p.root || p.document.body===p.root)
        throw new Stop('V2_SCOPE_INVALID');
      if (typeof options.origin!=='string' || p.document.location.origin!==options.origin) throw new Stop('V2_ORIGIN_MISMATCH');
      if (['epoch','realm','leaseRef','sessionRef','provider'].some(k=>!safeRef(p[k]))) throw new Stop('V2_BINDING_INVALID');
      return p;
    }
    async function capture(observationId) {
      if (busy) return frozen({status:'STOPPED',error_code:'V2_JOB_ACTIVE',last_completed_stage:'PREFLIGHT',failed_predicate:'V2_JOB_ACTIVE',values_included:false,production_writes:false});
      busy=true;
      lastHandles.clear();lastObservation=null;
      let stage='PREFLIGHT', start=null, observer=null, dirty=false;
      const measured={visited:0,emitted:0,relations:0,label_nodes:0,elapsed_ms:0,payload_bytes:0,geometry_reads:0,frontier_max:0};
      let exceeded=null;
      try {
        if (!safeRef(observationId)) throw new Stop('V2_OBSERVATION_INVALID');
        // Snapshot scalar bindings: readProof may expose a mutable runtime-state object.
        // Keeping that same object would let a later mutation rewrite both sides of comparison.
        const initial={...boundary()};
        // Deadlines begin only after fresh trusted boundary + foreground readiness, never while waiting.
        function bound(category, value) {
          if (value>limits[category]) { exceeded={category,measured:value,maximum:limits[category]}; throw new Stop('V2_BOUND_EXCEEDED',`BOUND_${category.toUpperCase()}`); }
        }
        function check() {
          if(dirty || observer?.takeRecords().length) throw new Stop('V2_STRUCTURE_CHANGED');
          const p=boundary();
          if (p.document!==initial.document || p.epoch!==initial.epoch || p.realm!==initial.realm) throw new Stop('V2_DOCUMENT_CHANGED');
          if (p.root!==initial.root || p.entityId!==initial.entityId || p.provider!==initial.provider) throw new Stop('V2_IDENTITY_CHANGED');
          if (p.leaseRef!==initial.leaseRef || p.sessionRef!==initial.sessionRef) throw new Stop('V2_BINDING_CHANGED');
          measured.elapsed_ms=Math.max(0,clock()-start); bound('elapsedMs',measured.elapsed_ms);
        }
        ledger.bind(initial.document,initial.epoch,initial.realm);
        const win=initial.document.defaultView;
        function visible(e, inherited=true) {
          const style=win.getComputedStyle(e);
          const hidden=!inherited||e.hidden||style.display==='none';
          bound('geometry',++measured.geometry_reads);
          const rect=e.getBoundingClientRect(), layout=!hidden&&semantics.styleVisible(e,style)&&
            (style.display==='contents'||rect.width>0&&rect.height>0);
          return {descendants:!hidden,layout,accessibility:e.getAttribute('aria-hidden')==='true'?'HIDDEN':'UNKNOWN',
            viewport:layout?(rect.bottom>0&&rect.right>0&&rect.top<win.innerHeight&&rect.left<win.innerWidth?'INSIDE':'OUTSIDE'):'UNKNOWN'};
        }
        if (!visible(initial.root).layout) throw new Stop('WAITING_FOR_OWNER_WORKSPACE');
        start=clock();
        observer=new win.MutationObserver(()=>{dirty=true;});
        const observeRoot=root=>observer.observe(root,{subtree:true,childList:true,attributes:true,characterData:true});
        observeRoot(initial.root);
        stage='BOUNDARY_VERIFIED';
        function attribute(e,k) {
          const s=e.getAttribute(k); if (s!==null) bound('attributeBytes',s.length); return s;
        }
        function labelText(e) {
          // Only admitted label/control/heading sources; no subtree-wide textContent/innerText getters.
          let count=0,text=''; const stack=[{n:e.firstChild,d:0}];
          while(stack.length) {
            check(); const {n,d}=stack.pop(); if (!n) continue;
            bound('labelNodes',++count); measured.label_nodes++;
            if(d>limits.labelDepth) return null;
            if(n.nextSibling) stack.push({n:n.nextSibling,d});
            if(n.nodeType===3) { if (n.nodeValue.length+text.length>limits.labelBytes) return null; text+=n.nodeValue; }
            else if(n.nodeType===1) {
              const tag=n.localName;
              if(PRIVATE.has(tag)||n.hasAttribute('data-private')||!['span','b','strong','em','i'].includes(tag)) return null;
              stack.push({n:n.firstChild,d:d+1});
            }
          }
          const token=norm(text); return allowed.has(token)?token:null;
        }
        const nodes=[], relations=[], entries=new Map(), physical=new Map(), ids=new Map(), refs=[], seen=new Set(), gaps=new Set();
        let byteBudget=0;
        function reserve(value){byteBudget+=new TextEncoder().encode(JSON.stringify(value)).length;bound('payloadBytes',byteBudget);}
        function edge(from,to,kind) {
          if (relations.some(e=>e.from===from&&e.to===to&&e.kind===kind)) return;
          bound('relations',relations.length+1);
          const value={id:`r${relations.length+1}`,from,to,kind};reserve(value);relations.push(value); measured.relations=relations.length;
        }
        // Sibling cursors bound frontier memory independently of a huge child list.
        const stack=[{node:initial.root,parent:null,depth:0,inherited:true,siblings:false}];
        while(stack.length) {
          measured.frontier_max=Math.max(measured.frontier_max,stack.length);bound('frontier',stack.length);
          check(); const item=stack.pop(),e=item.node; if(!e) continue;
          if(item.siblings && e.nextElementSibling) stack.push({...item,node:e.nextElementSibling});
          if(seen.has(e)) continue;
          bound('visited',++measured.visited); bound('depth',item.depth); seen.add(e);
          if(e.ownerDocument!==initial.document) throw new Stop('V2_SCOPE_INVALID');
          const tag=e.localName;
          // Do not enter value-bearing, executable or explicitly private subtrees.
          if(['script','style','template','option'].includes(tag)||e.hasAttribute('data-private')) { gaps.add('PRIVATE_SUBTREE_EXCLUDED'); continue; }
          bound('attributes',e.attributes.length); bound('emitted',nodes.length+1);
          const a={}; for(const k of attributes) a[k]=attribute(e,k);
          const id=ledger.id(e), vis=visible(e,item.inherited);
          const role=semantics.role(e,ROLES);
          const isNav=['tab','button','link'].includes(role);
          let selected=null;
          if(isNav) {
            selected=a['aria-selected']==='true'||['page','true'].includes(a['aria-current']);
            for(const c of stateClasses) if(e.classList.contains(c)||e.parentElement?.classList.contains(c)) selected=true;
          }
          let name=allowed.has(a['aria-label'])?a['aria-label']:null;
          if(!name && (['label','legend'].includes(tag)||role==='heading'||isNav)) name=labelText(e);
          const currentRoute=tag==='a' && !!a.href && a.href.startsWith('/')&&!/[?#]/.test(a.href) &&
            new URL(a.href,options.origin).origin===options.origin && new URL(a.href,options.origin).pathname===initial.document.location.pathname;
          const n={id,parent:item.parent,tag:TAGS.has(tag)?tag:'OTHER',role,name,name_conflict:false,current_route:currentRoute,
            visible:vis.layout,selected,expanded:isNav&&a['aria-expanded']!==null?a['aria-expanded']==='true':null,
            visibility:{layout:vis.layout?'VISIBLE':'HIDDEN',accessibility:vis.accessibility,viewport:vis.viewport,paint:'UNAVAILABLE'},
            control:CONTROLS.has(role),action_effect:'UNKNOWN',attributes:attributes.filter(k=>a[k]!==null)};
          reserve(n);
          nodes.push(n); entries.set(id,{element:e,node:n,attrs:a}); physical.set(e,id); measured.emitted=nodes.length;
          if(item.parent) edge(item.parent,id,'PARENT');
          const tree=e.getRootNode();
          if(!ids.has(tree))ids.set(tree,new Map());
          if(a.id) { if(!ids.get(tree).has(a.id)) ids.get(tree).set(a.id,[]); ids.get(tree).get(a.id).push(id); }
          for(const [k,kind] of Object.entries(REFS)) {
            if(!a[k]) continue;
            let targets=[];
            if(k==='href'||k.startsWith('data-')) { if(/^#[^\s#]+$/.test(a[k])) targets=[a[k].slice(1)]; }
            else {try{targets=semantics.idRefs(a[k],limits.references);}catch{bound('references',limits.references+1);}}
            bound('references',targets.length);
            if(targets.length) { bound('relations',refs.length+targets.length); refs.push(...targets.map(target=>({from:id,target,kind,tree}))); }
          }
          if(tag==='iframe') gaps.add('FRAME_UNOBSERVED');
          if(tag.includes('-')&&!e.shadowRoot) gaps.add('SHADOW_AVAILABILITY_UNKNOWN');
          if(!PRIVATE.has(tag)&&tag!=='iframe') {
            if(e.shadowRoot) {
              observeRoot(e.shadowRoot);
              // Preserve light ownership and open shadow ownership separately. Resolve assignedSlot
              // per visited light element later, never allocate an unbounded assignedElements list.
              if(e.firstElementChild) stack.push({node:e.firstElementChild,parent:id,depth:item.depth+1,inherited:vis.descendants,siblings:true});
              if(e.shadowRoot.firstElementChild) stack.push({node:e.shadowRoot.firstElementChild,parent:id,depth:item.depth+1,inherited:vis.descendants,siblings:true});
            } else if(tag==='slot') {
              // Text-only assignments are outside the structural element projection.
              gaps.add('SLOT_TEXT_UNOBSERVED');
              if(e.firstElementChild) stack.push({node:e.firstElementChild,parent:id,depth:item.depth+1,inherited:vis.descendants,siblings:true});
            } else if(e.firstElementChild) stack.push({node:e.firstElementChild,parent:id,depth:item.depth+1,inherited:vis.descendants,siblings:true});
          }
          if(measured.visited%limits.batch===0) { await pause(); check(); }
        }
        stage='GRAPH_CAPTURED';
        for(const [id,item] of entries) {
          const slot=item.element.assignedSlot;
          if(slot) {
            if(physical.has(slot)) edge(physical.get(slot),id,'SLOT_ASSIGNED');
            else gaps.add('RELATION_UNRESOLVED');
          }
        }
        const unresolved=[],resolutions=[];
        for(const ref of refs) {
          check(); const candidates=ids.get(ref.tree)?.get(ref.target)||[];
          if(candidates.length!==1) {
            unresolved.push({from:ref.from,kind:ref.kind,status:candidates.length?'AMBIGUOUS':'MISSING_OR_OUT_OF_SCOPE',candidate_count:candidates.length});
            gaps.add('RELATION_UNRESOLVED');
          } else edge(ref.from,candidates[0],ref.kind);
          const resolution={from:ref.from,kind:ref.kind,status:candidates.length===1?'RESOLVED':candidates.length?'AMBIGUOUS':'UNRESOLVED',
            candidates:[...candidates],candidate_count:candidates.length};reserve(resolution);resolutions.push(resolution);
        }
        for(const n of nodes.filter(n=>n.role==='tab')) if(!refs.some(r=>r.from===n.id&&r.kind==='CONTROLS'))
          resolutions.push({from:n.id,kind:'CONTROLS',status:'UNDECLARED',candidates:[],candidate_count:0});
        // Native wrapping-label and fieldset ownership, without collecting field values.
        for(const n of nodes) {
          if(!n.control) continue;
          let parent=n.parent;
          while(parent) {
            const p=entries.get(parent).node;
            if(p.tag==='label') edge(p.id,n.id,'LABEL_FOR');
            if(p.tag==='fieldset'||p.tag==='form') { edge(p.id,n.id,'GROUP_MEMBER'); break; }
            parent=p.parent;
          }
        }
        // Resolve names from the fixed source projection, retaining conflicting label evidence.
        for(const n of nodes) {
          const names=new Set(n.name?[n.name]:[]);
          for(const r of relations) {
            const source=r.kind==='LABELLED_BY'&&r.from===n.id?r.to:r.kind==='LABEL_FOR'&&r.to===n.id?r.from:null;
            if(source && entries.get(source).node.name) names.add(entries.get(source).node.name);
          }
          if(names.size===1) n.name=[...names][0];
          if(names.size>1) { n.name=null; n.name_conflict=true; }
        }
        // A display:contents wrapper is visible only with a visible admitted descendant.
        for(const n of [...nodes].reverse()) if(win.getComputedStyle(entries.get(n.id).element).display==='contents') {
          n.visible=nodes.some(c=>c.parent===n.id&&c.visible);n.visibility.layout=n.visible?'VISIBLE':'HIDDEN';n.visibility.viewport='UNKNOWN';
        }
        const evidence=nodes.map((n,i)=>({id:`e${i+1}`,source:'PROVIDER_DOM',claim:'NODE_METADATA',nodes:[n.id],
          algorithm:'metadata-projector-2',observation_id:observationId}));
        for(let i=0;i<nodes.length;i++) {
          const n=nodes[i],labelSources=relations.filter(r=>r.kind==='LABELLED_BY'&&r.from===n.id||r.kind==='LABEL_FOR'&&r.to===n.id);
          n.metadata_name={token:n.name,classification:n.name_conflict?'CONFLICTING':n.name?'APPROVED_STATIC':'UNCLASSIFIED',
            source_nodes:[...new Set([n.id,...labelSources.map(r=>r.kind==='LABELLED_BY'?r.to:r.from)])],
            relation_refs:labelSources.map(r=>r.id),evidence_refs:[evidence[i].id]};reserve(n.metadata_name);reserve(evidence[i]);
        }
        stage='RELATIONSHIPS_RESOLVED'; check();
        const graph={schema_version:VERSION,observation_id:observationId,
          binding:{document_epoch:initial.epoch,realm:initial.realm,lease_ref:initial.leaseRef,session_ref:initial.sessionRef,
            provider:initial.provider,entity_type:'LOAD',entity_id:initial.entityId},
          root:ledger.id(initial.root),nodes,relations,unresolved,resolutions,evidence,
          entity_proof:{entity_type:'LOAD',entity_id:initial.entityId,provider:initial.provider,root:ledger.id(initial.root),
            tenant_source:initial.tenantSource||'OWNER_ATTESTED',identity_source:'VERIFIED_X1_ADAPTER',evidence_refs:[evidence[0].id]},
          document_key:{document_epoch:initial.epoch,content_realm_epoch:initial.realm,frame_ref:'TOP_FRAME',sensor_module:'X1'},
          observation_binding:{observation_id:observationId,authority_ref:initial.leaseRef,session_proof_ref:initial.sessionRef,mutation_revision:0},
          semantic_read_validation:'NOT_VALIDATED',deferred_domains:['FIELDS','TABLES','NAVIGATION_ACTIVATION','OPERATIONAL_VALUES'],
          coverage:{scope:'VERIFIED_WORKSPACE',gaps:[...gaps].sort(),complete:gaps.size===0},
          activation:'CANDIDATE_ONLY',values_included:false,production_writes:false};
        measured.payload_bytes=new TextEncoder().encode(JSON.stringify(graph)).length; bound('payloadBytes',measured.payload_bytes);
        check();
        lastHandles=new Map([...entries].map(([id,entry])=>[id,entry.element]));lastObservation=observationId;
        return frozen({status:'CAPTURED',last_completed_stage:stage,graph,measurements:measured,values_included:false,production_writes:false});
      } catch(error) {
        const safe=error instanceof Stop?error:new Stop('V2_CAPTURE_FAILED');
        return frozen({status:'STOPPED',error_code:safe.code,failed_predicate:safe.predicate,last_completed_stage:stage,
          measurements:measured,bound:exceeded,values_included:false,production_writes:false});
      } finally { observer?.disconnect(); busy=false; }
    }
    function section(graph) {
      // This consumes only a completed graph; it confers no live action or identity authority.
      if(graph?.schema_version!==VERSION) throw new Stop('V2_PROTOCOL_MISMATCH');
      const byId=new Map(graph.nodes.map(n=>[n.id,n]));
      const selected=graph.nodes.filter(n=>n.control&&n.visible&&n.selected&&sections.has(n.name));
      const diag={selected_candidate_count:selected.length,recognized_section_labels:[...new Set(selected.map(n=>n.name))],
        target_relationship_kinds:[],visible_target_count:0,heading_root_count:0,unique_candidate_count:0};
      const stop=predicate=>frozen({status:'UNVERIFIED',error_code:'WORKSPACE_SECTION_UNVERIFIED',failed_predicate:predicate,diagnostic:diag});
      if(selected.length!==1) return stop('SELECTED_CONTROL_NOT_UNIQUE');
      const control=selected[0];
      if(graph.unresolved.some(r=>r.from===control.id&&['CONTROLS','FRAGMENT_TARGET','PROVIDER_TARGET'].includes(r.kind))) return stop('TARGET_REFERENCE_UNRESOLVED');
      const edges=graph.relations.filter(r=>r.from===control.id&&['CONTROLS','FRAGMENT_TARGET','PROVIDER_TARGET'].includes(r.kind));
      diag.target_relationship_kinds=[...new Set(edges.map(r=>r.kind))];
      const targets=[...new Set(edges.map(r=>r.to))].filter(id=>byId.get(id)?.visible);
      diag.visible_target_count=targets.length;
      function within(node,root) { for(let n=node;n;n=byId.get(n.parent)) if(n.id===root) return true; return false; }
      const headings=graph.nodes.filter(n=>n.role==='heading'&&n.visible&&n.name===control.name);
      diag.heading_root_count=headings.length;
      let candidates=targets.filter(t=>headings.some(h=>within(h,t)) || byId.get(t).name===control.name);
      let siblingRelation=null;
      if(!edges.length && control.current_route && headings.length===1) {
        const heading=headings[0];
        const order=new Map(graph.nodes.map((n,i)=>[n.id,i]));
        const branch=(n,ancestor)=>{while(n && n.parent!==ancestor)n=byId.get(n.parent);return n;};
        for(let p=byId.get(heading.parent);p;p=byId.get(p.parent)) {
          if(!within(control,p.id)) continue;
          const forms=graph.nodes.filter(n=>n.tag==='form'&&n.visible&&within(n,p.id));
          if(!forms.length) continue;
          candidates=[...new Set(forms.filter(n=>{
            const h=branch(heading,p.id),f=branch(n,p.id),c=branch(control,p.id);
            return h&&f&&c&&h.id!==f.id&&c.id!==f.id&&order.get(f.id)>order.get(h.id)&&
              !graph.nodes.some(x=>within(x,n.id)&&(x.control&&sections.has(x.name)||x.role==='heading'&&sections.has(x.name)));
          }).map(n=>branch(n,p.id).id))];
          diag.visible_target_count=forms.length;
          if(candidates.length===1&&forms.every(n=>within(n,candidates[0]))) siblingRelation={from:heading.id,to:candidates[0],kind:'SIBLING_FORM_REGION'};
          break;
        }
      }
      diag.unique_candidate_count=candidates.length;
      if(candidates.length!==1 || (!siblingRelation&&targets.length!==1)) return stop('TARGET_AND_HEADING_NOT_UNIQUE');
      // A section target containing its own navigation control is not a clean content region.
      if(within(control,candidates[0])) return stop('TARGET_CONTAINS_NAVIGATION');
      return frozen({status:'VERIFIED',source:'PROVIDER_DOM',section:control.name,root:candidates[0],control:control.id,
        evidence:edges.filter(e=>e.to===candidates[0]).map(e=>e.id),derived_relation:siblingRelation,diagnostic:diag,action_effect:'UNKNOWN'});
    }
    return Object.freeze({capture,section,resolveNode(graph,id){const p=boundary();if(graph.observation_id!==lastObservation||graph.binding.document_epoch!==ledger.epoch||graph.binding.realm!==ledger.realm||
      p.epoch!==graph.binding.document_epoch||p.realm!==graph.binding.realm||p.leaseRef!==graph.binding.lease_ref||p.entityId!==graph.binding.entity_id)throw new Stop('V2_DOCUMENT_CHANGED');
      // Only the offline adapter receives a handle. It must still apply the current provider proof.
      return lastHandles.get(id)||null;},close(){closed=true;ledger.close();lastHandles.clear();}});
  }
  globalThis.FreightDeskWebBridgeV2=Object.freeze({version:VERSION,stages:Object.freeze(STAGES),limits:DEFAULTS,createOfflineHarness});
})();
