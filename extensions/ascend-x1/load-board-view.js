(() => {
  'use strict';
  const maxCandidates=32;
  const classes=['active','selected','is-active','ui-tabs-active','ui-state-active'];
  const labels={'Active Loads':'ACTIVE_LOADS','All Loads':'ALL_LOADS','Ready for Accounting':'READY_FOR_ACCOUNTING'};
  const normalize=s=>(s||'').replace(/[_-]/g,' ').replace(/\s+/g,' ').trim().toLowerCase();
  const labelFor=s=>Object.keys(labels).find(label=>normalize(label)===normalize(s))||null;
  const controlLabel=e=>labelFor(e.getAttribute('aria-label'))||labelFor(e.textContent);
  const visible=e=>!!e?.getClientRects().length&&getComputedStyle(e).visibility!=='hidden'&&
    !e.closest('[hidden],[aria-hidden="true"]');
  const excluded=e=>!!e.closest('table,[role="grid"],dialog,[role="dialog"],.modal,.side-panel,form');
  const controlSelector='a,button,[role="tab"],[role="link"],[role="button"]';
  const stateClasses=e=>classes.filter(c=>e?.classList.contains(c));
  const flag=(e,name)=>e.getAttribute(name)==='true'?true:e.getAttribute(name)==='false'?false:null;
  function classify(candidates,overflow=false){
    let reason='NO_PROVIDER_SIGNAL',view='UNKNOWN',confidence='UNKNOWN';
    const shown=candidates.filter(c=>c.visible);
    const selected=c=>c.aria_selected===true||c.aria_pressed===true||c.aria_current||c.active||c.parent_active;
    const selectedControls=shown.filter(c=>c.kind==='CONTROL'&&selected(c));
    const conflict=shown.some(c=>c.conflicting_identity||
      c.kind==='CONTROL'&&selected(c)&&(c.aria_selected===false||c.aria_pressed===false));
    const signals=shown.filter(c=>c.kind!=='CONTROL'||selected(c)||
      c.unique_linked_panel&&c.visible_linked_panel&&c.aria_selected!==false&&c.aria_pressed!==false);
    if(overflow)reason='CANDIDATE_BOUND';
    else if(conflict)reason='CONFLICTING_PROVIDER_SIGNALS';
    else if(selectedControls.length>1||new Set(signals.map(c=>c.view)).size>1)reason='AMBIGUOUS_PROVIDER_SIGNALS';
    else if(signals.length){view=signals[0].view;confidence='VERIFIED';reason='PROVIDER_SIGNAL';}
    return {view,confidence,reason};
  }
  function observe(doc){
    const records=[],nodes=[],panels=[],groups=[];
    const controls=[...doc.querySelectorAll(controlSelector)].filter(e=>!excluded(e));
    const named=controls.filter(e=>controlLabel(e)||['data-board-view','data-load-board-view','data-view'].some(a=>labelFor(e.getAttribute(a))));
    const relevantGroups=new Set(named.map(e=>e.closest('[role="tablist"],.nav-tabs,.nav-pills')).filter(Boolean));
    function candidate(e,kind){
      const textLabel=kind==='CONTAINER'?null:controlLabel(e),data=[];
      const namedLabels=kind==='CONTAINER'?[]:[labelFor(e.textContent),labelFor(e.getAttribute('aria-label'))].filter(Boolean);
      for(const attr of ['data-board-view','data-load-board-view','data-view']){
        const value=e.getAttribute(attr);
        if(value!==null){const label=labelFor(value);if(label)data.push(labels[label]);
          else if(attr!=='data-view'&&value.trim())data.push('OTHER');}
      }
      const view=(textLabel&&labels[textLabel])||data[0]||'OTHER';
      const parent=e.parentElement;
      const singleParent=kind==='CONTROL'&&parent?.matches('li,[role="presentation"]')&&
        named.filter(n=>parent.contains(n)).length===1;
      const ownClasses=stateClasses(e),parentClasses=singleParent?stateClasses(parent):[];
      return {kind,label:textLabel||Object.keys(labels).find(l=>labels[l]===view)||'OTHER',view,visible:visible(e),
        aria_selected:flag(e,'aria-selected'),aria_pressed:flag(e,'aria-pressed'),aria_current:['page','true'].includes(e.getAttribute('aria-current')),
        active:ownClasses.length>0,parent_active:parentClasses.length>0,safe_classes:ownClasses,parent_safe_classes:parentClasses,
        data_view:data[0]||null,conflicting_identity:data.some(v=>v!==view)||namedLabels.some(l=>labels[l]!==view),visible_linked_panel:false,unique_linked_panel:false};
    }
    function add(e,kind){
      if(nodes.includes(e))return;
      nodes.push(e);records.push(candidate(e,kind));
    }
    for(const e of controls){
      if(named.includes(e)||[...relevantGroups].some(g=>g.contains(e)))add(e,'CONTROL');
      if(records.length>maxCandidates)break;
    }
    if(records.length<=maxCandidates)for(const e of doc.querySelectorAll('h1,h2,[role="heading"],[data-board-view],[data-load-board-view]')){
      if(excluded(e)||e.closest('nav,aside,[role="navigation"],[role="tablist"]')||e.matches(controlSelector))continue;
      if(e.matches('h1,h2,[role="heading"]')&&labelFor(e.textContent))add(e,'TITLE');
      else if((e.hasAttribute('data-board-view')||e.hasAttribute('data-load-board-view'))&&e.querySelector('table,[role="grid"]'))add(e,'CONTAINER');
      if(records.length>maxCandidates)break;
    }
    // Inspect only explicit fragment/aria panel relationships. Never accept a bare navigation link as selection.
    const refs=nodes.map((e,i)=>{
      if(records[i].kind!=='CONTROL')return null;
      const raw=e.getAttribute('aria-controls')||e.getAttribute('data-target')||e.getAttribute('data-bs-target')||e.getAttribute('href')||'';
      const name=raw.startsWith('#')?raw.slice(1):e.hasAttribute('aria-controls')?raw:'';
      if(!/^[a-zA-Z][\w-]{0,79}$/.test(name))return null;
      const matches=doc.querySelectorAll('[id="'+name+'"]');
      const panel=matches.length===1?matches[0]:null;
      return panel?.matches('[role="tabpanel"],[data-board-view],[data-load-board-view]')?panel:null;
    });
    for(let i=0;i<records.length;i++){
      const p=refs[i];if(!p)continue;
      for(const attr of ['data-board-view','data-load-board-view']){
        const raw=p.getAttribute(attr);
        if(raw!==null&&raw.trim()){
          const label=labelFor(raw),panelView=label?labels[label]:'OTHER';
          if(panelView!==records[i].view)records[i].conflicting_identity=true;
        }
      }
      records[i].visible_linked_panel=visible(p);
      records[i].unique_linked_panel=refs.filter(r=>r===p).length===1;
      panels.push(p);
    }
    groups.push(...relevantGroups);
    const overflow=records.length>maxCandidates,result=classify(records,overflow);
    const diagnostic={contract:'AscendLoadBoardViewContract',version:1,provider:'AscendTMS',source:'provider DOM',
      candidate_control_count:records.filter(r=>r.kind==='CONTROL').length,candidate_count:records.length,
      candidate_bound_exceeded:overflow,candidates:records,...result};
    return {diagnostic,nodes,panels,groups};
  }
  function watch(doc,record){
    const initial=observe(doc);record(initial.diagnostic);
    const key=JSON.stringify(initial.diagnostic);let changed=false;
    function changedRecords(records){
      for(const r of records){
        const own=initial.nodes.includes(r.target),parent=initial.nodes.some(n=>n.parentElement===r.target&&r.target.matches?.('li,[role="presentation"]'));
        if(r.type==='attributes'){
          if(!own&&!parent&&!initial.panels.includes(r.target))continue;
          if(r.attributeName==='class'&&!initial.panels.includes(r.target)){
            const old=classes.filter(c=>(r.oldValue||'').split(/\s+/).includes(c));
            if(JSON.stringify(old)!==JSON.stringify(stateClasses(r.target)))changed=true;
          }else if(r.oldValue!==r.target.getAttribute(r.attributeName))changed=true;
        }else if(initial.nodes.some(n=>n===r.target||n.contains(r.target))||initial.groups.some(g=>g.contains(r.target))||
          [...r.removedNodes||[]].some(n=>initial.nodes.some(e=>n===e||n.contains?.(e))))changed=true;
        else for(const n of r.addedNodes||[]){
          if(n.nodeType!==1||excluded(n))continue;
          for(const e of [n,...n.querySelectorAll(controlSelector+',h1,h2,[role="heading"],[data-board-view],[data-load-board-view]')])
            if(!excluded(e)&&(e.hasAttribute('data-board-view')||e.hasAttribute('data-load-board-view')||
              e.matches(controlSelector+',h1,h2,[role="heading"]')&&labelFor(e.textContent)))changed=true;
        }
      }
    }
    const observer=new MutationObserver(changedRecords);
    const attrs=['class','hidden','aria-hidden','aria-selected','aria-current','aria-pressed','aria-controls',
      'href','aria-label','data-target','data-bs-target','data-view','data-board-view','data-load-board-view'];
    // Provider view nodes/groups only. No document-tree or operational-cell observer.
    for(const e of new Set([...initial.nodes,...initial.groups])){
      const container=initial.diagnostic.candidates[initial.nodes.indexOf(e)]?.kind==='CONTAINER';
      observer.observe(e,container?{attributes:true,attributeOldValue:true,attributeFilter:attrs}:
        {attributes:true,attributeOldValue:true,attributeFilter:attrs,childList:true,characterData:true,subtree:true});
      if(e.parentElement)observer.observe(e.parentElement,{childList:true,attributes:true,attributeOldValue:true,attributeFilter:attrs});
    }
    for(const p of new Set(initial.panels))observer.observe(p,{attributes:true,attributeOldValue:true,attributeFilter:attrs});
    function check(){
      const current=observe(doc).diagnostic;record(current);
      changedRecords(observer.takeRecords());
      if(changed||JSON.stringify(current)!==key)throw Error('ACTIVE_VIEW_CHANGED');
      if(current.confidence!=='VERIFIED')throw Error('ACTIVE_VIEW_UNVERIFIED');
      if(current.view!=='ACTIVE_LOADS')throw Error('ACTIVE_VIEW_NOT_ACTIVE_LOADS');
      return current;
    }
    return {check,close:()=>observer.disconnect()};
  }
  globalThis.FreightDeskLoadBoardView=Object.freeze({observe,watch,classify});
})();
