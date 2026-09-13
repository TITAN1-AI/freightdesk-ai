/* Local status only. Explicit owner controls never dispatch vendor operations from the dashboard. */
(() => {
  'use strict';
  const root=document.querySelector('#x1-runtime');
  if(!root)return;
  let revision=0,busy=false,timer=null;
  const state=document.querySelector('#x1-state'),grid=document.querySelector('#x1-facts');
  const notice=document.querySelector('#x1-action'),controls=[...root.querySelectorAll('[data-x1-action]')];
  const value=(data,key,fallback='UNKNOWN')=>data[key]??fallback;
  const timestamp=(input,fallback)=>input==null?fallback:typeof input==='number'?
    new Date(input*1000).toISOString().replace('T',' ').replace('.000Z',' UTC'):String(input);
  function render(data,locked=false){
    state.textContent=locked?'Owner session required':value(data,'state');
    grid.replaceChildren();
    const facts=[['Last completed capture stage',data.mapping_diagnostic?.stage??'Not recorded'],['Board evidence',value(data,'board_evidence_status','LAST_KNOWN_BOARD_EVIDENCE')],['Scheduler',value(data,'scheduler')],['Last operation',value(data,'execution_stage','None')],['Safe result',value(data,'error_code','None')],['Schema predicate',value(data,'schema_predicate','None')],['Extension',value(data,'extension','DISCONNECTED')],['Native host',value(data,'native_host','DISCONNECTED')],
      ['Pairing',value(data,'pairing','UNKNOWN')],['Session',value(data,'session','UNKNOWN')],
      ['Read access',value(data,'read_access','DISABLED')],['Bound tab',value(data,'bound_tab','NONE')],
      ['View',value(data,'view','UNKNOWN')],['Last board sync',timestamp(data.last_board_sync,'None')],
      ['Board hash',value(data,'board_hash','None')],['Loads',value(data,'load_count','Unknown')],
      ['Read access expires',timestamp(data.lease_expires_at,'Not enabled')]];
    for(const [label,text] of facts){
      const dt=document.createElement('dt'),dd=document.createElement('dd');
      dt.textContent=label;dd.textContent=String(text);grid.append(dt,dd);
    }
    notice.textContent=locked?'Open FreightDesk with your private owner launcher.':
      data.owner_action||data.action||'Open Ascend and sign in normally. Writes remain disabled.';
    for(const button of controls)button.disabled=locked||busy;
    const enable=controls.find(b=>b.dataset.x1Action==='enable');
    if(enable)enable.disabled=locked||busy||data.pairing!=='VALID'||data.read_access==='ENABLED';
  }
  async function refresh(){
    const current=++revision;
    try{
      const response=await fetch('/api/ascend/runtime/status');
      if(current!==revision)return;
      if(!response.ok){render({},true);return;}
      const data=await response.json();if(current!==revision)return;render(data);
    }catch{if(current===revision)render({state:'ERROR',owner_action:'Local Ascend status is unavailable.'});}
  }
  async function control(action){
    if(busy)return;
    busy=true;revision++;for(const button of controls)button.disabled=true;
    try{
      const response=await fetch('/api/ascend/runtime/control',{method:'POST',
        headers:{'Content-Type':'application/json','x-freightdesk-local':'1'},
        body:JSON.stringify({action,hours:8})});
      if(!response.ok)throw Error('control_failed');
      const data=await response.json();busy=false;render(data);
      if(action==='repair')notice.textContent='Enrollment and read access closed. Run the local owner enrollment setup to pair again.';
    }catch{
      busy=false;await refresh();notice.textContent='Unable to complete that owner action. Check local enrollment and access.';
    }
  }
  for(const button of controls)button.addEventListener('click',()=>control(button.dataset.x1Action));
  document.querySelector('#x1-refresh').addEventListener('click',refresh);
  document.addEventListener('freightdesk-live-ready',refresh);
  // Only poll the local projection while the dashboard is visible; FreightDesk's host owns vendor scheduling.
  function schedule(){clearTimeout(timer);if(!document.hidden)timer=setTimeout(async()=>{await refresh();schedule();},15000);}
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();schedule();});
  refresh();schedule();
})();
