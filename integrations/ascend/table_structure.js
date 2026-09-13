arg => {
    // Fixed DOM-only collector. Never return general row text, URLs or control values.
    const visible = e => !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
    const norm = s => s.replace(/\s+/g, ' ').trim().toLowerCase();
    const schema = s => {
        // Schema-only strings; unsafe/dynamic labels stay presence-only.
        if (!s || s.length > 100 || /[@\d]/.test(s.trim()) || !/^[a-zA-Z\s#()./&:_-]+$/.test(s)) return null;
        return s;
    };
    const selector = e => {
        const parts = [];
        while (e && e.nodeType === 1) {
            const n = [...e.parentElement?.children || []].indexOf(e) + 1;
            parts.unshift(e.tagName.toLowerCase() + (n ? `:nth-child(${n})` : ''));
            e = e.parentElement;
        }
        return parts.join(' > ');
    };
    const candidates = [...document.querySelectorAll('table,[role="grid"],[role="table"],[role="treegrid"]')];
    if (candidates.length > 30) return {overflow:true, tables:[]};
    const tables = candidates.map((t, index) => {
        const own = s => [...t.querySelectorAll(s)].filter(e => e.closest('table,[role="grid"],[role="table"],[role="treegrid"]') === t);
        const rows = own('tr,[role="row"]');
        const cells = r => [...r.querySelectorAll('td,[role="cell"],[role="gridcell"]')].filter(e=>e.closest('tr,[role="row"]')===r);
        const data = rows.filter(r=>cells(r).length);
        if (rows.length > 500 || own('th,td,[role="columnheader"],[role="cell"],[role="gridcell"]').length > 25000) return {overflow:true,index};
        const headers = [];
        const hs = own('thead th,th,[role="columnheader"]');
        const add = (e, col, source, raw) => {
            const label = schema(raw);
            headers.push({column_index:col,source,label, label_present:!!raw,selector:selector(e),
                visible:visible(e),aria_colindex:/^\d+$/.test(e.getAttribute('aria-colindex')||'')?Number(e.getAttribute('aria-colindex')):null,
                span_ambiguous:Number(e.getAttribute('colspan')||1)!==1 || Number(e.getAttribute('rowspan')||1)!==1});
        };
        hs.forEach(h=>{
            const peers=[...h.parentElement.children];
            const col=peers.indexOf(h);
            const walker=document.createTreeWalker(h,NodeFilter.SHOW_TEXT);
            let raw='',node;
            while((node=walker.nextNode())) if(!node.parentElement.closest('select,option,input,textarea,script,style')) raw+=node.textContent;
            add(h,col,'header_text',raw);
            for(const a of ['aria-label','data-title','title']) if(h.hasAttribute(a)) add(h,col,a,h.getAttribute(a));
        });
        // Cell metadata may contain values. Accept only recognized field labels or labels seen in a header.
        const known = new Set(['load #','load number','load no.','pickup date','delivery date','status',
            'pickup','delivery','customer','carrier','driver','equipment','power unit','trailer']);
        headers.filter(h=>h.label).forEach(h=>known.add(norm(h.label)));
        for(const r of data) cells(r).forEach((c,col)=>{
            for(const a of ['data-title','data-label','aria-label','title']) {
                const raw=c.getAttribute(a);
                if(raw && known.has(norm(raw)) && !headers.some(h=>h.column_index===col && h.source===a && h.label===raw)) add(c,col,a,raw);
            }
            for(const label of c.querySelectorAll('.dtr-title,[class~="responsive-label"]')) {
                const raw=label.textContent;
                if(schema(raw) && known.has(norm(raw))) add(label,col,'responsive_label',raw);
            }
        });
        const uniform=data.length>0 && data.every(r=>cells(r).length===cells(data[0]).length && cells(r).every(c=>
            Number(c.getAttribute('colspan')||1)===1 && Number(c.getAttribute('rowspan')||1)===1));
        const loadColumns=[...new Set(headers.filter(h=>h.label && ['load #','load number','load no.'].includes(norm(h.label)) && !h.span_ambiguous).map(h=>h.column_index))];
        const loadSafe=uniform && !headers.some(h=>h.span_ambiguous) && loadColumns.length===1 && headers.filter(h=>h.column_index===loadColumns[0]).every(h=>
            !h.span_ambiguous && h.label && ['load #','load number','load no.'].includes(norm(h.label)) &&
            (h.aria_colindex===null || h.aria_colindex===loadColumns[0]+1));
        const matches=[];
        data.forEach((r,row_index)=>{
            const cs=cells(r); const columns=[];
            cs.forEach((c,i)=>{
                const text=c.textContent || '';
                const re=/(^|[^\d])09\/11\/2026(?=$|[^\d])/g;
                const count=[...text.matchAll(re)].length;
                if(count) columns.push({column_index:i,occurrence_count:count,
                    header_labels:[...new Set(headers.filter(h=>h.column_index===i && h.label).map(h=>h.label))]});
            });
            if(columns.length) {
                const raw=loadSafe ? cs[loadColumns[0]]?.textContent.trim() : null;
                matches.push({row_index,visible:visible(r),load_number:raw && /^\d{1,20}$/.test(raw)?raw:null,
                    columns,multiple_date_columns:columns.length>1});
            }
        });
        const wrapper=t.closest('.dataTables_wrapper,.dt-container') || t.parentElement;
        const pagination=[...wrapper.querySelectorAll('.dataTables_paginate,.dt-paging,[role="navigation"][aria-label*="agin"]')];
        const sizes=[...wrapper.querySelectorAll('.dataTables_length select,.dt-length select')];
        const size=sizes.length===1 && /^\d{1,4}$/.test(sizes[0].value)?Number(sizes[0].value):null;
        let scroll=false; for(let e=t;e && e!==document.body;e=e.parentElement) scroll ||= e.scrollWidth>e.clientWidth+1;
        const headerRows=own('thead tr').map(r=>norm(r.textContent));
        return {index,selector:selector(t),element_type:t.tagName.toLowerCase(),role:t.getAttribute('role'),visible:visible(t),
            visible_row_count:data.filter(visible).length,dom_row_count:rows.length,data_row_count:data.length,
            header_cell_count:hs.length,first_data_row_cell_count:data.length?cells(data[0]).length:0,uniform_cell_count:uniform,
            horizontal_scrolling:scroll,hidden_columns:own('th,td,[role="columnheader"],[role="cell"],[role="gridcell"]').some(e=>!visible(e)),
            duplicated_headers: new Set(headerRows).size<headerRows.length,
            thead_exists:!!t.querySelector('thead'),aria_column_labels:own('[aria-label]').length>0,
            aria_column_indexes:own('[aria-colindex]').length>0,cell_field_labels:data.some(r=>cells(r).some(c=>['data-title','data-label','aria-label','title'].some(a=>c.hasAttribute(a)))),
            pagination_present:pagination.length>0,pagination_selectors:pagination.map(selector),page_size:size,
            body_selectors:own('tbody,[role="rowgroup"]').map(selector),headers,date_matches:matches};
    });
    // Detached/fixed cloned tables stay separate: never transfer their indexes to another body.
    for(const t of tables) if(t.headers) t.cloned_header_candidate=tables.some(o=>o!==t && o.headers &&
        JSON.stringify(o.headers.map(h=>h.label))===JSON.stringify(t.headers.map(h=>h.label)) && t.headers.length>0);
    return {overflow:tables.some(t=>t.overflow),tables};
}
