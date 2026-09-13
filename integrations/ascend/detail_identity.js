approved => {
    const visible=e=>!!e.getClientRects().length && getComputedStyle(e).visibility!=='hidden';
    const norm=s=>(s||'').replace(/\s+/g,' ').trim().toLowerCase();
    const labels=new Set(['load id','load #','load number','load no.','booking load id']);
    const names=new Set(['load_id','loadid','booking_load_id','bookingloadid']);
    const selector=e=>{
        const path=[];
        while(e && e.nodeType===1){path.unshift(e.tagName.toLowerCase()+':nth-child('+([...e.parentElement?.children||[]].indexOf(e)+1 || 1)+')');e=e.parentElement;}
        return path.join(' > ');
    };
    const nodes=[...document.querySelectorAll('input,select,dt,label,legend,.control-label,h1,h2,h3,[role="heading"],[role="tab"],[role="dialog"],nav[aria-label="breadcrumb"] a,[data-load-id],[data-booking-load-id]')];
    if(nodes.length>500) return {overflow:true,signals:[]};
    const signals=[];
    const add=(e,kind,label,raw)=>{
        const value=(raw||'').trim();
        if(!value) return;
        signals.push({kind,label,element_type:e.tagName.toLowerCase(),visible:visible(e),
            candidate_value:approved.includes(value)?value:null,unapproved_value:!approved.includes(value),
            selector:selector(e),id_present:e.hasAttribute('id'),name_present:e.hasAttribute('name')});
    };
    for(const e of nodes){
        if(e.closest('table,[role="grid"],[role="table"]')) continue; // A retained board is not detail proof.
        const label=norm(e.getAttribute('aria-label') || e.labels?.[0]?.textContent ||
            (['DT','LABEL','LEGEND'].includes(e.tagName) || e.classList.contains('control-label')?e.textContent:''));
        if(e.tagName==='LABEL' && e.control) continue; // Its input is collected once, not duplicated.
        if(labels.has(label) && visible(e)){
            const raw='value' in e?e.value:e.nextElementSibling?.textContent;
            add(e,'visible_field',label,raw);
        } else if(e.tagName==='INPUT' && names.has(norm(e.getAttribute('name')||e.id))) {
            add(e,'named_input','load identity input',e.value);
        }
        if(visible(e) && (['H1','H2','H3'].includes(e.tagName) || ['heading','tab','dialog'].includes(e.getAttribute('role')) || e.closest('nav[aria-label="breadcrumb"]'))) {
            const text=e.getAttribute('role')==='dialog'?e.getAttribute('aria-label'):e.textContent;
            const match=(text||'').trim().match(/^(?:booking\s+)?load\s*(?:id|number|#|no\.?)?\s*[:#-]?\s*(\d{1,20})$/i);
            if(match) add(e,'heading','load heading',match[1]);
        }
        for(const a of ['data-booking-load-id','data-load-id']) if(e.hasAttribute(a)) add(e,'data_attribute',a,e.getAttribute(a));
    }
    return {overflow:false,signals};
}
