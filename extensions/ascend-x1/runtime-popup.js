'use strict';
(() => {
  let operationMode=null;
  const states=new Set(['MAPPING_READY','CONTENT_SCRIPT_MISSING','CONTENT_SCRIPT_OLD_VERSION','CONTENT_SCRIPT_PORT_STALE','DOCUMENT_CHANGED','PROTOCOL_VERSION_MISMATCH','CONTENT_SCRIPT_INJECTION_BLOCKED','CONTENT_SCRIPT_RECOVERY_FAILED','DISCOVERING_ASCEND','NAVIGATING_ACTIVE_LOADS','BOUND','TAB_DISCOVERY_FAILED','CONTENT_SCRIPT_STALE','VIEW_UNVERIFIED','SCHEDULER_NOT_RUNNING','NOT_ENROLLED','HOST_UNAVAILABLE','HOST_NOT_REGISTERED','OFFLINE_PROTOTYPE','PAIRING_REQUIRED','PAIRING_STALE','PAIRED','READ_ONLY_READY','ERROR',
    'WAITING_FOR_ASCEND','ASCEND_REAUTH_REQUIRED','TAB_SELECTION_REQUIRED','STOPPED','PAUSED','READ_LEASE_EXPIRED','READ_ACCESS_DISABLED']);
  const action=s=>s==='MAPPING_READY'?'Mapping Mode: navigate manually, then capture the current section.':s==='CONTENT_SCRIPT_STALE'?'Automatic content reconnect pending':s==='TAB_DISCOVERY_FAILED'?'Check X1 site access and discovery result.':s==='SCHEDULER_NOT_RUNNING'?'Open Edge with X1 enabled.':s==='VIEW_UNVERIFIED'?'Review the Active Loads navigation result in FreightDesk.':s==='ASCEND_REAUTH_REQUIRED'?'Sign into Ascend.':s==='TAB_SELECTION_REQUIRED'?'Choose the Ascend tab to use.':
    s==='NOT_ENROLLED'?'Complete one-time owner enrollment on Windows after the native host is registered.':s==='PAIRING_STALE'?'Review enrollment in FreightDesk.':
    s==='HOST_NOT_REGISTERED'?'Native host is Windows-only and is not registered for this browser.':
    s==='OFFLINE_PROTOTYPE'?'Extension loaded. Pairing and reads stay dormant until the Windows native host is present.':
    s==='PAIRING_REQUIRED'?'Import an owner-created enrollment file only on the registered Windows host.':
    s==='WAITING_FOR_ASCEND'?'Open Ascend normally.':s==='HOST_UNAVAILABLE'?'Start FreightDesk on Windows with the registered native host.':
    s==='STOPPED'||s==='ERROR'?'Review the safe runtime result in FreightDesk.':'';
  const captureStages=new Set(['TAB_VERIFIED','SESSION_VERIFIED','ENTITY_DISCOVERY','LOAD_WORKSPACE_CANDIDATE_FOUND','WORKSPACE_IDENTITY_VERIFIED','SECTION_IDENTIFIED','STRUCTURE_CAPTURED','MAP_PERSISTED']);
  const fields={mapping_stage:'Last completed capture stage',mapping_operation_mode:'Mapping mode',mapping_scope:'Mapping scope',mapping_workspace_count:'Workspace captures',mapping_section_count:'Section observations',mapping_contract_count:'Field observations',mapping_capture_count:'Mapping captures',mapping_capture_limit:'Capture limit',schema_predicate:'Schema predicate',board_evidence_status:'Board evidence',extension:'Extension',native_host:'Native host',pairing:'Pairing',session:'Session',read_access:'Read access',
    scheduler:'Scheduler',error_code:'Safe result',bound_tab:'Bound tab',view:'View',last_board_sync:'Last board sync',board_hash:'Board hash',load_count:'Loads'};
  const stateValues=new Set(['OBSERVE','AUTO_MAP','FIRST_VALIDATION','NORMAL_OWNER_PRESENT','CURRENT_VERIFIED_BOARD','LAST_KNOWN_BOARD_EVIDENCE','NO_BOARD_EVIDENCE','RUNNING','NOT_RUNNING','CONNECTED','DISCONNECTED','VALID','UNKNOWN','AUTHENTICATED','ASCEND_REAUTH_REQUIRED','ENABLED',
    'DISABLED','EXPIRED','REVOKED','ACTIVE','NONE','UNBOUND','ACTIVE_LOADS','ALL_LOADS','READY_FOR_ACCOUNTING','OTHER']);
  function render(s){
    const state=states.has(s?.state)?s.state:'ERROR';operationMode=s?.mapping_operation_mode;
    document.getElementById('runtime-state').textContent=state;document.getElementById('runtime-action').textContent=s?.mapping_scope==='NORMAL_OWNER_PRESENT'&&state==='MAPPING_READY'?'Mapping your current foreground workspace as you navigate. Metadata only.':action(state);
    const rows=[];
    for(const [key,label] of Object.entries(fields)){
      const value=key==='mapping_stage'?s?.mapping_diagnostic?.stage:s?.[key];let text='UNKNOWN';
      if(key==='mapping_stage'&&captureStages.has(value))text=value;
      if(['mapping_capture_count','mapping_capture_limit','mapping_workspace_count','mapping_section_count','mapping_contract_count'].includes(key)&&Number.isInteger(value)&&value>=0&&value<=3000)text=String(value);
      else if(key==='board_hash'&&typeof value==='string'&&/^[a-f0-9]{64}$/.test(value))text=value;
      else if(key==='load_count'&&Number.isInteger(value)&&value>=0&&value<=100)text=String(value);
      else if(key==='last_board_sync'&&typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<253402300800)text=new Date(value*1000).toISOString();
      else if(key==='last_board_sync'&&typeof value==='string'&&/^\d{4}-\d{2}-\d{2}T[\d:.+-]+Z?$/.test(value))text=value;
      else if(key==='error_code'&&['NO_FOREGROUND_ASCEND_WORKSPACE','EXPECTED_LOAD_NOT_OPEN','STARTING_SECTION_MISMATCH','NOT_A_LOAD_WORKSPACE','MAPPING_CAPTURE_BOUND','MAPPING_CAPTURE_PENDING','MAPPING_COMPLETE','NAVIGATION_CONTRACT_UNVERIFIED','NAVIGATION_CONTROL_AMBIGUOUS','NAVIGATION_CONTROL_CHANGED','AUTO_MAP_SECTION_UNVERIFIED','MAPPING_VALIDATION_REQUIRED','MAPPING_WORKSPACE_BOUND','MAPPING_SECTION_BOUND','MAPPING_CONTRACT_BOUND','MAPPING_OWNER_NOT_PRESENT','MAPPING_CONTRACT_INVALID','MAPPING_NOT_ENABLED','MAPPING_PAYLOAD_BOUND','MAPPING_SESSION_CONSUMED','WORKSPACE_AMBIGUOUS','WORKSPACE_BOUND','WORKSPACE_CHANGED','WORKSPACE_IDENTITY_CONFLICT','WORKSPACE_IDENTITY_MISSING','WORKSPACE_SCOPE_DENIED','WORKSPACE_SECTION_UNVERIFIED','BOARD_SCHEMA_INVALID','READ_TIMEOUT','ACTIVE_VIEW_UNVERIFIED','ACTIVE_VIEW_NOT_ACTIVE_LOADS','ACTIVE_VIEW_CHANGED','NAVIGATION_UNVERIFIED','NAVIGATION_STARTED','REFRESH_ASCEND_TAB','TAB_DISCOVERY_FAILED','CONTENT_SCRIPT_STALE','READ_PERSIST_FAILED','READ_EXECUTION_FAILED','RECEIPT_INVALID','HOST_NOT_REGISTERED','NATIVE_HOST_WINDOWS_ONLY'].includes(value))text=value;
      else if(key==='schema_predicate'&&['CANDIDATE_GRID_BOUND', 'NO_VISIBLE_GRID', 'REQUIRED_HEADERS_MISSING', 'AMBIGUOUS_DATA_GRIDS', 'HEADER_COUNT_MISMATCH', 'DUPLICATE_REQUIRED_HEADERS', 'HEADER_SPAN', 'ROW_SPAN', 'ARIA_COLUMN_ALIGNMENT', 'ROW_COUNT_BOUND', 'ROW_CELL_COUNT_MISMATCH', 'EMPTY_STATE_UNVERIFIED', 'INITIALIZATION_BUSY', 'ROW_IDENTITY_INVALID', 'DUPLICATE_LOAD_ID', 'STABILITY_TIMEOUT', 'HOST_DUPLICATE_LOAD_ID', 'HOST_BOARD_HASH_MISMATCH', 'STRUCTURAL_METADATA_UNAVAILABLE'].includes(value))text=value;
      else if(stateValues.has(value))text=value;
      const term=document.createElement('dt'),description=document.createElement('dd');term.textContent=label;description.textContent=text;rows.push(term,description);
    }
    document.getElementById('runtime-health').replaceChildren(...rows);
    const capture=document.getElementById('mapping-capture');if(capture)capture.textContent=operationMode==='AUTO_MAP'?'Map current load (closes popup)':'Capture current workspace section';if(capture)capture.disabled=!(s?.mapping_mode&&s.read_access==='ENABLED'&&!s.paused&&s.state!=='STOPPED'&&!s.mapping_capture_requested&&s.mapping_capture_count<s.mapping_capture_limit);
  }
  async function send(message){try{const result=await chrome.runtime.sendMessage(message);render(result);return result;}catch{render({state:'HOST_UNAVAILABLE'});return null;}}
  document.getElementById('runtime-rebind').onclick=()=>send({action:'RUNTIME_REBIND'});
  document.getElementById('runtime-list').onclick=async()=>{
    const result=await chrome.runtime.sendMessage({action:'RUNTIME_TABS'}).catch(()=>null),select=document.getElementById('runtime-tab');
    select.replaceChildren(new Option('Select an Ascend tab',''));
    for(const tab of result?.tabs||[])if(Number.isInteger(tab.tab_id)&&['/','/loads','/login.html','OTHER'].includes(tab.path))
      select.add(new Option('Ascend '+tab.path+' (tab '+tab.tab_id+')',String(tab.tab_id)));
  };
  document.getElementById('runtime-select').onclick=()=>{
    const value=document.getElementById('runtime-tab').value;
    if(/^\d+$/.test(value))send({action:'RUNTIME_SELECT',tab_id:Number(value)});
  };
  const capture=document.getElementById('mapping-capture');if(capture)capture.onclick=()=>{if(operationMode==='AUTO_MAP'){chrome.runtime.sendMessage({action:'RUNTIME_MAPPING_CAPTURE'}).catch(()=>{});window.close();}else send({action:'RUNTIME_MAPPING_CAPTURE'});};
  send({action:'RUNTIME_STATUS'});setInterval(()=>send({action:'RUNTIME_STATUS'}),1000);
})();
