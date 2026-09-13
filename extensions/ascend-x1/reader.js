(() => {
  'use strict';
  const C=globalThis.FreightDeskX1Contract;
  const visible=e=>!!e?.getClientRects().length&&getComputedStyle(e).visibility!=='hidden'&&!e.closest('[hidden],[aria-hidden="true"]');
  const norm=s=>(s||'').replace(/\s+/g,' ').trim();
  const id=s=>/^[0-9]{1,20}$/.test(s)?s:null;
  const domPath=e=>{const parts=[];for(let n=e;n?.nodeType===1;n=n.parentElement)
    parts.unshift(n.tagName.toLowerCase()+':nth-child('+([...n.parentElement?.children||[]].indexOf(n)+1||1)+')');return parts.join(' > ');};
  const bounded=(n,max,code)=>{if(n>max)throw Error(code);};
  const nav=['Dashboard','Loads','Customers','Carriers','Locations','Reporting','Accounting','Settings'];
  const statuses=['Active','Available','Assigned','Booked','Dispatched','In Transit','Delivered','Completed'];
  const statusesSafe=s=>statuses.includes(s)?s:'UNKNOWN';
  const date=s=>s.match(/^\d{2}\/\d{2}\/\d{4}(?=$|\s)/)?.[0]||null;
  const headers=['Load ID','Load Status','Last Contact/Tracking','Customer','Picks','Pick Date','Drops','Drop Date',
    'Users & Roles','Carrier','Driver','Equipment','Power Unit','Trailer','Distance','Weight','Income','Expenses',
    'Gross Profit/Loss',null,'Reference','Truck Status','Branch',null,'Smart Capacity','TruckSmarter','Asset Group',
    'Container','Last Free Day','Created','Load Posting Notes','Public Load Notes','Temperature'];
  const hex=buffer=>[...new Uint8Array(buffer)].map(n=>n.toString(16).padStart(2,'0')).join('');
  async function create(doc,origin) {
    if(origin!==C.origin||doc.location.origin!==C.origin)throw Error('origin_denied');
    let selected=null,foundContext=null,lastView=null,verifiedDetail=null,lastSchema=null,verifiedContainerDiagnostic=null,lastMappingSection=null;
    function session(runtime=false){
      if(doc.location.origin!==C.origin)throw Error('origin_denied');
      const path=['/','/loads','/login.html'].includes(doc.location.pathname)?doc.location.pathname:'UNKNOWN';
      const controls=[...doc.querySelectorAll('a,button,[role="link"]')];
      const markers=nav.filter(n=>controls.some(e=>norm(e.textContent)===n&&visible(e)));
      const login=[...doc.querySelectorAll('input[type="password"],form[action*="login"]')].some(visible);
      return {session_authenticated:(runtime?path!=='/login.html':['/','/loads'].includes(path))&&!login&&markers.includes('Dashboard')&&markers.includes('Loads')&&markers.length>=4,
        path,login_form_present:login,nav_markers:markers,tenant_identity_source:'OWNER_ATTESTED'};
    }
    function guard(runtime=false){if(!session(runtime).session_authenticated)throw Error('session_unverified');}
    function grid(identityOnly=false,allowEmpty=false){
      guard();
      lastView=FreightDeskLoadBoardView.observe(doc).diagnostic;
      if(lastView.confidence!=='VERIFIED')throw Error('ACTIVE_VIEW_UNVERIFIED');
      if(lastView.view!=='ACTIVE_LOADS')throw Error('ACTIVE_VIEW_NOT_ACTIVE_LOADS');
      const known=headers.filter(Boolean),key=s=>norm(s).toLowerCase(),critical=['Load ID','Pick Date','Drop Date'];
      const tables=[...doc.querySelectorAll('table,[role="grid"]')];
      const candidates=[],eligible=[],empty=[];
      lastSchema={version:1,candidate_grid_count:tables.length,candidates:[],failed_predicate:null,selected_candidate:null,render_samples:1,pagination:{page_size:null,next_disabled:null,previous_disabled:null}};
      const fail=predicate=>{lastSchema.failed_predicate=predicate;throw Error('BOARD_SCHEMA_INVALID');};
      for(const [candidate_index,table] of tables.slice(0,30).entries()){
        const hs=[...table.querySelectorAll('thead th,[role="columnheader"]')].filter(h=>h.closest('table,[role="grid"]')===table);
        const names=hs.map(h=>known.find(n=>key(n)===key(h.textContent))||(norm(h.textContent)?'UNKNOWN_LABEL':'EMPTY_LABEL'));
        const positions=Object.fromEntries(known.map(n=>[n,names.flatMap((v,i)=>v===n?[i]:[])]));
        const indexes=Object.fromEntries(known.map(n=>[n,positions[n].length===1?positions[n][0]:null]));
        const rows=[...table.querySelectorAll('tbody > tr,[role="row"]')].filter(r=>visible(r)&&r.closest('table,[role="grid"]')===table);
        const data=rows.map(row=>({row,cells:[...row.children].filter(e=>e.matches('td,[role="cell"],[role="gridcell"]')),indexes})).filter(r=>r.cells.length);
        const emptyMarker=data.length===1&&data[0].cells.length===1&&data[0].cells[0].classList.contains('dataTables_empty')&&
          ['No data available in table','No matching records found'].includes(norm(data[0].cells[0].textContent));
        const wrapper=table.closest('.dataTables_wrapper');
        const busy=table.getAttribute('aria-busy')==='true'||!!wrapper&&[...wrapper.querySelectorAll('.dataTables_processing')].some(visible);
        const ariaMismatch=hs.some((h,i)=>h.hasAttribute('aria-colindex')&&h.getAttribute('aria-colindex')!==String(i+1))||
          data.slice(0,101).some(r=>r.cells.some((c,i)=>c.hasAttribute('aria-colindex')&&c.getAttribute('aria-colindex')!==String(i+1)));
        const summary={candidate_index,visible:visible(table),data_bearing:data.length>0&&!emptyMarker,has_body:!!table.querySelector('tbody,[role="rowgroup"]'),
          header_count:hs.length,header_labels:names.slice(0,64),header_visible:hs.slice(0,64).map(visible),
          row_count:data.length,row_visible_cell_counts:[...new Set(data.slice(0,101).map(r=>r.cells.filter(visible).length))].slice(0,64),row_cell_counts:[...new Set(data.slice(0,101).map(r=>r.cells.length))].slice(0,64),
          required_header_mapping:indexes,missing_headers:known.filter(n=>positions[n].length===0),duplicate_headers:known.filter(n=>positions[n].length>1),
          header_spans:hs.some(h=>h.colSpan>1||h.rowSpan>1||Number(h.getAttribute('aria-colspan'))>1||Number(h.getAttribute('aria-rowspan'))>1),row_spans:!emptyMarker&&data.slice(0,101).some(r=>r.cells.some(c=>c.colSpan>1||c.rowSpan>1||Number(c.getAttribute('aria-colspan'))>1||Number(c.getAttribute('aria-rowspan'))>1)),
          aria_column_mismatch:ariaMismatch,initialization_busy:busy,empty_marker:emptyMarker};
        candidates.push(summary);lastSchema.candidates=candidates;
        const relevant=critical.every(n=>positions[n].length>0);
        if(!summary.visible||!relevant)continue;
        const item={summary,data:emptyMarker?[]:data,indexes,table};
        if(summary.data_bearing)eligible.push(item);else if(summary.has_body)empty.push(item);
      }
      if(tables.length>30)fail('CANDIDATE_GRID_BOUND');
      // Header-only/fixed clones never compete with an actual data-bearing table.
      if(eligible.length>1)fail('AMBIGUOUS_DATA_GRIDS');
      const selectedGrid=eligible[0]||(!eligible.length&&empty.length===1?empty[0]:null);
      if(!selectedGrid)fail(candidates.some(c=>c.visible)?'REQUIRED_HEADERS_MISSING':'NO_VISIBLE_GRID');
      const m=selectedGrid.summary;lastSchema.selected_candidate=m.candidate_index;
      const wrapper=selectedGrid.table.closest('.dataTables_wrapper');
      if(wrapper){
        const sizes=[...wrapper.querySelectorAll('select[name$="_length"]')];
        if(sizes.length===1&&/^[0-9]{1,4}$/.test(sizes[0].value))lastSchema.pagination.page_size=Number(sizes[0].value);
        for(const [key,selector] of [['next_disabled','.paginate_button.next'],['previous_disabled','.paginate_button.previous']]){
          const controls=wrapper.querySelectorAll(selector);
          if(controls.length===1)lastSchema.pagination[key]=controls[0].classList.contains('disabled')||controls[0].getAttribute('aria-disabled')==='true';
        }
      }
      if(m.initialization_busy)fail('INITIALIZATION_BUSY');
      if(m.header_count!==33)fail('HEADER_COUNT_MISMATCH');
      if(m.duplicate_headers.length)fail('DUPLICATE_REQUIRED_HEADERS');
      if(m.missing_headers.length)fail('REQUIRED_HEADERS_MISSING');
      if(m.header_spans)fail('HEADER_SPAN');
      if(m.row_spans)fail('ROW_SPAN');
      if(m.aria_column_mismatch)fail('ARIA_COLUMN_ALIGNMENT');
      if(m.row_count>100)fail('ROW_COUNT_BOUND');
      if(m.data_bearing&&m.row_cell_counts.some(n=>n!==m.header_count))fail('ROW_CELL_COUNT_MISMATCH');
      if(!m.data_bearing&&(!allowEmpty||!m.empty_marker))fail('EMPTY_STATE_UNVERIFIED');
      const output=selectedGrid.data.map(({row,cells,indexes})=>{
        const number=id(norm(cells[indexes['Load ID']].textContent));if(!number)fail('ROW_IDENTITY_INVALID');
        // Identity controller never reads assignment, finance, notes or other operational cells.
        if(identityOnly)return {row,cells,indexes,facts:{drop_date:date(norm(cells[indexes['Drop Date']].textContent)),load_id:number,pick_date:date(norm(cells[indexes['Pick Date']].textContent))}};
        const present=i=>visible(cells[i])&&!!norm(cells[i].textContent);
        return {row,cells,indexes,facts:{load_id:number,load_status:statusesSafe(norm(cells[indexes['Load Status']].textContent)),
          pick_date:date(norm(cells[indexes['Pick Date']].textContent)),drop_date:date(norm(cells[indexes['Drop Date']].textContent)),
          carrier_presence:present(indexes['Carrier']),driver_presence:present(indexes['Driver']),power_unit_presence:present(indexes['Power Unit']),
          trailer_presence:present(indexes['Trailer']),truck_status:statusesSafe(norm(cells[indexes['Truck Status']].textContent))}};
      });
      if(new Set(output.map(r=>r.facts.load_id)).size!==output.length)fail('DUPLICATE_LOAD_ID');
      return output;
    }
    async function board(identityOnly=false,allowEmpty=false){
      const rows=grid(identityOnly,allowEmpty);
      const facts=rows.map(r=>r.facts).sort((a,b)=>Number(a.load_id)-Number(b.load_id));
      const revision=hex(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(facts))));
      return {rows,revision,facts};
    }
    const panels=()=>[...doc.querySelectorAll('[role="dialog"],dialog,.modal,.side-panel,[role="tabpanel"]')].filter(visible);
    function opener(row,number){
      const links=[...row.querySelectorAll('a,button,[role="button"],[role="link"]')].filter(e=>visible(e)&&[number,'View','Details','Open'].includes(norm(e.textContent)));
      if(links.length!==1)throw Error('opener_ambiguous');
      const e=links[0],href=e.getAttribute('href')||'';
      if(e.matches('[type="submit"],[type="reset"]')||(e.tagName==='BUTTON'&&e.closest('form')&&e.type!=='button'))throw Error('write_control_denied');
      if(href&&!href.startsWith('#')){
        const u=new URL(href,doc.location.href);
        if(u.origin!==C.origin||u.username||u.password||/save|submit|delete|create|assign|edit|update|send|upload|note/i.test(u.pathname+' '+u.search))throw Error('unsafe_opener');
      }
      return e;
    }
    function capture(row,number,control,revision,loadCell){
      if(!row.contains(control)||(!loadCell||!row.contains(loadCell)||norm(loadCell.textContent)!==number))throw Error('row_binding_invalid');
      const bridge=globalThis.FreightDeskWebBridge;
      const before=bridge?[]:panels();if(!bridge)bounded(before.length,12,'detail_containers_bound');
      selected={row,number,control,revision,loadCell,domSnapshot:bridge?.DOMSnapshot.capture(doc,{row,opener:control,loadId:number}),before:new Map(before.map(e=>[e,e.getAttribute('aria-hidden')||'visible'])),
        selectedBefore:row.getAttribute('aria-selected')==='true'||control.getAttribute('aria-expanded')==='true'};
    }
    function detail(number,identityOnly=false){
      if(!selected||selected.number!==number||!selected.row.isConnected||!selected.control.isConnected||(!selected.loadCell?.isConnected||norm(selected.loadCell.textContent)!==number))
        throw Error('row_context_missing');
      const {control,row,before}=selected;
      const refs=[];
      if(selected.domSnapshot){for(const r of selected.domSnapshot.refs){const element=doc.getElementById(r.id);if(element)refs.push({element,attribute:r.attribute});}}
      else for(const e of [control,row]) for(const name of ['aria-controls','data-target','data-bs-target','href']){
        const raw=e.getAttribute(name)||'';
        const value=name==='aria-controls'?raw:/^#[\w-]+$/.test(raw)?raw.slice(1):'';
        if(value&&doc.getElementById(value))refs.push({element:doc.getElementById(value),attribute:name});
      }
      const changes=selected.domSnapshot?FreightDeskWebBridge.DOMDiff.compare(selected.domSnapshot,doc,refs.map(r=>r.element)):null;
      const candidates=changes?null:panels().filter(p=>!before.has(p)||refs.some(r=>r.element===p));
      if(!changes){bounded(candidates.length,12,'detail_containers_bound');
        if(candidates.length!==1)throw Error(candidates.length?'detail_container_ambiguous':'detail_binding_missing');}
      const choice=changes?FreightDeskWebBridge.AdaptiveLocator.selectContainer(changes):null;
      const panel=choice?choice.element:candidates[0], signals=[];
      selected.detailPanel=panel;selected.containerReasons=changes?.find(c=>c.element===panel)?.reasons||[];
      const fields=[panel,...panel.querySelectorAll('label,input[name="load_id"],input[name="loadId"],[data-load-id],h1,h2,h3,[role="heading"]')];
      if(selected.domSnapshot)FreightDeskWebBridge.identityCandidates(selected.domSnapshot,fields.length);
      else bounded(fields.length,64,'identity_fields_bound');
      for(const e of fields){
        if(!visible(e))continue;
        if(e.hasAttribute('data-load-id'))signals.push(norm(e.getAttribute('data-load-id')));
        if(e.matches('input[name="load_id"],input[name="loadId"]'))signals.push(norm(e.value));
        if(e.matches('label')&&['Load ID','Load #','Load Number'].includes(norm(e.textContent))&&e.control)signals.push(norm(e.control.value));
        if(e.matches('h1,h2,h3,[role="heading"]')){const m=norm(e.textContent).match(/^Load\s*(?:ID|#|Number)?\s*:?\s*(\d+)$/);if(m)signals.push(m[1]);}
      }
      const openerId=control.getAttribute('data-load-id');
      if(signals.some(n=>n!==number)||(openerId!==null&&openerId!==number))throw Error('identity_conflict');
      const relation=refs.find(r=>r.element===panel);
      const nowSelected=row.getAttribute('aria-selected')==='true'||control.getAttribute('aria-expanded')==='true';
      const newlyVisible=selected.domSnapshot?!selected.domSnapshot.states.get(panel)?.visible:!before.has(panel);
      const strategy=signals.length?'PROVIDER_DETAIL_FIELD':newlyVisible&&relation&&openerId===number?'PROVIDER_OPENER_BINDING':
        newlyVisible&&relation&&nowSelected&&!selected.selectedBefore?'PROVIDER_SELECTED_ROW_BINDING':null;
      if(!strategy)throw Error('provider_binding_missing');
      if(identityOnly)return {expected_load_id:number,observed_load_id:number,
        identity_strategy:strategy==='PROVIDER_OPENER_BINDING'?'PROVIDER_OPENER_IDENTITY':strategy,confidence:'VERIFIED',
        board_hash:selected.revision,row_match:true,opener_belongs_to_row:row.contains(control),unique_panel:true,
        detail_field_match:signals.length>0,direct_panel_reference:!!relation,opener_identity_match:openerId===number,
        selection_transition:nowSelected&&!selected.selectedBefore,newly_visible:newlyVisible};
      const labels=[...panel.querySelectorAll('h1,h2,h3,[role="tab"],legend')].filter(visible).map(e=>norm(e.textContent));
      return {load_id:number,identity:{strategy,expected_load_id:number,provider_observed_load_id:number,
        evidence:{row_load_id:number,opener_belongs_to_row:true,unique_panel:true,relationship_attribute:relation?.attribute||null,
          row_dom_path:domPath(row),opener_dom_path:domPath(control),panel_dom_path:domPath(panel),
          detail_field_match:signals.length>0,selection_transition:nowSelected&&!selected.selectedBefore},scope:'OBSERVATION_ONLY'},
        stop_section_presence:labels.some(s=>['Stops','Pickup','Delivery'].includes(s)),
        appointment_section_presence:labels.some(s=>['Appointments','Pickup Appointment','Delivery Appointment'].includes(s))};
    }
    async function execute(command){
      C.validate(command);
      if(command.operation==='ASCEND_GET_SESSION_STATE')return session();
      guard();
      const current=await board();
      if(command.operation==='ASCEND_GET_ACTIVE_LOADS')return {source_view:'ACTIVE_LOADS',coverage:'VISIBLE_BOARD_ONLY',revision:current.revision,rows:current.facts};
      if(current.revision!==command.expected_revision)throw Error('board_revision_changed');
      const match=current.rows.find(r=>r.facts.load_id===command.load_id);if(!match)throw Error('exact_load_missing');
      if(command.operation==='ASCEND_FIND_LOAD')return {load_id:command.load_id,exact_row:true,revision:current.revision};
      if(command.operation==='ASCEND_OPEN_LOAD_READONLY'){
        const control=opener(match.row,command.load_id);capture(match.row,command.load_id,control,current.revision,match.cells[match.indexes['Load ID']]);
        if(selected.domSnapshot)FreightDeskWebBridge.DOMSnapshot.markClicked(selected.domSnapshot);
        control.click(); // Fixed read control only; never accept JS/selectors/actions from a command.
        return {load_id:command.load_id,opener_located:true,identity_verified:false};
      }
      if(selected?.revision!==current.revision)throw Error('selected_context_stale');
      const evidence=detail(command.load_id);
      if(command.operation==='ASCEND_READ_STOPS')return {...evidence,appointments:null,stops:null,mapping:'UNKNOWN'};
      if(command.operation==='ASCEND_READ_ASSIGNMENT')return {...evidence,carrier_presence:match.facts.carrier_presence,
        driver_presence:match.facts.driver_presence,power_unit_presence:match.facts.power_unit_presence,trailer_presence:match.facts.trailer_presence,source:'ACTIVE_LOADS_BOARD'};
      return {...match.facts,...evidence,source:'BOARD_FACTS_AND_DETAIL_IDENTITY',revision:current.revision};
    }
    function observeSelected(event){
      if(!event.isTrusted)throw Error('untrusted_selection');
      const control=event.target.closest('a,button');if(!control)return;
      const rows=grid();const match=rows.find(r=>r.row.contains(control));if(!match)return;
      if(opener(match.row,match.facts.load_id)!==control)throw Error('opener_ambiguous');
      // A future authorized controller binds a fresh revision before accepting this observation.
      capture(match.row,match.facts.load_id,control,null,match.cells[match.indexes['Load ID']]);
      return {load_id:match.facts.load_id,selection_observed:true,identity_verified:false};
    }
    async function executeIdentity(command,lease){
      lastView=null;
      C.validate(command);lease();
      if(command.operation==='ASCEND_OPEN_LOAD_READONLY')globalThis.FreightDeskWebBridge?.resetDiagnostic();
      if(!C.operations.slice(0,4).includes(command.operation))throw Error('COMMAND_NOT_ALLOWED');
      if(command.operation==='ASCEND_GET_SESSION_STATE'){
        const s=session();return {authenticated_app:s.session_authenticated,login_form_present:s.login_form_present,nav_markers:s.nav_markers};
      }
      guard();
      if(doc.location.pathname!=='/loads')throw Error('ACTIVE_VIEW_UNVERIFIED');
      const viewWatch=FreightDeskLoadBoardView.watch(doc,value=>{lastView=value;});
      const originalLease=lease;
      lease=()=>{originalLease();viewWatch.check();};
      try{
      lease(); // Independent provider view identity is required BEFORE any board-row access.
      const current=await board(true);lease();
      if(command.operation==='ASCEND_GET_ACTIVE_LOADS')return {source_view:'ACTIVE_LOADS',coverage:'VISIBLE_BOARD_ONLY',rows:current.facts,board_hash:current.revision,view_contract:lastView};
      if(current.revision!==command.expected_revision)throw Error('BOARD_CHANGED');
      const match=current.rows.find(r=>r.facts.load_id===command.load_id);if(!match)throw Error('EXACT_LOAD_MISSING');
      const control=opener(match.row,command.load_id);
      if(command.operation==='ASCEND_FIND_LOAD'){
        foundContext={row:match.row,control,revision:current.revision};
        return {load_id:command.load_id,exact_row:true,board_hash:current.revision,view_contract:lastView};
      }
      if(!foundContext||foundContext.row!==match.row||foundContext.control!==control||foundContext.revision!==current.revision)
        throw Error('TAB_STATE_CHANGED');
      const href=control.getAttribute('href')||'';
      // First test is a same-document opener only. No URL, script or form submission primitive.
      if((href&&!/^#[\w-]*$/.test(href))||control.hasAttribute('download')||
        !['','_self'].includes(control.getAttribute('target')||'')||control.hasAttribute('formaction'))throw Error('UNSAFE_OPENER');
      capture(match.row,command.load_id,control,current.revision,match.cells[match.indexes['Load ID']]);
      lease();if(selected.domSnapshot)FreightDeskWebBridge.DOMSnapshot.markClicked(selected.domSnapshot);
      control.click(); // Exactly once; never retry an uncertain click.
      const until=Date.now()+3000;let stable=null;
      while(Date.now()<until){
        await new Promise(resolve=>setTimeout(resolve,100));lease();guard();
        if((await board(true)).revision!==current.revision)throw Error('BOARD_CHANGED');
        lease();
        try{
          const evidence=detail(command.load_id,true),key=JSON.stringify(evidence);
          if(stable===key){verifiedDetail=evidence;verifiedContainerDiagnostic=selected.domSnapshot?FreightDeskWebBridge.diagnostic():null;
            return {...evidence,view_contract:lastView,...(verifiedContainerDiagnostic?{container_diagnostic:verifiedContainerDiagnostic}:{})};}
          stable=key;
        }catch(error){
          if(!['detail_binding_missing','provider_binding_missing'].includes(error.message))throw error;
          stable=null;
        }
      }
      throw Error('DETAIL_IDENTITY_MISSING');
      }finally{viewWatch.close();}
    }
    async function navigateActive(lease){
      lease();guard(true);lastView=doc.location.pathname==='/loads'?FreightDeskLoadBoardView.observe(doc).diagnostic:null;
      if(doc.location.pathname==='/loads'&&lastView?.confidence==='VERIFIED'&&lastView.view==='ACTIVE_LOADS')return {view_contract:lastView};
      // Only fixed provider navigation labels, outside operational forms and load rows.
      const target=doc.location.pathname==='/loads'?'Active Loads':'Loads';
      const candidates=[...doc.querySelectorAll('a,button,[role="tab"]')].filter(e=>visible(e)&&
        !e.closest('table,[role="grid"],form,[role="dialog"],dialog,.modal,.side-panel')&&norm(e.textContent)===target);
      bounded(candidates.length,8,'NAVIGATION_UNVERIFIED');
      if(candidates.length!==1)throw Error('NAVIGATION_UNVERIFIED');
      const control=candidates[0],href=control.getAttribute('href')||'';
      if(control.hasAttribute('download')||control.hasAttribute('formaction')||control.matches('[type="submit"],[type="reset"]')||
        !['','_self'].includes(control.getAttribute('target')||'')||control.tagName==='BUTTON'&&control.type!=='button')throw Error('UNSAFE_OPENER');
      if(target==='Loads'){
        if(control.tagName!=='A')throw Error('NAVIGATION_UNVERIFIED');
        const u=new URL(href,doc.location.href);
        if(u.origin!==C.origin||u.pathname!=='/loads'||u.search||u.hash||u.username||u.password)throw Error('UNSAFE_OPENER');
      }else if(href&&!/^#[\w-]*$/.test(href))throw Error('UNSAFE_OPENER');
      lease();control.click(); // One typed read-navigation action; never submit or retry the same click.
      if(target==='Loads')throw Error('NAVIGATION_STARTED'); // New document needs fresh session proof, not an old-page render wait.
      let stable=null;
      for(let i=0;i<30;i++){
        await new Promise(resolve=>setTimeout(resolve,100));lease();guard(true);
        lastView=FreightDeskLoadBoardView.observe(doc).diagnostic;
        if(doc.location.pathname==='/loads'&&lastView?.confidence==='VERIFIED'&&lastView.view==='ACTIVE_LOADS'){
          const key=JSON.stringify(lastView);if(stable===key)return {view_contract:lastView};stable=key;
        }else stable=null;
      }
      throw Error('ACTIVE_VIEW_UNVERIFIED');
    }
    async function executeRuntime(command,lease,progress=()=>{}){
      C.validateRuntime(command);lease();lastView=null;lastSchema=null;lastMappingSection=null;
      if(['ASCEND_MAP_WORKSPACE','ASCEND_MAP_NAVIGATE_SECTION'].includes(command.operation)){
        const started=performance.now();
        const check=()=>{lease();if(command.operation==='ASCEND_MAP_WORKSPACE'&&performance.now()-started>=3000)throw Error('READ_TIMEOUT');if(command.operation==='ASCEND_MAP_NAVIGATE_SECTION')guard(true);if(command.owner_present&&(doc.visibilityState!=='visible'||!doc.hasFocus()))throw Error('MAPPING_OWNER_NOT_PRESENT');};check();guard(true);check();
        if(command.operation==='ASCEND_MAP_WORKSPACE')progress({stage:'SESSION_VERIFIED',candidate_workspace_count:0,identity_signal_count:0,section_control_count:0,elapsed_ms:Math.floor(performance.now()-started)});
        const report=value=>{if(value.section_diagnostic)lastMappingSection=value.section_diagnostic;progress(value);};
        try{
          const mapped=await (command.operation==='ASCEND_MAP_NAVIGATE_SECTION'?FreightDeskWorkspace.navigate(doc,command,check):FreightDeskWebBridge.BrowserSensor.mapWorkspace(doc,command.approved_load_ids,check,report,started,command));guard(true);check();return mapped;
        }catch(error){if(error.section_diagnostic)lastMappingSection=error.section_diagnostic;throw error;}
      }
      if(command.operation==='ASCEND_GET_SESSION_STATE'){
        const s=session(true);return {authenticated_app:s.session_authenticated,login_form_present:s.login_form_present,nav_markers:s.nav_markers};
      }
      if(command.operation==='ASCEND_NAVIGATE_ACTIVE_LOADS')return navigateActive(lease);
      if(['ASCEND_FIND_LOAD','ASCEND_OPEN_LOAD_READONLY'].includes(command.operation))
        return executeIdentity(command,lease);
      guard();
      const watch=FreightDeskLoadBoardView.watch(doc,value=>{lastView=value;});
      const check=()=>{lease();watch.check();};
      try{
        check();let current;
        if(command.operation==='ASCEND_GET_ACTIVE_LOADS'){
          let stable=null,samples=0,stabilized=false;const until=Date.now()+3000;
          while(Date.now()<until){
            check();samples++;
            try{
              current=await board(true,true);check();
              const structural=JSON.stringify(lastSchema);
              if(structural===stable){lastSchema.render_samples=samples;stabilized=true;break;}
              stable=structural;
            }catch(error){if(FreightDeskReadErrors.safe(error)!=='BOARD_SCHEMA_INVALID')throw error;stable=null;current=null;}
            await new Promise(resolve=>setTimeout(resolve,150));
          }
          if(!current||!stabilized){if(lastSchema){lastSchema.render_samples=samples;lastSchema.failed_predicate||='STABILITY_TIMEOUT';}throw Error('BOARD_SCHEMA_INVALID');}
        }else current=await board(true,true);
        check();
        if(command.operation==='ASCEND_GET_ACTIVE_LOADS')return {source_view:'ACTIVE_LOADS',coverage:'VISIBLE_BOARD_ONLY',
          rows:current.facts,board_hash:current.revision,view_contract:lastView,schema_diagnostic:schemaDiagnostic()};
        if(current.revision!==command.expected_revision)throw Error('BOARD_CHANGED');
        if(!verifiedDetail||verifiedDetail.observed_load_id!==command.load_id||verifiedDetail.board_hash!==current.revision)
          throw Error('DETAIL_IDENTITY_MISSING');
        const identity=detail(command.load_id,true);check();
        if(JSON.stringify(identity)!==JSON.stringify(verifiedDetail))throw Error('DETAIL_IDENTITY_CONFLICT');
        if(command.operation==='ASCEND_DISCOVER_DETAIL_CONTRACT'){
          if(!globalThis.FreightDeskWebBridge||!selected.domSnapshot)throw Error('DETAIL_CONTRACT_UNAVAILABLE');
          const contract=await FreightDeskWebBridge.BrowserSensor.discover(selected.detailPanel,{...identity,view_contract:lastView,
            ...(verifiedContainerDiagnostic?{container_diagnostic:verifiedContainerDiagnostic}:{})},selected.containerReasons);
          check();
          if((await board(true,true)).revision!==current.revision)throw Error('BOARD_CHANGED');
          if(JSON.stringify(detail(command.load_id,true))!==JSON.stringify(identity))throw Error('DETAIL_IDENTITY_CONFLICT');
          check();return {load_id:command.load_id,board_hash:current.revision,view_contract:lastView,contract};
        }
        // No observed field contract yet: preserve unknown operational fields, never guess from labels or position.
        return {load_id:command.load_id,board_hash:current.revision,view_contract:lastView,mapping_state:'UNKNOWN',fields:[]};
      }finally{watch.close();}
    }
    function schemaDiagnostic(){
      if(!lastSchema)return null;
      const safe={...lastSchema,candidates:[...lastSchema.candidates],metadata_truncated:false};
      // Leave room for view proof, rows and the unchanged 64 KiB Native Messaging envelope.
      while(new TextEncoder().encode(JSON.stringify(safe)).length>30000&&safe.candidates.length>1){
        let index=safe.candidates.length-1;
        if(safe.candidates[index].candidate_index===safe.selected_candidate)index--;
        safe.candidates.splice(index,1);safe.metadata_truncated=true;
      }
      return safe;
    }
    return Object.freeze({execute,executeIdentity,executeRuntime,observeSelected,viewDiagnostic:()=>lastView,boardDiagnostic:schemaDiagnostic,mappingSectionDiagnostic:()=>lastMappingSection,
      detailDiagnostic:()=>globalThis.FreightDeskWebBridge?.diagnostic()||null});
  }
  globalThis.FreightDeskX1Reader=Object.freeze({create});
})();
