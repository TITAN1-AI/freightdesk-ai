(() => {
  'use strict';
  const S=FreightDeskMappingScope,W=FreightDeskWebBridge;
  const norm=s=>(s||'').replace(/\s+/g,' ').trim(),key=s=>norm(s).toLowerCase().replace(/\s*\/\s*/g,'/');
  const visible=e=>!!e?.isConnected&&!!e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden'&&!e.closest('[hidden],[aria-hidden="true"]');
  const bound=(a,n)=>{if(a.length>n)throw Error('WORKSPACE_BOUND');return a;};
  const collection=(items,n)=>Array.from(bound(items,n));
  // Label text is admitted before access. Never read aggregate textContent or arbitrary neighbors.
  const privateSelector='[data-private],[contenteditable],input,select,textarea,option,script,style,template';
  function staticText(e){
    if(!e||e.closest(privateSelector))return '';
    let result='',count=0;const stack=[{node:e.firstChild,depth:0}];
    while(stack.length){
      const {node,depth}=stack.pop();if(!node)continue;
      if(++count>32||depth>4)return '';
      if(node.nextSibling)stack.push({node:node.nextSibling,depth});
      if(node.nodeType===3){if(result.length+node.length>128)return '';result+=node.data;}
      else if(node.nodeType===1){
        if(node.matches(privateSelector)||!node.matches('span,b,strong,em,i,small'))return '';
        stack.push({node:node.firstChild,depth:depth+1});
      }
    }
    return result;
  }
  function query(root,selector,maximum=1024){
    // Streaming native iterator: bounds precede JS collection/layout and private descendants are pruned.
    const doc=root.ownerDocument||root;let visited=0;
    const walker=doc.createTreeWalker(root,1,{acceptNode(e){
      if(++visited>4096)throw Error('WORKSPACE_BOUND');
      if(e.matches('[data-private],[contenteditable],script,style,template,option')||e.parentElement?.closest(privateSelector))return 2;
      return e.matches(selector)?1:3;
    }});
    const result=[];let e;while((e=walker.nextNode())){if(result.length>=maximum)throw Error('WORKSPACE_BOUND');result.push(e);}
    return result;
  }
  const selected=e=>e.getAttribute('aria-selected')==='true'||e.getAttribute('aria-current')==='page'||e.getAttribute('aria-current')==='true'||e.classList.contains('active')||e.parentElement?.classList.contains('active');
  const sectionName=s=>S.sections.find(x=>key(x)===key(s))||'DISCOVERED_UNCLASSIFIED';
  const label=s=>Object.keys(S.fields).find(x=>key(x)===key(s))||null;
  const controls='a,button,[role="tab"],[role="button"],[role="link"]';
  const roots='section,form,[role="tabpanel"],[role="region"],[data-section]';
  const loadId=s=>norm(s).match(/^Load\s*#\s*(\d{1,20})$/i)?.[1]||null;
  const proofEligible=e=>!e.closest('form,[role="tabpanel"],[data-section]')&&
    !(e.getAttribute('aria-selected')==='false')&&(!e.closest('[role="tablist"]')||selected(e));
  function pathPattern(doc){
    const parts=doc.location.pathname.split('/').filter(Boolean);if(parts.length>8)return '/:segment';
    return '/'+parts.map((p,i)=>['load','loads'].includes(p)?p:i===1&&['load','loads'].includes(parts[0])&&/^\d{1,20}$/.test(p)?':load_id':':segment').join('/');
  }
  function observeWorkspace(doc,allowed,at,check=()=>{},mark=()=>{},scope=doc){
    if(doc.location.origin!=='https://ascendtms.com')throw Error('WORKSPACE_SCOPE_DENIED');
    check();
    // Bound semantic candidate iteration before layout work; later checks reuse the proved shell.
    const candidates=query(scope,'h1,h2,h3,[role="heading"],'+controls);
    const anchors=[],nav=[];
    for(const e of candidates){
      check();
      if(staticText(e).length>100)continue;
      if(loadId(staticText(e))&&proofEligible(e)&&visible(e))anchors.push(e);
      if(e.matches(controls)&&sectionName(staticText(e))!=='DISCOVERED_UNCLASSIFIED'&&visible(e))nav.push(e);
      bound(anchors,16);bound(nav,64);
    }
    mark('ENTITY_DISCOVERY',{identity_signal_count:anchors.length,section_control_count:nav.length});
    if(!anchors.length&&!nav.length)throw Error('NOT_A_LOAD_WORKSPACE');
    const shells=scope!==doc&&visible(scope)?[scope]:[];
    const hasNav=e=>new Set(nav.filter(n=>e.contains(n)).map(n=>sectionName(staticText(n)))).size>=2;
    for(const a of anchors){for(let e=a.parentElement,depth=0;e&&depth<10;e=e.parentElement,depth++)if(hasNav(e)){shells.push(e);break;}}
    for(const e of bound([...query(scope,'[data-load-workspace],main,[role="main"]')].filter(visible),16))if(hasNav(e))shells.push(e);
    const unique=[...new Set(shells)].filter(e=>!shells.some(other=>other!==e&&e.contains(other)));
    mark('LOAD_WORKSPACE_CANDIDATE_FOUND',{candidate_workspace_count:unique.length},unique.length>0);
    if(!unique.length)throw Error('WORKSPACE_IDENTITY_MISSING');
    if(unique.length!==1)throw Error('WORKSPACE_AMBIGUOUS');
    const shell=unique[0],signals=[];
    for(const a of anchors.filter(e=>shell.contains(e)))signals.push({kind:a.closest('.breadcrumb,[aria-label="breadcrumb"],[aria-label="Breadcrumb"]')?'BREADCRUMB':'HEADER_CONTROL',load_id:loadId(staticText(a)),outside_child_section:true});
    const attributes=[shell,...query(shell,'[data-load-workspace][data-load-id]')].filter(e=>visible(e)&&!e.closest('form,[role="tabpanel"]'));
    for(const e of bound(attributes,16)){const id=e.getAttribute('data-load-id');if(id&&/^\d{1,20}$/.test(id))signals.push({kind:'PROVIDER_ATTRIBUTE',load_id:id,outside_child_section:true});}
    const route=doc.location.pathname.match(/^\/loads?\/(\d{1,20})(?:\/|$)/);
    if(route)signals.push({kind:'ROUTE_ID',load_id:route[1],outside_child_section:true});
    bound(signals,16);if(!signals.length)throw Error('WORKSPACE_IDENTITY_MISSING');
    const ids=new Set(signals.map(s=>s.load_id));if(ids.size!==1)throw Error('WORKSPACE_IDENTITY_CONFLICT');
    const id=[...ids][0];if(allowed!==null&&!allowed.includes(id))throw Error('WORKSPACE_SCOPE_DENIED');
    const sectionControls=S.sections.filter(s=>nav.some(e=>shell.contains(e)&&sectionName(staticText(e))===s));
    mark('WORKSPACE_IDENTITY_VERIFIED',{identity_signal_count:signals.length,section_control_count:sectionControls.length});
    return {shell,identityElements:[...anchors.filter(e=>shell.contains(e)),...attributes.filter(e=>e.hasAttribute('data-load-id'))],nav:nav.filter(e=>shell.contains(e)),contract:{contract:'AscendLoadWorkspaceContract',provider:'AscendTMS',entity_type:'LOAD',source:'provider DOM',load_id:id,confidence:'VERIFIED',signals,
      section_controls:sectionControls,path_pattern:pathPattern(doc),observed_at:at,tenant_identity_source:'OWNER_ATTESTED'}};
  }
  function sectionStructure(workspace,selections){
    const shell=workspace.shell,children=collection(shell.children,1024),headings=[...query(shell,'h1,h2,h3,legend,[role="heading"]')].filter(visible);
    const output={schema_version:1,observation_scope:'VERIFIED_WORKSPACE_ONLY',status:'CAPTURED',selected_controls:[],
      heading_candidate_count:headings.length,heading_candidates:[],workspace_direct_child_count:children.length,workspace_direct_children:[],diagnostic_bounds:[]};
    const tag=e=>['a','button','div','span','li','ul','ol','nav','main','section','form','h1','h2','h3','legend','table','tbody','tr','td'].includes(e?.tagName?.toLowerCase())?e.tagName.toLowerCase():'OTHER';
    const role=e=>['tab','button','link','tablist','tabpanel','region','main','navigation','heading','dialog'].includes(e?.getAttribute('role'))?e.getAttribute('role'):'OTHER';
    const label=e=>{const name=sectionName(staticText(e));return name==='DISCOVERED_UNCLASSIFIED'?'UNCLASSIFIED':name;};
    const markers=e=>{
      const result=[];
      for(const [attribute,value,marker] of [['aria-selected','true','ARIA_SELECTED_TRUE'],['aria-current','page','ARIA_CURRENT_PAGE'],['aria-current','true','ARIA_CURRENT_TRUE']])
        if(e.getAttribute(attribute)===value)result.push(marker);
      if(e.classList.contains('active'))result.push('CLASS_ACTIVE');if(e.parentElement?.classList.contains('active'))result.push('PARENT_CLASS_ACTIVE');return result;
    };
    const within=(category,measured,maximum)=>{if(measured<=maximum)return true;output.status='PARTIAL';output.diagnostic_bounds.push({category,measured,maximum});return false;};
    const shape=(e,attribute)=>{
      const v=e.getAttribute(attribute)||''; // Classify transiently; no attribute value leaves this function.
      if(!v)return 'EMPTY';if(v==='#')return 'EMPTY_FRAGMENT';
      if(/^#[\w-]+$/.test(v))return 'FRAGMENT';
      if(attribute==='aria-controls'&&/^[\w-]+$/.test(v))return 'SINGLE_ID';
      if(attribute==='aria-controls'&&/^[\w-]+(?:\s+[\w-]+)+$/.test(v))return 'ID_LIST';
      if(/^javascript:/i.test(v.trim()))return 'SCRIPT_REFERENCE';
      if(/^\/(?!\/)/.test(v))return 'RELATIVE_PATH';
      if(/^https:\/\/ascendtms\.com(?:[/?#]|$)/i.test(v))return 'SAME_ORIGIN_URL';return 'OTHER';
    };
    const destination=control=>{
      if(control.tagName!=='A'||!control.hasAttribute('href')||shape(control,'href')==='SCRIPT_REFERENCE')return null;
      try{const url=new URL(control.getAttribute('href'),shell.ownerDocument.location.href);
        if(!['http:','https:'].includes(url.protocol))return null;
        return {same_origin:url.origin===shell.ownerDocument.location.origin,same_path:url.pathname===shell.ownerDocument.location.pathname,
          fragment_present:url.href.includes('#'),query_present:url.href.split('#')[0].includes('?')};
      }catch{return null;}
    };
    if(within('SELECTED_CONTROLS',selections.length,24))output.selected_controls=selections.map((control,candidate_index)=>({
      candidate_index,section_label:label(control),tag:tag(control),role:role(control),state_markers:markers(control),
      references:[['aria-controls','ARIA_CONTROLS'],['href','HREF'],['data-target','DATA_TARGET'],['data-bs-target','DATA_BS_TARGET']]
        .filter(([attribute])=>control.hasAttribute(attribute)).map(([attribute,name])=>({attribute:name,shape:shape(control,attribute)})),
      id_present:control.hasAttribute('id'),aria_labelledby_present:control.hasAttribute('aria-labelledby'),onclick_present:control.hasAttribute('onclick'),
      parent_tag:tag(control.parentElement),parent_role:role(control.parentElement),workspace_child_index:children.findIndex(e=>e===control||e.contains(control))<0?null:children.findIndex(e=>e===control||e.contains(control)),
      anchor_destination:destination(control),
    }));
    const headingsBound=within('HEADING_CANDIDATES',headings.length,48);
    if(headingsBound)output.heading_candidates=headings.map((heading,candidate_index)=>{
      const root=heading.closest(roots),name=label(heading);
      const root_kind=!root?'NONE':root.matches('section')?'SECTION':root.matches('form')?'FORM':root.getAttribute('role')==='tabpanel'?'TABPANEL':root.getAttribute('role')==='region'?'REGION':'DATA_SECTION';
      const predicate=name==='UNCLASSIFIED'?'NOT_RECOGNIZED_LABEL':!root?'NO_SUPPORTED_ROOT':root===shell?'ROOT_IS_WORKSPACE':!shell.contains(root)?'ROOT_OUTSIDE_WORKSPACE':root.querySelector('[role="tablist"]')?'ROOT_CONTAINS_TABLIST':'ACCEPTED';
      return {candidate_index,section_label:name,tag:tag(heading),root_kind,predicate};
    });
    if(within('WORKSPACE_DIRECT_CHILDREN',children.length,24))output.workspace_direct_children=children.map((child,child_index)=>({
      child_index,tag:tag(child),role:role(child),visible:visible(child),child_element_count:child.children.length,
      known_navigation_control_count:workspace.nav.filter(e=>child===e||child.contains(e)).length,
      selected_control_count:selections.filter(e=>child===e||child.contains(e)).length,
      descendant_field_control_count:query(child,'input,select,textarea,output,[role="textbox"],[role="combobox"],[role="checkbox"],[data-field]').length,
      immediate_heading_labels:headingsBound?collection(child.children,1024).filter(e=>e.matches('h1,h2,h3,legend,[role="heading"]')&&visible(e)).map(label):[],
    }));
    return output;
  }
  function siblingFormSection(workspace,heading,headings,name){
    const shell=workspace.shell,diagnostic={strategy:'NEAREST_HEADING_CONTEXT_UNIQUE_LATER_FORM_REGION',context_count:0,
      selected_context_depth:null,context_candidates:[],failed_predicate:null};
    const stop=predicate=>{diagnostic.failed_predicate=predicate;return {root:null,diagnostic};};
    let context=heading.parentElement,depth=1;
    for(;context&&context!==shell&&shell.contains(context)&&depth<=8;context=context.parentElement,depth++){
      const children=[...context.children],record={ancestor_depth:depth,direct_child_count:children.length,form_candidate_count:null,visible_form_count:null,field_candidate_count:null,
        heading_child_count:null,form_bearing_child_count:null,heading_child_index:null,form_child_index:null,
        all_visible_forms_contained:null,predicate:'NOT_DIV'};
      diagnostic.context_count=depth;diagnostic.context_candidates.push(record);
      const reject=predicate=>{record.predicate=predicate;return stop(predicate);};
      if(context.tagName!=='DIV')continue;
      if(!visible(context)){record.predicate='NOT_VISIBLE';continue;}
      if(workspace.identityElements.some(e=>context===e||context.contains(e)))return reject('CONTEXT_CONTAINS_IDENTITY');
      if(headings.some(e=>context.contains(e)&&sectionName(staticText(e))!=='DISCOVERED_UNCLASSIFIED'&&sectionName(staticText(e))!==name))
        return reject('CONTEXT_CONTAINS_OTHER_HEADING');
      if(children.length>24)return reject('DIRECT_CHILD_BOUND');
      const forms=[...query(context,'form')];record.form_candidate_count=forms.length;
      if(forms.length>16)return reject('CONTEXT_FORM_BOUND');
      const shown=forms.filter(visible);record.visible_form_count=shown.length;
      if(!shown.length){record.predicate='NO_VISIBLE_CONTEXT_FORMS';continue;}
      // The nearest form-bearing context is authoritative for this bounded relationship.
      // Never climb past split form branches and turn their outer wrapper into a false singleton.
      const headingChildren=children.filter(e=>visible(e)&&(e===heading||e.contains(heading)));
      record.heading_child_count=headingChildren.length;
      if(headingChildren.length!==1)return reject('HEADING_CHILD_NOT_UNIQUE');
      const regions=children.filter(e=>visible(e)&&shown.some(form=>e===form||e.contains(form)));
      record.form_bearing_child_count=regions.length;
      if(regions.length!==1)return reject('FORM_CHILD_NOT_UNIQUE');
      const root=regions[0];record.heading_child_index=children.indexOf(headingChildren[0]);record.form_child_index=children.indexOf(root);
      if(record.form_child_index<=record.heading_child_index)return reject('FORM_REGION_PRECEDES_HEADING');
      if(root.tagName!=='DIV')return reject('FORM_REGION_NOT_DIV');
      record.all_visible_forms_contained=shown.every(form=>root.contains(form));
      if(!record.all_visible_forms_contained)return reject('FORM_REGION_NOT_ALL_FORMS');
      if(workspace.identityElements.some(e=>root===e||root.contains(e)))return reject('FORM_REGION_CONTAINS_IDENTITY');
      if(workspace.nav.some(e=>root===e||root.contains(e)))return reject('FORM_REGION_CONTAINS_NAVIGATION');
      if(headings.some(e=>root.contains(e)&&sectionName(staticText(e))!=='DISCOVERED_UNCLASSIFIED'&&sectionName(staticText(e))!==name))
        return reject('FORM_REGION_CONTAINS_OTHER_HEADING');
      let fieldCount=0,hasVisibleFields=false;record.field_candidate_count=0;
      for(const form of shown){
        const items=[...query(form,'input,select,textarea,output,[role="textbox"],[role="combobox"],[role="checkbox"],[role="status"],[data-field]')];
        fieldCount+=items.length;record.field_candidate_count=fieldCount;if(fieldCount>256)return reject('FORM_FIELD_BOUND');
        if(items.some(e=>visible(e)&&!e.matches('[type="hidden"],[type="password"],[type="submit"],[type="reset"],[type="button"]')))hasVisibleFields=true;
      }
      if(!hasVisibleFields)return reject('NO_VISIBLE_FORM_FIELDS');
      record.predicate='ELIGIBLE';diagnostic.selected_context_depth=depth;
      return {root,diagnostic};
    }
    return stop(context&&context!==shell&&shell.contains(context)&&depth>8?'CONTEXT_ANCESTOR_BOUND':'NO_ELIGIBLE_CONTEXT');
  }
  function routeHeadingSection(workspace,selections,headings){
    const shell=workspace.shell,diagnostic={strategy:'SELECTED_CURRENT_ROUTE_AND_MATCHING_HEADING',route_anchor_candidate_count:0,
      matching_heading_count:0,ancestor_count:0,eligible_root_count:0,selected_ancestor_depth:null,visible_field_candidate_count:null,
      root_relationship:null,sibling_form_diagnostic:null,ancestor_candidates:[],failed_predicate:null};
    const stop=predicate=>{diagnostic.failed_predicate=predicate;return {section:null,diagnostic};};
    // The observed provider route and heading must agree independently of the requested section.
    const anchors=selections.filter(control=>{
      if(control.tagName!=='A'||sectionName(staticText(control))==='DISCOVERED_UNCLASSIFIED')return false;
      const href=control.getAttribute('href');if(!href?.trim()||/^javascript:/i.test(href.trim()))return false;
      try{const url=new URL(href,shell.ownerDocument.location.href);
        return url.origin===shell.ownerDocument.location.origin&&url.pathname===shell.ownerDocument.location.pathname&&
          !url.username&&!url.password&&!url.href.includes('#')&&!url.href.includes('?');
      }catch{return false;}
    });
    diagnostic.route_anchor_candidate_count=anchors.length;
    if(!anchors.length)return stop('ROUTE_ANCHOR_COUNT_ZERO');
    if(anchors.length!==1)return stop('ROUTE_ANCHOR_COUNT_MULTIPLE');
    const name=sectionName(staticText(anchors[0])),matching=headings.filter(e=>sectionName(staticText(e))===name);
    diagnostic.matching_heading_count=matching.length;
    if(!matching.length)return stop('MATCHING_HEADING_COUNT_ZERO');
    if(matching.length!==1)return stop('MATCHING_HEADING_COUNT_MULTIPLE');
    let root=matching[0].parentElement,depth=1;
    for(;root&&root!==shell&&shell.contains(root)&&depth<=8;root=root.parentElement,depth++){
      const record={ancestor_depth:depth,tag:['div','section','form','main','nav','span'].includes(root.tagName.toLowerCase())?root.tagName.toLowerCase():'OTHER',
        form_candidate_count:null,visible_form_count:null,field_candidate_count:null,forms_with_visible_fields:null,predicate:'NOT_DIV'};
      diagnostic.ancestor_count=depth;diagnostic.ancestor_candidates.push(record);
      if(root.tagName!=='DIV')continue;
      if(!visible(root)){record.predicate='NOT_VISIBLE';continue;}
      if(workspace.identityElements.some(e=>root===e||root.contains(e))){record.predicate='CONTAINS_WORKSPACE_IDENTITY';continue;}
      if(workspace.nav.some(e=>root===e||root.contains(e))){record.predicate='CONTAINS_SECTION_NAVIGATION';continue;}
      if(headings.some(e=>root.contains(e)&&sectionName(staticText(e))!=='DISCOVERED_UNCLASSIFIED'&&sectionName(staticText(e))!==name)){
        record.predicate='CONTAINS_OTHER_SECTION_HEADING';continue;
      }
      const forms=[...query(root,'form')];record.form_candidate_count=forms.length;
      if(forms.length>16){record.predicate='FORM_CANDIDATE_BOUND';continue;}
      const shown=forms.filter(visible);record.visible_form_count=shown.length;
      record.field_candidate_count=0;record.forms_with_visible_fields=0;
      for(const form of shown){
        const fields=[...query(form,'input,select,textarea,output,[role="textbox"],[role="combobox"],[role="checkbox"],[role="status"],[data-field]')];
        record.field_candidate_count+=fields.length;
        if(record.field_candidate_count>256){record.predicate='FORM_FIELD_CANDIDATE_BOUND';break;}
        if(fields.some(e=>!e.matches('[type="hidden"],[type="password"],[type="submit"],[type="reset"],[type="button"]')&&visible(e)))record.forms_with_visible_fields++;
      }
      if(record.predicate==='FORM_FIELD_CANDIDATE_BOUND')continue;
      if(!record.forms_with_visible_fields){record.predicate='NO_VISIBLE_FORM_FIELDS';continue;}
      record.predicate='ELIGIBLE';diagnostic.eligible_root_count=1;diagnostic.selected_ancestor_depth=depth;diagnostic.root_relationship='ANCESTOR_FORM_REGION';
      diagnostic.visible_field_candidate_count=[...query(root,'input,select,textarea,output,[role="textbox"],[role="combobox"],[role="checkbox"],[role="status"],[data-field]')]
        .filter(visible).filter(e=>!e.matches('[type="hidden"],[type="password"],[type="submit"],[type="reset"],[type="button"]')).length;
      // One matching heading gives one ancestor chain. Choose its innermost eligible form region;
      // coverage remains CURRENT_VISIBLE_SECTION_ONLY, never the whole Load Basics workspace.
      return {section:{root,name,signal:'SELECTED_ROUTE_AND_VISIBLE_HEADING'},diagnostic};
    }
    const sibling=siblingFormSection(workspace,matching[0],headings,name);diagnostic.sibling_form_diagnostic=sibling.diagnostic;
    if(sibling.root){
      diagnostic.root_relationship='SIBLING_FORM_REGION';diagnostic.eligible_root_count=1;
      diagnostic.visible_field_candidate_count=[...query(sibling.root,'input,select,textarea,output,[role="textbox"],[role="combobox"],[role="checkbox"],[role="status"],[data-field]')]
        .filter(visible).filter(e=>!e.matches('[type="hidden"],[type="password"],[type="submit"],[type="reset"],[type="button"]')).length;
      return {section:{root:sibling.root,name,signal:'SELECTED_ROUTE_AND_VISIBLE_HEADING'},diagnostic};
    }
    return stop(root&&root!==shell&&shell.contains(root)&&depth>8?'ANCESTOR_BOUND':'NO_ELIGIBLE_ROOT');
  }
  function observeSection(workspace){
    const shell=workspace.shell,markers=new Set(),relationships=new Set(),labels=new Set();
    const diagnostic={schema_version:1,selected_candidate_count:0,recognized_section_labels:[],approved_state_markers:[],
      target_relationship_kinds:[],visible_target_count:0,heading_root_count:0,unique_candidate_count:0,failed_predicate:null};
    const safeLabel=text=>{const name=sectionName(text);labels.add(name==='DISCOVERED_UNCLASSIFIED'?'UNCLASSIFIED':name);return name;};
    const snapshot=()=>({...diagnostic,recognized_section_labels:[...labels].sort(),approved_state_markers:[...markers].sort(),target_relationship_kinds:[...relationships].sort()});
    const fail=(predicate,code='WORKSPACE_SECTION_UNVERIFIED')=>{
      diagnostic.failed_predicate=predicate;
      try{diagnostic.structure_diagnostic=sectionStructure(workspace,selections);}catch{
        diagnostic.structure_diagnostic={schema_version:1,observation_scope:'VERIFIED_WORKSPACE_ONLY',status:'UNAVAILABLE',selected_controls:[],
          heading_candidate_count:null,heading_candidates:[],workspace_direct_child_count:null,workspace_direct_children:[],diagnostic_bounds:[]};
      }
      const error=Error(code);error.section_diagnostic=snapshot();throw error;
    };
    for(const e of workspace.nav)safeLabel(staticText(e));
    const selections=[...query(shell,controls)].filter(visible).filter(selected).filter(e=>!loadId(staticText(e)));
    diagnostic.selected_candidate_count=selections.length;
    for(const control of selections.slice(0,24)){
      safeLabel(staticText(control));
      for(const [attribute,value,marker] of [['aria-selected','true','ARIA_SELECTED_TRUE'],['aria-current','page','ARIA_CURRENT_PAGE'],['aria-current','true','ARIA_CURRENT_TRUE']])
        if(control.getAttribute(attribute)===value)markers.add(marker);
      if(control.classList.contains('active'))markers.add('CLASS_ACTIVE');
      if(control.parentElement?.classList.contains('active'))markers.add('PARENT_CLASS_ACTIVE');
    }
    if(selections.length>24)fail('SELECTED_CANDIDATE_BOUND','WORKSPACE_BOUND');
    const candidates=[],visibleTargets=new Set();let proofHeadings=[];
    for(const control of selections){
      const name=sectionName(staticText(control)),refs=[];
      for(const [attribute,kind] of [['aria-controls','ARIA_CONTROLS'],['href','FRAGMENT'],['data-target','DATA_TARGET'],['data-bs-target','DATA_BS_TARGET']]){
        const value=control.getAttribute(attribute)||'';
        const id=attribute==='aria-controls'&&/^[\w-]+$/.test(value)?value:/^#[\w-]+$/.test(value)?value.slice(1):null;
        if(id){relationships.add(kind);refs.push(...query(shell,'#'+CSS.escape(id)));}
      }
      if(control.id){
        const labelled=[...query(shell,'[role="tabpanel"][aria-labelledby]')].filter(e=>e.getAttribute('aria-labelledby').split(/\s+/).includes(control.id));
        if(labelled.length)relationships.add('LABELLEDBY');refs.push(...labelled);
      }
      for(const root of [...new Set(refs)].filter(e=>visible(e)&&e!==shell&&shell.contains(e)&&!e.contains(control))){
        visibleTargets.add(root);diagnostic.visible_target_count=visibleTargets.size;
        if(visibleTargets.size>96)fail('VISIBLE_TARGET_BOUND','WORKSPACE_BOUND');
        candidates.push({root,name,signal:'SELECTED_CONTROL'});
      }
    }
    if(!candidates.length){
      const headings=[...query(shell,'h1,h2,h3,legend,[role="heading"]')].filter(visible),headingRoots=new Set();
      if(headings.length>48)fail('HEADING_CANDIDATE_BOUND','WORKSPACE_BOUND');
      proofHeadings=headings;
      for(const h of headings){
        const name=sectionName(staticText(h)),root=h.closest(roots);
        if(name!=='DISCOVERED_UNCLASSIFIED')safeLabel(staticText(h));
        if(name!=='DISCOVERED_UNCLASSIFIED'&&root&&root!==shell&&shell.contains(root)&&!root.querySelector('[role="tablist"]')){
          headingRoots.add(root);candidates.push({root,name,signal:'VISIBLE_HEADING'});
        }
      }
      diagnostic.heading_root_count=headingRoots.size;
    }
    let unique=candidates.filter((c,i)=>candidates.findIndex(x=>x.root===c.root&&x.name===c.name)===i);
    if(!unique.length){
      const fallback=routeHeadingSection(workspace,selections,proofHeadings);
      diagnostic.route_heading_diagnostic=fallback.diagnostic;
      if(fallback.section)unique=[fallback.section];
    }
    diagnostic.unique_candidate_count=unique.length;
    if(!unique.length)fail('UNIQUE_CANDIDATE_COUNT_ZERO');
    if(unique.length!==1)fail('UNIQUE_CANDIDATE_COUNT_MULTIPLE');
    if(workspace.identityElements.some(e=>unique[0].root.contains(e)))fail('SECTION_CONTAINS_WORKSPACE_IDENTITY','WORKSPACE_IDENTITY_MISSING');
    return {...unique[0],diagnostic:snapshot()};
  }
  function relativePath(e,root){const parts=[];for(let n=e;n!==root;n=n.parentElement){if(!n?.parentElement||parts.length>=12)throw Error('WORKSPACE_BOUND');parts.unshift([...n.parentElement.children].indexOf(n));}return parts;}
  function navigationTarget(control,shell){
    if(control.getAttribute('role')!=='tab'||!['A','BUTTON'].includes(control.tagName)||control.closest('form')||
      control.tagName==='BUTTON'&&control.type!=='button'||control.hasAttribute('disabled')||control.getAttribute('aria-disabled')==='true')return null;
    if(control.tagName==='A'&&!/^#[\w-]+$/.test(control.getAttribute('href')||''))return null;
    const found=[];
    for(const [attr,kind] of [['aria-controls','ARIA_CONTROLS'],['href','FRAGMENT'],['data-target','DATA_TARGET'],['data-bs-target','DATA_TARGET']]){
      const value=control.getAttribute(attr)||'',id=attr==='aria-controls'&&/^[\w-]+$/.test(value)?value:/^#[\w-]+$/.test(value)?value.slice(1):null;
      if(id)for(const target of query(shell,'#'+CSS.escape(id)))if(target!==shell&&!target.contains(control))found.push({target,kind});
    }
    if(!found.length&&control.id)for(const target of query(shell,'[role="tabpanel"][aria-labelledby]'))
      if(target.getAttribute('aria-labelledby').split(/\s+/).includes(control.id))found.push({target,kind:'LABELLEDBY'});
    const targets=[...new Set(found.map(f=>f.target))];return targets.length===1?found[0]:null;
  }
  async function navigationCandidates(workspace){
    const candidates=[];
    for(const control of workspace.nav){
      const ref=navigationTarget(control,workspace.shell);if(!ref)continue;
      const structure={section:sectionName(staticText(control)),tag:control.tagName.toLowerCase(),role:'tab',control_type:control.tagName==='BUTTON'?'button':'anchor',
        reference:ref.kind,relative_path:relativePath(control,workspace.shell),target_relative_path:relativePath(ref.target,workspace.shell),same_document_target:true};
      candidates.push({...structure,fingerprint:await W.ProviderContract.fingerprint(structure)});
    }
    return bound(candidates,13);
  }
  async function fields(section,id,at,check=()=>{}){
    const root=section.root,result=[];
    const items=bound([...query(root,'input,select,textarea,output,[role="textbox"],[role="combobox"],[role="checkbox"],[role="status"],[data-field]')].filter(visible).filter(e=>!e.matches('[type="hidden"],[type="password"],[type="submit"],[type="reset"],[type="button"]')),64);
    for(const e of items){
      check();
      const signals=[],labels=[],nativeLabels=collection(e.labels||[],32);
      for(const l of nativeLabels)if(root.contains(l)&&visible(l)&&label(staticText(l))){signals.push('LABEL_CONTROL');labels.push(label(staticText(l)));}
      if(label(e.getAttribute('aria-label'))){signals.push('ARIA_LABEL');labels.push(label(e.getAttribute('aria-label')));}
      for(const id of bound((e.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean),8)){
        const l=e.ownerDocument.getElementById(id);if(l&&root.contains(l)&&visible(l)&&label(staticText(l))){signals.push('ARIA_LABELLEDBY');labels.push(label(staticText(l)));}
      }
      const neighbor=e.previousElementSibling,near=neighbor?.matches('label,legend')&&visible(neighbor)?label(staticText(neighbor)):null;
      if(near&&!labels.length){signals.push('NEIGHBOR');labels.push(near);}
      const provider=e.getAttribute('data-field'),keys=[...new Set(labels.map(l=>S.fields[l]))];
      if(Object.values(S.fields).includes(provider)){signals.push('PROVIDER_ATTRIBUTE');keys.push(provider);}
      const unknownExplicit=nativeLabels.some(l=>root.contains(l)&&visible(l)&&!label(staticText(l)))||
        e.hasAttribute('aria-label')&&!label(e.getAttribute('aria-label'))||provider!==null&&!Object.values(S.fields).includes(provider);
      const names=[...new Set(keys)],field=names.length===1&&!unknownExplicit?names[0]:'UNKNOWN';
      if(e.hasAttribute('role'))signals.push('CONTROL_ROLE');
      const graph={signals:[...new Set(signals)],relative_path:relativePath(e,root),neighboring_labels:near?[near]:[],
        data_attribute_names:[...new Set(collection(e.attributes,32).filter(a=>a.name.startsWith('data-')).map(a=>S.data_attributes.includes(a.name)?a.name:'data-unclassified'))],
        aria_relationships:['labelledby','describedby','controls'].filter(a=>e.hasAttribute('aria-'+a))};
      const score=W.EvidenceScorer.mapping(field,signals);
      const type=e.tagName==='SELECT'?'select':e.tagName==='TEXTAREA'?'textarea':e.tagName==='OUTPUT'?'output':e.tagName!=='INPUT'?'STATIC':
        ['text','tel','email','number','date','time','datetime-local','checkbox'].includes(e.type)?e.type:'OTHER';
      const value={field_name_candidate:field,section:section.name,semantic_label:labels.length?labels[0]:'UNCLASSIFIED_LABEL',control_type:type,
        editable:!e.disabled&&!e.readOnly&&(e.matches('input,select,textarea')||e.getAttribute('contenteditable')==='true'),
        role:['textbox','combobox','checkbox','status'].includes(e.getAttribute('role'))?e.getAttribute('role'):'OTHER',locator_graph:graph,
        ...score};
      result.push({...value,presence:'VISIBLE',optionality:'UNKNOWN',observed_on_load:id,observed_at:at,contract_fingerprint:await W.ProviderContract.fingerprint(value)});
    }
    return result;
  }
  async function capture(doc,allowed,lease,progress=()=>{},started=performance.now(),target={},hooks={}){
    let diagnostic={stage:'SESSION_VERIFIED',candidate_workspace_count:0,identity_signal_count:0,section_control_count:0,elapsed_ms:0};
    const check=()=>{lease();if(performance.now()-started>=3000)throw Error('READ_TIMEOUT');};
    const mark=(stage,counts={},complete=true)=>{Object.assign(diagnostic,counts);if(complete){diagnostic.stage=stage;diagnostic.elapsed_ms=Math.floor(performance.now()-started);progress({...diagnostic});}check();};
    // Yield to deliver the session receipt before bounded DOM discovery.
    await new Promise(r=>setTimeout(r,0));check();
    const at=Date.now()/1000,before=observeWorkspace(doc,target.capture_load_id?null:allowed,at,check,mark);
    if(target.capture_load_id&&before.contract.load_id!==target.capture_load_id)throw Error('EXPECTED_LOAD_NOT_OPEN');
    const section=observeSection(before);
    mark('SECTION_IDENTIFIED',{section_diagnostic:section.diagnostic});
    if(target.capture_section&&section.name!==target.capture_section)throw Error('STARTING_SECTION_MISMATCH');
    hooks.onVerified?.({workspace:before,section});check();
    await new Promise(r=>setTimeout(r,0));check();
    const stops = section.name==='Edit Stops' && globalThis.FreightDeskStopsMetadata ? FreightDeskStopsMetadata.inspect(section.root,check) : null;
    if(stops && !['SELECTED_CONTROL','SELECTED_ROUTE_AND_VISIBLE_HEADING'].includes(section.signal))throw Error('WORKSPACE_SECTION_UNVERIFIED');
    const metadata=stops?[]:await W.LocatorGraph.mappingFields(section,before.contract.load_id,at,check);
    const headings=bound([...query(section.root,'h1,h2,h3,legend,[role="heading"]')].filter(visible),24).map(e=>sectionName(staticText(e))==='DISCOVERED_UNCLASSIFIED'?'UNCLASSIFIED_LABEL':sectionName(staticText(e)));
    const actions=stops?[]:bound([...query(section.root,'button,a,[role="button"]')].filter(visible),32).map(e=>S.actions.find(a=>key(a)===key(staticText(e)))||S.sections.find(a=>key(a)===key(staticText(e)))||'UNCLASSIFIED_LABEL');
    await new Promise(r=>setTimeout(r,150));check();
    const after=observeWorkspace(doc,allowed,at,check,()=>{},before.shell),current=observeSection(after);
    if(W.DOMDiff.workspaceChanged(before,after)||current.root!==section.root||current.name!==section.name||
      JSON.stringify(metadata)!==JSON.stringify(stops?[]:await fields(current,after.contract.load_id,at,check)))throw Error('WORKSPACE_CHANGED');
    if(stops){const refreshed=FreightDeskStopsMetadata.inspect(current.root,check);if(stops.bindings.length!==refreshed.bindings.length||stops.bindings.some((e,i)=>e!==refreshed.bindings[i])||JSON.stringify(stops.metadata)!==JSON.stringify(refreshed.metadata))throw Error('WORKSPACE_CHANGED');}
    check();
    before.contract.shell_fingerprint=await W.ProviderContract.fingerprint({signals:[...new Set(before.contract.signals.map(s=>s.kind))].sort(),sections:before.contract.section_controls});
    before.contract.navigation_candidates=await navigationCandidates(before);
    const contract={contract:'AscendLoadSectionContract',section:section.name,workspace_load_id:before.contract.load_id,identity_source:'INHERITED_FROM_REVALIDATED_WORKSPACE',section_signal:section.signal,
      headings,action_controls:actions,fields:metadata,coverage:'CURRENT_VISIBLE_SECTION_ONLY',fingerprint:await W.ProviderContract.fingerprint({section:section.name,headings,actions,fields:metadata.map(f=>f.contract_fingerprint)})};
    if(stops){contract.stops_metadata=stops.metadata;contract.fingerprint=await W.ProviderContract.fingerprint({section:section.name,headings,actions,fields:[],stops_metadata:stops.metadata});}
    const output={schema_version:1,provider:'AscendTMS',source:'live extension DOM',workspace:before.contract,section:contract,revalidated_after_capture:true,activation:'CANDIDATE_ONLY',values_included:false,writes_allowed:false,owner_present:doc.visibilityState==='visible'&&doc.hasFocus()};
    if(new TextEncoder().encode(JSON.stringify(output)).length>45000)throw Error('MAPPING_PAYLOAD_BOUND');
    mark('STRUCTURE_CAPTURED');check();return output;
  }
  async function navigate(doc,command,check){
    check();const proof=await capture(doc,command.approved_load_ids,check),contract=command.navigation;
    if(proof.workspace.load_id!==command.load_id||proof.workspace.shell_fingerprint!==contract.workspace_fingerprint)throw Error('WORKSPACE_CHANGED');
    if(proof.section.section!==command.expected_from_section)throw Error('AUTO_MAP_SECTION_UNVERIFIED');
    if(contract.classification!=='READ_ONLY_NAVIGATION'||contract.confidence!=='VERIFIED')throw Error('NAVIGATION_CONTRACT_UNVERIFIED');
    const w=observeWorkspace(doc,command.approved_load_ids,proof.workspace.observed_at),target=contract.candidate;
    const candidates=await navigationCandidates(w),matches=candidates.filter(c=>c.section===target.section&&c.fingerprint===target.fingerprint);
    if(matches.length!==1||candidates.filter(c=>c.section===target.section).length!==1)throw Error('NAVIGATION_CONTROL_AMBIGUOUS');
    let control=w.shell;for(const i of target.relative_path)control=control?.children[i];
    if(!control||!visible(control)||sectionName(staticText(control))!==target.section||!navigationTarget(control,w.shell))throw Error('NAVIGATION_CONTROL_CHANGED');
    const relation=navigationTarget(control,w.shell);
    if(relation.kind!==target.reference||JSON.stringify(relativePath(relation.target,w.shell))!==JSON.stringify(target.target_relative_path))throw Error('NAVIGATION_CONTROL_CHANGED');
    check();const immediate=observeWorkspace(doc,command.approved_load_ids,proof.workspace.observed_at);
    if(immediate.contract.load_id!==command.load_id||observeSection(immediate).name!==command.expected_from_section)throw Error('WORKSPACE_CHANGED');
    // The only AUTO_MAP action: a current provider tab previously approved as read-only navigation.
    control.click();
    const until=Date.now()+4000;
    while(Date.now()<until){
      await new Promise(r=>setTimeout(r,100));check();const after=observeWorkspace(doc,command.approved_load_ids,Date.now()/1000);
      if(after.contract.load_id!==command.load_id)throw Error('WORKSPACE_CHANGED');
      const child=observeSection(after);
      if(child.name===target.section){const observed=await capture(doc,command.approved_load_ids,check);
        if(observed.workspace.load_id!==command.load_id||observed.workspace.shell_fingerprint!==contract.workspace_fingerprint||observed.section.section!==target.section)throw Error('WORKSPACE_CHANGED');
        return observed;}
      if(child.name!==command.expected_from_section)throw Error('AUTO_MAP_SECTION_UNVERIFIED');
    }
    throw Error('AUTO_MAP_SECTION_UNVERIFIED');
  }
  globalThis.FreightDeskWorkspace=Object.freeze({readerRevision:2,capture,navigate,observeWorkspace,observeSection,pathPattern,fields,navigationCandidates});
})();
