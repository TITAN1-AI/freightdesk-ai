({state, approved, opener, target, mode}) => {
    const bound=(category,measured,maximum)=>{if(measured>maximum) throw {bound:{category,measured,maximum}};};
    try {
    // Observer-owned handles only: no page globals, DOM edits, event execution or network inspection.
    const visible=e=>!!e?.getClientRects().length && getComputedStyle(e).visibility!=='hidden';
    const norm=s=>(s||'').trim().toLowerCase().replace(/\s+/g,' ');
    const key=e=>{if(!state.nodes.has(e)) state.nodes.set(e,++state.next);return state.nodes.get(e);};
    const pos=e=>{
        const p=[];
        while(e?.nodeType===1){p.unshift(e.tagName.toLowerCase()+':nth-child('+([...e.parentElement?.children||[]].indexOf(e)+1||1)+')');e=e.parentElement;}
        return p.join(' > ');
    };
    const vocabulary=new Set(['data','load','loads','id','number','no','booking','detail','details','modal','dialog',
        'panel','side','target','bs','toggle','view','open','selected','active','row','form','tab','content','container']);
    const safeName=s=>s && s.length<=64 && s.split(/[-_]/).every(x=>vocabulary.has(x.toLowerCase())||approved.includes(x))?s:'[redacted]';
    const loadKey=s=>/^(?:data[-_])?(?:booking[-_]?)?load[-_]?(?:id|number|no)$/i.test(s||'');
    const path=raw=>{
        try {
            const u=new URL(raw,location.href);
            if(u.origin!==location.origin||u.username||u.password) return null;
            return u.pathname.split('/').filter(Boolean).every(x=>['loads','load','detail','details','view'].includes(x)||approved.includes(x))?u.pathname:'[redacted path]';
        } catch {return null;}
    };
    const identity=(value,category,e)=>({category,node:key(e),selector:pos(e),
        value:approved.includes((value||'').trim())?value.trim():null,
        unapproved_value:!!(value||'').trim()&&!approved.includes(value.trim())});
    const attrs=e=>{
        bound(e===opener?'opener_attributes':'container_attributes',e.attributes.length,32);
        bound('class_tokens',e.classList.length,20);
        return ({id_present:e.hasAttribute('id'),name_present:e.hasAttribute('name'),
        id:e.id?safeName(e.id):null,name:e.getAttribute('name')?safeName(e.getAttribute('name')):null,
        classes:[...e.classList].slice(0,20).map(safeName),class_count:e.classList.length,
        data_attributes:[...e.attributes].filter(a=>a.name.startsWith('data-')).slice(0,30).map(a=>({
            name:safeName(a.name),approved_value:approved.includes(a.value.trim())?a.value.trim():null})),
        aria_label_present:e.hasAttribute('aria-label'),aria_labelledby_present:e.hasAttribute('aria-labelledby')});};
    const ownSignals=e=>{
        const result=[];
        bound(e===opener?'opener_attributes':'identity_element_attributes',e.attributes.length,32);
        for(const a of [...e.attributes]) {
            if(loadKey(a.name)) result.push(identity(a.value,'load_attribute',e));
            if(['id','name'].includes(a.name)) {
                const m=a.value.match(/^(?:booking[-_]?)?load[-_]?(?:detail[-_]?)?(?:id[-_]?)?(\d{1,20})$/i);
                if(m) result.push(identity(m[1],'load_element_identifier',e));
            }
        }
        return result;
    };
    const eventMeta=e=>{
        const raw=e.getAttribute('onclick')||'';
        // Only a full, single, explicitly read-named call with one literal integer. Never execute it.
        const m=raw.match(/^\s*(?:return\s+)?(?:openLoad|viewLoad|showLoadDetails|openLoadDetails)\(\s*(['"]?)(\d{1,20})\1\s*\)\s*;?\s*$/);
        return {onclick_present:!!raw,safe_single_load_call:!!m,
            signal:m?identity(m[2],'read_named_event_argument',e):null};
    };
    const row=opener?.closest('tr,[role="row"]');
    const targetRow=target?.closest('tr,[role="row"]');
    const table=row?.closest('table,[role="grid"],[role="table"]');
    const headers=table?[...table.querySelectorAll('thead th,[role="columnheader"]')]:[];
    bound('row_headers',headers.length,64);
    const idColumns=headers.map((e,i)=>['load id','load #','load number'].includes(norm(e.textContent))?i:-1).filter(i=>i>=0);
    const cells=row?[...row.children].filter(e=>e.matches('td,[role="cell"],[role="gridcell"]')):[];
    const identityCell=idColumns.length===1?cells[idColumns[0]]:null;
    const rowBound=!!row && row===targetRow && row.contains(opener) && identityCell?.contains(target) &&
        norm(identityCell.textContent)==='1755' && norm(target.textContent)==='1755';
    const selected=e=>!!e&&(e.getAttribute('aria-selected')==='true'||e.getAttribute('aria-expanded')==='true'||e.classList.contains('selected'));
    let control=null;
    if(opener){
        const href=(opener.getAttribute('href')||'').trim();
        const scheme=!href?'empty':href.startsWith('#')?'hash':/^javascript:/i.test(href)?'javascript':path(href)!==null?'normal_same_origin':'other';
        const event=eventMeta(opener);
        control={node:key(opener),selector:pos(opener),tag:opener.tagName.toLowerCase(),href_type:scheme,
            href_path:scheme==='normal_same_origin'?path(href):null,attributes:attrs(opener),event,
            identity_signals:ownSignals(opener).concat(event.signal?[event.signal]:[]),
            exact_row_bound:!!rowBound,row_load_id:rowBound?'1755':null,load_id_column:idColumns.length===1?idColumns[0]:null,
            row_node:row?key(row):null,row_selected:selected(row),control_selected:selected(opener),
            row_identity_signals:row?ownSignals(row):[]};
    }
    if(mode==='opener') return {overflow:false,control,containers:[]};
    const direct=[];
    for(const source of [opener,row].filter(Boolean)){
        for(const a of ['aria-controls','aria-owns','href','data-target','data-bs-target']){
            const raw=source.getAttribute(a)||'';
            const ids=['aria-controls','aria-owns'].includes(a)?raw.split(/\s+/).filter(Boolean):/^#[\w-]+$/.test(raw)?[raw.slice(1)]:[];
            bound('opener_references',ids.length,8);
            for(const id of ids){const n=document.getElementById(id);if(n&&!direct.includes(n)) direct.push(n);}
        }
    }
    bound('opener_references',direct.length,8);
    // Specific container selectors only. No [id], universal selector, tree walker or descendant enumeration.
    const likely='[role="dialog"],dialog,.modal,.side-panel,.offcanvas,[role="tabpanel"],form,h1,h2,h3,[role="heading"],section.load-detail,section.load-details,[data-load-detail]';
    const visibleCandidates=[];
    for(const e of document.querySelectorAll(likely)){
        if(mode==='before') state.known.add(e);
        if(visible(e)&&!e.closest('table,[role="grid"],[role="table"]')) visibleCandidates.push(e);
    }
    bound('visible_candidate_containers',visibleCandidates.length,24);
    const candidates=[...new Set([...visibleCandidates,...direct,...(mode==='after'?[...state.baseline.keys()]:[])])];
    bound('candidate_containers',candidates.length,32);
    const containers=[];
    for(const e of candidates){
        if(!e.isConnected) continue;
        const previous=state.baseline.get(e);
        const detail=!e.matches('h1,h2,h3,[role="heading"],[role="tab"]');
        const narrowed=mode==='after'&&visible(e)&&(direct.includes(e)||!previous||!previous.visible);
        const signals=[],labels=[],types={};
        let nodes=[];
        if(narrowed){
            nodes=[e,...e.querySelectorAll('label,dt,input[readonly],input[type="hidden"][name],input[name*="load" i],input[id*="load" i],input[aria-label*="load" i],select[aria-label*="load" i],[data-load-id],[data-booking-load-id],h1,h2,h3,[role="heading"],[aria-label*="load" i]')];
            bound('identity_candidates',nodes.length,64);
        }
        for(const n of nodes){
            signals.push(...ownSignals(n));
            const rawLabel=n.getAttribute('aria-label') || n.labels?.[0]?.textContent || (n.matches('label,dt')?n.textContent:'');
            const label=norm(rawLabel).replace(/:$/,'');
            const approvedLabel=['load','load id','load #','load number','booking load id'].includes(label);
            if(/\bload\b/i.test(label)) labels.push({node:key(n),label:approvedLabel?label:'[load-related label]',tag:n.tagName.toLowerCase(),readonly:n.hasAttribute('readonly'),hidden:n.getAttribute('type')==='hidden'});
            if(approvedLabel){
                const valueNode=n.control||n;
                if(valueNode.matches('input,select')&&valueNode.type!=='password') signals.push(identity(valueNode.value,'detail_load_field',valueNode));
                else if(n.matches('dt,label')&&!n.control&&n.nextElementSibling) signals.push(identity(n.nextElementSibling.textContent,'detail_load_field',n));
            } else if(n.matches('input')&&n.type!=='password'&&(loadKey(n.name)||loadKey(n.id))) signals.push(identity(n.value,'named_load_input',n));
            if(n.matches('h1,h2,h3,[role="heading"]')||n.hasAttribute('aria-label')){
                const text=n.getAttribute('aria-label')||(n.matches('h1,h2,h3,[role="heading"]')?n.textContent:'');
                const m=text.trim().match(/^(?:booking\s+)?load\s*(?:id|number|#)?\s*[:#-]?\s*(\d{1,20})$/i);
                if(m) signals.push(identity(m[1],'load_heading_or_aria',n));
            }
        }
        const links=[];
        const bind=(source,attribute,targetId,reverse=false)=>{
            const destination=document.getElementById(targetId);
            if(!source||!destination) return;
            if((!reverse&&(destination===e||e.contains(destination))) || (reverse&&(destination===opener||destination===row)))
                links.push({attribute,source:key(source),destination:key(destination),container:key(e)});
        };
        for(const source of [opener,row].filter(Boolean)){
            for(const a of ['aria-controls','aria-owns']) for(const value of (source.getAttribute(a)||'').split(/\s+/).filter(Boolean)) bind(source,a,value);
            for(const a of ['data-target','data-bs-target','href']){
                const v=source.getAttribute(a)||'';
                if(/^#[\w-]+$/.test(v)) bind(source,a,v.slice(1));
            }
        }
        for(const value of (e.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean)) bind(e,'aria-labelledby',value,true);
        const ancestors=[];for(let p=e.parentElement;p;p=p.parentElement) if(candidates.includes(p)) ancestors.push(key(p));
        const fingerprint={visible:visible(e),child_count:e.children.length,attributes:attrs(e),bindings:links};
        containers.push({fingerprint,previously_existed:state.known.has(e),identity_inspected:narrowed,node:key(e),selector:pos(e),detail,surface:detail&&e.tagName!=='FORM',visible:visible(e),ancestors,
            tag:e.tagName.toLowerCase(),attributes:attrs(e),child_count:e.children.length,
            control_types:types,labels:labels.slice(0,100),identity_signals:signals,bindings:links,
            action_path:e.tagName==='FORM'?path(e.getAttribute('action')||''):null});
    }
    if(mode==='before') state.baseline=new Map(candidates.filter(e=>e.isConnected).map(e=>[e,{visible:visible(e)}]));
    return {overflow:false,control,containers};
    } catch(error) {if(error.bound) return {overflow:true,bound:error.bound};throw error;}
}
