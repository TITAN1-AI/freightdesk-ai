arg => {
    const norm=s=>(s||'').replace(/\s+/g,' ').trim().toLowerCase();
    const visible=e=>!!e.getClientRects().length && getComputedStyle(e).visibility!=='hidden';
    const candidates=[...document.querySelectorAll('table,[role="grid"],[role="table"]')];
    if(candidates.length>30) return {overflow:true,grids:[]};
    const grids=[];
    for(const t of candidates) {
        if(!visible(t)) continue;
        const own=s=>[...t.querySelectorAll(s)].filter(e=>e.closest('table,[role="grid"],[role="table"]')===t);
        const hs=own('thead th,[role="columnheader"]');
        const rows=own('tbody tr,[role="row"]').filter(r=>visible(r));
        const cells=r=>[...r.querySelectorAll('td,[role="cell"],[role="gridcell"]')].filter(c=>c.closest('tr,[role="row"]')===r);
        const data=rows.filter(r=>cells(r).length);
        if(!data.length) continue; // Fixed/header clones never compete with data grids.
        if(data.length>500) return {overflow:true,grids:[]};
        if(hs.length!==arg.headers.length || !data.every(r=>cells(r).length===hs.length)) continue;
        const label=h=>{
            let text='',node; const walker=document.createTreeWalker(h,NodeFilter.SHOW_TEXT);
            while((node=walker.nextNode())) if(!node.parentElement.closest('select,option,input,textarea,script,style')) text+=node.textContent;
            return norm(text);
        };
        if(hs.some((h,i)=>arg.headers[i]!==null && label(h)!==norm(arg.headers[i]))) continue;
        if([...hs,...data.flatMap(cells)].some(c=>Number(c.getAttribute('colspan')||1)!==1 ||
            Number(c.getAttribute('rowspan')||1)!==1)) continue;
        if(hs.some((h,i)=>h.hasAttribute('aria-colindex') && Number(h.getAttribute('aria-colindex'))!==i+1)) continue;
        const extracted=[];
        // Date columns only are examined on unmatched rows. No finance/notes/phone fields are read.
        const dateText=c=>(c.textContent||'').trim();
        let unknown_dates=0;
        for(const row of data) {
            const cs=cells(row); const pick=dateText(cs[5]),drop=dateText(cs[7]);
            const prefix=s=>{
                const m=s.match(arg.format==='US'?/^(\d{2}\/\d{2}\/\d{4})(?=$|\s)/:/^(\d{4}-\d{2}-\d{2})(?=$|[ T])/);
                return m?m[1]:null;
            };
            const pd=prefix(pick),dd=prefix(drop);
            unknown_dates+=Number(pd===null || dd===null);
            if(pd!==arg.display_date && dd!==arg.display_date) continue;
            const out={};
            for(const [field,index] of Object.entries(arg.fields)) {
                // Exclude tooltips, hidden contact details and descendants representing private notes.
                const copy=cs[index].cloneNode(true);
                copy.querySelectorAll('script,style,input,textarea,[hidden],.tooltip,.popover').forEach(e=>e.remove());
                out[field]=(copy.textContent||'').trim();
                if(out[field].length>1000) return {overflow:true,grids:[]};
            }
            extracted.push(out);
        }
        const wrapper=t.closest('.dataTables_wrapper,.dt-container');
        const pagination={next_disabled:null,previous_disabled:null,start:null,end:null,total:null,page_size:null};
        if(wrapper) {
            const disabled=selector=>{
                const es=[...wrapper.querySelectorAll(selector)];
                if(es.length!==1) return null;
                const e=es[0];
                return e.matches(':disabled,[aria-disabled="true"],.disabled') || e.parentElement?.matches('.disabled') || false;
            };
            pagination.next_disabled=disabled('.dataTables_paginate .next,.dt-paging .next');
            pagination.previous_disabled=disabled('.dataTables_paginate .previous,.dt-paging .previous');
            const sizes=wrapper.querySelectorAll('.dataTables_length select,.dt-length select');
            if(sizes.length===1 && /^\d{1,4}$/.test(sizes[0].value)) pagination.page_size=Number(sizes[0].value);
            const infos=wrapper.querySelectorAll('.dataTables_info,.dt-info');
            if(infos.length===1) {
                const m=infos[0].textContent.trim().match(/^Showing ([\d,]+) to ([\d,]+) of ([\d,]+) entries(?: \(filtered from [\d,]+ total entries\))?$/i);
                if(m) [pagination.start,pagination.end,pagination.total]=m.slice(1).map(s=>Number(s.replaceAll(',','')));
            }
        }
        grids.push({rows:extracted,visible_rows:data.length,header_count:hs.length,pagination,unknown_dates,table_index:candidates.indexOf(t)});
    }
    return {overflow:false,grids};
}
