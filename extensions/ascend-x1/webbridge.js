(() => {
  'use strict';
  // Small DOM-only sensor. No network, messaging, clicks, mutation, or model/visual inference.
  const norm=s=>(s||'').replace(/\s+/g,' ').trim();
  const visible=e=>!!e?.isConnected&&!!e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden'&&!e.closest('[hidden],[aria-hidden="true"]');
  const limits=Object.freeze({direct_targets:4,new_containers:8,newly_visible:8,changed_selected:4,identity_candidates:64,
    opener_attributes:24,attributes:24,controls:64,headings:32,candidates:8,depth:10});
  function bounded(items,max,category){if(items.length>max)throw Error('DETAIL_BOUND_'+category);return items;}
  const scope=globalThis.FreightDeskDetailScope;
  const sections=['Identity','Assignment','Status','Pickup','Delivery'];
  const labels=[...new Set(Object.values(scope).flatMap(s=>s.labels))];
  const approved=s=>labels.includes(norm(s))?norm(s):null;
  const attrs=['id','name','role','aria-selected','aria-expanded','aria-controls','aria-label','aria-labelledby','data-load-id','data-field','data-target','data-bs-target'];
  const containers='[role="dialog"],dialog,.modal,.side-panel,[role="tabpanel"],[data-load-detail],form';
  const chrome='nav,header,footer,[role="navigation"],[role="banner"],[role="contentinfo"]';
  function attributes(e){
    bounded([...e.attributes],limits.attributes,'ATTRIBUTES');
    // Attribute values are never exported, except exact approved field identifiers separately.
    return attrs.filter(a=>e.hasAttribute(a));
  }
  const canonical=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.keys(x).sort().map(k=>[k,x[k]])):x);
  async function fingerprint(value){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(value))))].map(n=>n.toString(16).padStart(2,'0')).join('');}
  function headings(e){return bounded([...e.querySelectorAll('h1,h2,h3,legend,[role="heading"]')],limits.headings,'HEADINGS').filter(visible);}
  const selected=e=>!!e&&(e.getAttribute('aria-selected')==='true'||e.getAttribute('aria-expanded')==='true'||e.classList.contains('active')||e.classList.contains('selected'));
  const category=e=>e.matches('[role="dialog"],dialog')?'dialogs':e.matches('form')?'forms':e.matches('[role="tabpanel"]')?'tabs':e.matches('.modal,.side-panel')?'panels':'other';
  const counts=()=>({direct_targets:0,new_containers:0,newly_visible:0,changed_selected:0,identity_candidates:0,opener_attributes:0});
  let lastDiagnostic=null;
  function diagnostic(){return lastDiagnostic?JSON.parse(JSON.stringify(lastDiagnostic)):null;}
  function checkBound(d,name,measured){
    d.counts[name]=measured;
    if(measured>limits[name]){
      d.failed_category=name;d.measured=measured;d.maximum=limits[name];
      throw Error('DETAIL_BOUND_'+name.toUpperCase());
    }
  }
  // An index of fixed semantic container types only. No descendant form/heading/input walks,
  // raw text, attribute inventory, or recursive traversal of the document.
  const index=doc=>new Map([...doc.querySelectorAll(containers)].filter(e=>!e.closest(chrome)).map(e=>[e,{visible:visible(e),selected:selected(e)}]));
  function references(doc,row,opener,d){
    const result=[];
    if(opener)checkBound(d,'opener_attributes',opener.attributes.length);
    for(const node of [opener,row].filter(Boolean))for(const name of ['aria-controls','data-target','data-bs-target','href']){
      const raw=node.getAttribute(name)||'';
      const ids=name==='aria-controls'?raw.split(/\s+/).filter(Boolean):/^#[\w-]+$/.test(raw)?[raw.slice(1)]:[];
      for(const id of ids){
        if(!result.some(r=>r.id===id))result.push({id,attribute:name});
      }
    }
    checkBound(d,'direct_targets',result.length);
    return result; // Raw target IDs stay ephemeral; diagnostics export only counts and fixed relationships.
  }
  const resolveTargets=(doc,refs)=>[...new Set(refs.flatMap(r=>[...doc.querySelectorAll('#'+CSS.escape(r.id))]))];
  function snapshot(doc,binding={}){
    const {row=null,opener=null,loadId=null}=binding;
    const d={version:1,stage:'BEFORE_CLICK',click_dispatched:false,row_verified:!!row&&!!loadId,
      opener_verified:!!row&&!!opener&&row.contains(opener),baseline_container_count:0,ignored_unchanged_count:0,
      candidate_count:0,categories:{dialogs:0,panels:0,forms:0,tabs:0,other:0},counts:counts(),
      limits:Object.fromEntries(Object.keys(counts()).map(k=>[k,limits[k]])),ranked_candidates:[],
      selected_level:null,failed_category:null,measured:null,maximum:null};
    lastDiagnostic=d;
    if((row||opener||loadId)&&(!d.opener_verified||!row.isConnected||!opener.isConnected))throw Error('DETAIL_CONTAINER_UNVERIFIED');
    const refs=references(doc,row,opener,d),states=index(doc);
    const targets=resolveTargets(doc,refs);checkBound(d,'direct_targets',Math.max(refs.length,targets.length));
    for(const e of targets)states.set(e,{visible:visible(e),selected:selected(e)});
    d.baseline_container_count=states.size;
    return {states,row,opener,loadId,refs,diagnostic:d,selection_before:selected(row)||selected(opener)};
  }
  const levels={DIRECT_REFERENCE:{level:'A',score:400},NEW_CONTAINER:{level:'B',score:300},NEWLY_VISIBLE:{level:'C',score:200},SELECTION_CHANGED:{level:'D',score:100}};
  function containerScore(reasons){return reasons.map(r=>levels[r]).filter(Boolean).sort((a,b)=>b.score-a.score)[0]||null;}
  function connected(before,e){
    const ids=(e.getAttribute('aria-labelledby')||'').split(/\s+/);
    return [before.row,before.opener].some(n=>n?.id&&ids.includes(n.id))||
      !!before.loadId&&e.getAttribute('data-load-id')===before.loadId;
  }
  function containerGraph(before,doc,refs=[]){
    const d=before.diagnostic;lastDiagnostic=d;d.stage='DOM_DIFF';d.failed_category=null;d.measured=null;d.maximum=null;
    d.ranked_candidates=[];d.selected_level=null;
    d.counts.identity_candidates=0;
    const direct=[...new Set([...resolveTargets(doc,before.refs),...refs].filter(Boolean))];
    checkBound(d,'direct_targets',Math.max(before.refs.length,direct.length));
    if(direct.some(e=>e===doc.body||e===doc.documentElement||e.closest(chrome)||!e.matches(containers+',div,section,article')))throw Error('DETAIL_CONTAINER_UNVERIFIED');
    const after=index(doc),changes=[];d.ignored_unchanged_count=0;
    for(const e of direct)after.set(e,{visible:visible(e),selected:selected(e)});
    for(const [element,current] of after){
      if(!current.visible)continue;
      const prior=before.states.get(element),reasons=[];
      if(direct.includes(element))reasons.push('DIRECT_REFERENCE');
      if(!prior)reasons.push('NEW_CONTAINER');else if(!prior.visible)reasons.push('NEWLY_VISIBLE');
      if(prior&&connected(before,element)&&((!prior.selected&&current.selected)||
        !before.selection_before&&(selected(before.row)||selected(before.opener))))reasons.push('SELECTION_CHANGED');
      if(reasons.length)changes.push({element,reasons,...containerScore(reasons)});else d.ignored_unchanged_count++;
    }
    // Forms/tabpanels nested in an equally or more strongly related root are one causal root.
    const byElement=new Map(changes.map(c=>[c.element,c]));
    const roots=changes.filter(c=>{
      for(let parent=c.element.parentElement;parent;parent=parent.parentElement){
        const related=byElement.get(parent);if(related&&related.score>=c.score)return false;
      }
      return true;
    });
    d.candidate_count=roots.length;d.categories={dialogs:0,panels:0,forms:0,tabs:0,other:0};
    for(const c of roots)d.categories[category(c.element)]++;
    d.counts.new_containers=roots.filter(c=>c.reasons.includes('NEW_CONTAINER')).length;
    d.counts.newly_visible=roots.filter(c=>c.reasons.includes('NEWLY_VISIBLE')).length;
    d.counts.changed_selected=roots.filter(c=>c.reasons.includes('SELECTION_CHANGED')).length;
    for(const name of ['new_containers','newly_visible','changed_selected'])checkBound(d,name,d.counts[name]);
    roots.sort((a,b)=>b.score-a.score);
    d.ranked_candidates=roots.map(c=>({level:c.level,score:c.score,reasons:c.reasons,category:category(c.element)}));
    return roots;
  }
  function diff(before,doc,refs=[]){return containerGraph(before,doc,refs);}
  function chooseContainer(candidates){
    if(!candidates.length)throw Error('detail_binding_missing');
    if(candidates.length>1&&candidates[0].score===candidates[1].score)throw Error('DETAIL_IDENTITY_AMBIGUOUS');
    lastDiagnostic.selected_level=candidates[0].level;return candidates[0];
  }
  function markClicked(before){before.diagnostic.click_dispatched=true;before.diagnostic.stage='AFTER_CLICK';lastDiagnostic=before.diagnostic;}
  function identityCandidates(before,n){lastDiagnostic=before.diagnostic;lastDiagnostic.stage='IDENTITY';checkBound(lastDiagnostic,'identity_candidates',n);}
  function relativePath(e,root){
    const parts=[];let n=e;
    while(n&&n!==root){if(parts.length>=limits.depth)throw Error('DETAIL_BOUND_DEPTH');
      parts.unshift([...n.parentElement.children].indexOf(n));n=n.parentElement;}
    if(n!==root)throw Error('DETAIL_CONTAINER_UNVERIFIED');return parts;
  }
  function sectionFor(control,root){
    for(let e=control.parentElement;e;e=e.parentElement){
      if(e.matches('fieldset,section,[role="group"],[role="tabpanel"]')||e===root){
        const direct=headings(e).filter(h=>h.parentElement===e||h.parentElement?.parentElement===e);
        const known=[...new Set(direct.map(h=>norm(h.textContent)).filter(s=>sections.includes(s)))];
        if(known.length===1)return known[0];if(known.length>1)return 'UNKNOWN';
      }
      if(e===root)break;
    }
    return 'UNKNOWN';
  }
  function labelSignals(e,root){
    const result=[];
    for(const l of e.labels||[])if(root.contains(l)&&visible(l)&&approved(l.textContent))result.push({label:approved(l.textContent),strategy:'LABEL_CONTROL'});
    if(approved(e.getAttribute('aria-label')))result.push({label:approved(e.getAttribute('aria-label')),strategy:'ARIA_LABEL'});
    const ids=(e.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean);
    bounded(ids,limits.candidates,'CANDIDATES');
    for(const name of ids){const l=e.ownerDocument.getElementById(name);if(l&&root.contains(l)&&visible(l)&&approved(l.textContent))result.push({label:approved(l.textContent),strategy:'ARIA_LABELLEDBY'});}
    const cell=e.closest('td');
    if(cell&&root.contains(cell)){const row=cell.parentElement,table=cell.closest('table');
      const hs=table?.querySelectorAll('thead th')||[];const h=hs[cell.cellIndex];
      if(h&&visible(h)&&approved(h.textContent))result.push({label:approved(h.textContent),strategy:'TABLE_HEADER'});
      void row;
    }
    const neighbor=e.previousElementSibling;
    if(neighbor&&visible(neighbor)&&approved(neighbor.textContent)&&!result.length)result.push({label:approved(neighbor.textContent),strategy:'NEIGHBOR'});
    return bounded(result,limits.candidates,'CANDIDATES');
  }
  function score(candidates){
    if(candidates.length!==1||candidates[0].conflicting)return {confidence:'UNKNOWN',evidence_level:null};
    const c=candidates[0],level=c.strategy==='PROVIDER_ATTRIBUTE'?'LEVEL_1':['LABEL_CONTROL','ARIA_LABEL','ARIA_LABELLEDBY'].includes(c.strategy)?'LEVEL_2':'LEVEL_3';
    return {confidence:level==='LEVEL_3'?'PROPOSED':'VERIFIED',evidence_level:level};
  }
  function graph(root){
    const controls=bounded([...root.querySelectorAll('input,select,textarea,[role="textbox"],[role="combobox"],[role="status"],output')],limits.controls,'CONTROLS').filter(visible);
    const result=Object.fromEntries(Object.keys(scope).map(k=>[k,[]]));
    for(const e of controls){
      if(e.matches('[type="hidden"],[type="password"],[type="submit"],[type="reset"],[type="button"]'))continue;
      const section=sectionFor(e,root),signals=labelSignals(e,root),providerField=e.getAttribute('data-field');
      const keys=new Set(signals.flatMap(s=>Object.keys(scope).filter(k=>scope[k].section===section&&scope[k].labels.includes(s.label))));
      if(Object.hasOwn(scope,providerField)&&scope[providerField].section===section)keys.add(providerField);
      if(!keys.size)continue; // No value access for excluded/unrecognized fields (finance, private notes, etc.).
      const names=attributes(e),path=relativePath(e,root);
      const explicitUnknown=[...e.labels||[]].some(l=>root.contains(l)&&visible(l)&&!approved(l.textContent))||
        e.hasAttribute('aria-label')&&!approved(e.getAttribute('aria-label'))||
        providerField!==null&&!Object.hasOwn(scope,providerField);
      const conflicting=keys.size>1||explicitUnknown;
      for(const field of keys){
        const matching=signals.filter(s=>scope[field].labels.includes(s.label));
        const signal=matching.find(s=>s.strategy!=='NEIGHBOR'&&s.strategy!=='TABLE_HEADER')||matching[0];
        const strategy=providerField===field?'PROVIDER_ATTRIBUTE':signal.strategy;
        const value=conflicting?'':('value' in e?e.value:e.textContent);
        result[field].push({section,label:signal?.label||null,strategy,tag:e.tagName.toLowerCase(),
          control_type:['text','tel','date','time','datetime-local','number','email'].includes(e.type)?e.type:'OTHER',
          role:['textbox','combobox','status'].includes(e.getAttribute('role'))?e.getAttribute('role'):null,
          attribute_names:names,relative_path:path,neighbor_labels:matching.map(s=>s.label),
          value_present:!!norm(value),conflicting});
        bounded(result[field],limits.candidates,'CANDIDATES');
      }
    }
    return result;
  }
  async function discover(root,identity,reasons){
    if(!identity||identity.expected_load_id!==identity.observed_load_id||identity.confidence!=='VERIFIED'||
      !['PROVIDER_DETAIL_FIELD','PROVIDER_OPENER_IDENTITY','PROVIDER_SELECTED_ROW_BINDING'].includes(identity.identity_strategy))throw Error('DETAIL_IDENTITY_MISSING');
    if(!visible(root)||!reasons.length)throw Error('DETAIL_CONTAINER_UNVERIFIED');
    const supported=identity.identity_strategy==='PROVIDER_DETAIL_FIELD'?identity.detail_field_match:
      identity.newly_visible&&identity.direct_panel_reference&&(identity.identity_strategy==='PROVIDER_OPENER_IDENTITY'?identity.opener_identity_match:identity.selection_transition);
    if(!supported||!identity.row_match||!identity.opener_belongs_to_row||!identity.unique_panel)throw Error('DETAIL_IDENTITY_MISSING');
    if(lastDiagnostic)lastDiagnostic.stage='FIELD_MAPPING';
    const g=graph(root),fields=[];
    for(const [name,candidates] of Object.entries(g)){
      const evaluated=name==='load_id'?{confidence:'VERIFIED',evidence_level:'LEVEL_1'}:score(candidates);
      fields.push({field:name,...evaluated,presence:name==='load_id'?'PRESENT':candidates.length===1&&!candidates[0].conflicting?(candidates[0].value_present?'PRESENT':'EMPTY'):'UNKNOWN',candidates});
    }
    // Fingerprint structure only: values/presence/time/load identifier do not define a mapping version.
    const structure=fields.map(f=>({field:f.field,candidates:f.candidates.map(({value_present,...c})=>c)}));
    return {schema_version:1,provider:'AscendTMS',view:'LOAD_DETAIL',source:'live extension DOM',
      validation_load_id:identity.observed_load_id,observed_at:Date.now()/1000,identity,
      fields,container_reasons:reasons,contract_fingerprint:await fingerprint(structure),
      activation:'CANDIDATE_ONLY',writes_allowed:false,values_included:false};
  }
  // Deterministic semantic equivalence can propose a replacement, never activate it or permit writes.
  function remap(previous,current){
    const safe=current.confidence==='VERIFIED'&&previous.field===current.field&&current.candidates.length===1&&previous.candidates.length===1;
    const a=previous.candidates[0],b=current.candidates[0];
    return safe&&['section','label','role','control_type','tag'].every(k=>a[k]===b[k])?
      {result:'PROPOSED_READ_REMAP',activation:'CANDIDATE_ONLY',writes_allowed:false}:{result:'UNKNOWN',activation:'CANDIDATE_ONLY',writes_allowed:false};
  }
  const mappingScore=(field,signals)=>{const evidence_level=field==='UNKNOWN'?null:signals.includes('PROVIDER_ATTRIBUTE')?'LEVEL_1':signals.some(s=>['LABEL_CONTROL','ARIA_LABEL','ARIA_LABELLEDBY'].includes(s))?'LEVEL_2':'LEVEL_3';return {evidence_level,confidence:evidence_level?'PROPOSED':'UNKNOWN'};};
  globalThis.FreightDeskWebBridge=Object.freeze({BrowserSensor:{discover,mapWorkspace:(...a)=>FreightDeskWorkspace.capture(...a)},DOMSnapshot:{capture:snapshot,markClicked,workspace:(...a)=>FreightDeskWorkspace.observeWorkspace(...a)},DOMDiff:{compare:diff,workspaceChanged:(a,b)=>a.shell!==b.shell||JSON.stringify(a.contract)!==JSON.stringify(b.contract)},
    LocatorGraph:{build:graph,containers:containerGraph,mappingFields:(...a)=>FreightDeskWorkspace.fields(...a)},AdaptiveLocator:{propose:remap,selectContainer:chooseContainer,proposeMapping:(a,b)=>({result:a.field_name_candidate!=='UNKNOWN'&&['field_name_candidate','section','semantic_label','control_type','role'].every(k=>a[k]===b[k])?'PROPOSED_READ_REMAP':'UNKNOWN',activation:'CANDIDATE_ONLY',writes_allowed:false})},
    ProviderContract:{fingerprint},EvidenceScorer:{score,container:containerScore,mapping:mappingScore},identityCandidates,diagnostic,
    resetDiagnostic:()=>{lastDiagnostic=null;},limits});
})();
