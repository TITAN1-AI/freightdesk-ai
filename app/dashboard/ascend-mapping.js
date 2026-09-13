/* Owner product controls. Polling reads local job status only. No vendor requests or selectors. */
(() => {
  'use strict';
  const root=document.querySelector('#ascend-mapping');if(!root)return;
  const get=id=>document.getElementById(id);let busy=false,locked=true,last=null;
  const labels={stage:'Current stage',safe_stop_code:'Safe stop code',last_completed_dom_stage:'Last completed DOM stage',failed_predicate:'Failed predicate',owner_action_text:'Owner action',cleanup_state:'Cleanup state',scope:'Target scope',workspaces_observed:'Workspaces observed',sections_observed:'Sections observed',contracts_proposed:'Contracts proposed',contracts_validated:'Contracts validated',maturity:'Provider map maturity',drift_detected:'Drift detected',needs_review:'Needs review'};
  const friendly=value=>typeof value==='boolean'?(value?'Yes':'No'):typeof value==='string'?value.replaceAll('_',' ').toLowerCase().replace(/^./,s=>s.toUpperCase()):String(value);
  function render(data){
    last=data;get('mapping-status').textContent=friendly(data.status||'Owner session required');get('mapping-message').textContent=data.message||'Open the protected owner dashboard to map Ascend.';
    get('mapping-facts').replaceChildren();
    for(const [key,label] of Object.entries(labels)){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=friendly(data[key]??'Unknown');get('mapping-facts').append(dt,dd);}
    const review=get('mapping-review');review.hidden=!(data.needs_review&&data.owner_action==='REVIEW_NEW_NAVIGATION');
    const holder=get('mapping-review-sections');
    if(holder.dataset.signature!==JSON.stringify(data.review_sections||[])){
      holder.replaceChildren();holder.dataset.signature=JSON.stringify(data.review_sections||[]);
      for(const name of data.review_sections||[]){const label=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.value=name;label.append(box,document.createTextNode(name));holder.append(label);}
    }
    for(const button of root.querySelectorAll('[data-mapping-action]')){
      const action=button.dataset.mappingAction;button.disabled=locked||busy||action==='start'&&!['IDLE','COMPLETE','STOPPED'].includes(data.status)||['cancel','pause'].includes(action)&&['IDLE','COMPLETE','STOPPED'].includes(data.status)||action==='resume'&&data.status!=='PAUSED'||action==='review'&&review.hidden;
    }
  }
  async function refresh(){if(busy)return;try{const response=await fetch('/api/ascend/mapping/status');locked=!response.ok;render(response.ok?await response.json():{});}catch{locked=true;render({message:'Local mapping status is unavailable.'});}}
  async function control(action){
    if(busy||locked)return;busy=true;render(last||{});
    const body={action};
    if(action==='start'){
      const scope=get('mapping-scope').value;body.intent={scope};
      if(scope==='VALIDATION_COHORT')body.intent.load_ids=get('mapping-cohort').value.split(',').map(s=>s.trim());
    }
    if(action==='review')body.sections=[...get('mapping-review-sections').querySelectorAll('input:checked')].map(e=>e.value);
    try{const response=await fetch('/api/ascend/mapping/control',{method:'POST',headers:{'Content-Type':'application/json','x-freightdesk-local':'1'},body:JSON.stringify(body)});if(!response.ok)throw Error('STOP');const data=await response.json();busy=false;render(data);}
    catch{busy=false;await refresh();get('mapping-message').textContent='The operation could not continue. Review the preserved report.';}
  }
  for(const button of root.querySelectorAll('[data-mapping-action]'))button.addEventListener('click',()=>control(button.dataset.mappingAction));
  get('mapping-report-button').addEventListener('click',async()=>{
    const response=await fetch('/api/ascend/mapping/report');if(!response.ok)return;
    const report=await response.json();delete report.advanced_reports;
    get('mapping-report').textContent=JSON.stringify(report,null,2);get('mapping-report').hidden=false;
  });
  get('mapping-scope').addEventListener('change',()=>{get('mapping-cohort-scope').hidden=get('mapping-scope').value!=='VALIDATION_COHORT';});
  document.addEventListener('freightdesk-live-ready',refresh);refresh();setInterval(()=>{if(!document.hidden)refresh();},2000);
})();
