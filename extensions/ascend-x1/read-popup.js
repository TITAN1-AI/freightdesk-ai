(() => {
  'use strict';
  const get=id=>document.getElementById(id),labels=['1. Verify session','2. Read and reconcile Active Loads','3. Find exact load 1755','4. Open 1755 for identity only'];
  let busy=false;
  function render(value){
    get('read-state').textContent=value.error_code||value.state||'Explicit tab selected';
    if(value.receipt||value.plan)get('read-receipt').textContent=JSON.stringify(value.receipt||value.plan,null,2);
    if(value.state){
      get('read-next').disabled=value.state!=='READ_ONLY_READY';
      get('read-next').textContent=labels[value.index||0]||'Identity complete — further reads blocked';
    }
  }
  async function send(message){
    if(busy)return null;busy=true;
    try{const value=await chrome.runtime.sendMessage(message);render(value);return value;}
    catch{render({state:'STOPPED',error_code:'PAIRING_LOST'});return null;}
    finally{busy=false;}
  }
  get('read-tabs').onclick=async()=>{
    const value=await send({action:'LIST_ASCEND_TABS'});
    if(!value?.tabs)return;
    const select=get('read-tab');select.replaceChildren(new Option('Select a tab',''));
    for(const tab of value.tabs)select.add(new Option('Ascend tab '+tab.tab_id+' — '+tab.path,String(tab.tab_id)));
    get('read-state').textContent=value.tabs.length?value.tabs.length+' eligible tabs. Select one explicitly.':'NO_ELIGIBLE_TAB';
  };
  get('read-select').onclick=()=>{
    if(get('read-tab').value===''){render({state:'STOPPED',error_code:'TAB_SELECTION_REQUIRED'});return;}
    send({action:'SELECT_ASCEND_TAB',tab_id:Number(get('read-tab').value)});
  };
  get('read-plan').onclick=()=>send({action:'LOAD_READ_PLAN'});
  get('read-next').onclick=()=>send({action:'READ_NEXT'});
  // Restore an already received safe result when the popup is reopened. No vendor read is issued.
  send({action:'READ_STATUS'});
})();
