(() => {
  'use strict';
  if(location.origin!==FreightDeskX1Contract.origin) return;
  // Bootstrap installs no page click/mutation listeners and performs no reads without a paired host grant.
  // Isolated-world state cannot be changed by provider page JavaScript.
  const PRODUCTION_CONNECTION_ENABLED=false;
  const B=FreightDeskBuild;
  if(chrome.runtime.getManifest().version!==B.extension_version)return;
  // Dispose our own prior registration. Pre-0.4.1 listeners never understand the new dispatch kind.
  globalThis.__freightdeskX1Registration?.dispose();
  const prior=globalThis.__freightdeskX1Document;
  const documentId=prior?.id||crypto.randomUUID().replaceAll('-','');
  const documentGeneration=(prior?.generation||0)+1;
  globalThis.__freightdeskX1Document={id:documentId,generation:documentGeneration};
  let activePort=null,reader=null;
  // Only the private extension worker can acquire this top-frame, document-bound read channel.
  // A port alone performs no DOM read. Each command needs the worker's verified native dispatch.
  const onConnect=port=>{
    if(port.name!=='freightdesk-x1-identity'||port.sender?.id!==chrome.runtime.id||port.sender?.tab){port.disconnect();return;}
    if(activePort)activePort.disconnect();
    activePort=port;let alive=true,busy=false;const used=new Set(),initialPath=location.pathname;
    const causal=reason=>{
      try{port.postMessage({kind:'X1_CAUSAL_TRACE',document_id:documentId,document_generation:documentGeneration,reason});}catch{/* Diagnostic failure never changes security or execution gates. */}
    };
    let mappingObserver=null,mappingExpiry=0,mappingTimer=null,mappingStopTimer=null,readinessExpiry=0;
    const clearMapping=()=>{mappingObserver?.disconnect();mappingObserver=null;clearTimeout(mappingTimer);clearTimeout(mappingStopTimer);mappingExpiry=0;};
    const mappingHint=()=>{
      if(!alive||Date.now()/1000>=mappingExpiry)return;
      clearTimeout(mappingTimer);mappingTimer=setTimeout(()=>{
        if(alive&&Date.now()/1000<mappingExpiry&&document.visibilityState==='visible'&&document.hasFocus())
          port.postMessage({kind:'X1_MAPPING_CHANGED_V1',document_id:documentId,document_generation:documentGeneration});
      },2000);
    };
    const ownerFocus=()=>{
      if(alive&&Date.now()/1000<readinessExpiry&&document.visibilityState==='visible'&&document.hasFocus())
        port.postMessage({kind:'X1_OWNER_READINESS_CHANGED',document_id:documentId,document_generation:documentGeneration});
      mappingHint();
    };
    addEventListener('focus',ownerFocus);
    document.addEventListener?.('visibilitychange',ownerFocus);
    const invalidate=()=>{alive=false;clearMapping();readinessExpiry=0;removeEventListener('focus',ownerFocus);document.removeEventListener?.('visibilitychange',ownerFocus);if(activePort===port)activePort=null;};
    port.onDisconnect.addListener(invalidate);
    const pagehide=()=>{invalidate();port.disconnect();};
    addEventListener('pagehide',pagehide,{once:true});
    port.postMessage({kind:'X1_DOCUMENT_READY',trace_revision:1,mapping_reader_revision:globalThis.FreightDeskWorkspace?.readerRevision,build:B,document_generation:documentGeneration,document_id:documentId,path:['/','/loads','/login.html'].includes(initialPath)?initialPath:'OTHER'});
    port.onMessage.addListener(async message=>{
      // Presence is a fixed document-bound readiness signal, never authority to inspect a workspace.
      // Arming this listener during the short probe lease lets the owner return without racing capture.
      if(message?.kind==='X1_OWNER_READINESS'){
        if(!alive||activePort!==port||Object.keys(message).sort().join()!=='document_generation,document_id,kind,lease_expires_at,request_id'||
          message.document_id!==documentId||message.document_generation!==documentGeneration||typeof message.request_id!=='string'||!/^[a-f0-9]{32}$/.test(message.request_id)||
          typeof message.lease_expires_at!=='number'||!Number.isFinite(message.lease_expires_at)||location.origin!==FreightDeskX1Contract.origin||location.pathname!==initialPath){port.disconnect();return;}
        readinessExpiry=Math.min(message.lease_expires_at,Date.now()/1000+1800);
        if(document.visibilityState!=='visible')causal('FOREGROUND_LOST');
        else if(!document.hasFocus())causal('FOCUS_LOST');
        port.postMessage({kind:'X1_OWNER_READINESS_ACK',document_id:documentId,document_generation:documentGeneration,request_id:message.request_id,
          owner_present:!busy&&Date.now()/1000<readinessExpiry&&document.visibilityState==='visible'&&document.hasFocus()});
        return;
      }
      const check=()=>{
        if(!alive){causal('CONTENT_PORT_DISCONNECTED');throw Error('PAIRING_LOST');}
        if(activePort!==port){causal('CONTENT_PORT_REPLACED');throw Error('PAIRING_LOST');}
        if(location.origin!==FreightDeskX1Contract.origin||location.pathname!==initialPath){causal('CONTENT_PATH_CHANGED');throw Error('DOCUMENT_CHANGED');}
        if(Date.now()/1000>=message.deadline)throw Error('READ_TIMEOUT');
      };
      try{
        if(busy||!message||Object.keys(message).sort().join()!=='command,deadline,document_generation,document_id,kind'||message.kind!=='X1_RUNTIME_DISPATCH_V2'||message.document_generation!==documentGeneration||
          message.document_id!==documentId||typeof message.deadline!=='number'||message.deadline>Date.now()/1000+13)
          throw Error('COMMAND_NOT_ALLOWED');
        const runtime=true;
        (runtime?FreightDeskX1Contract.validateRuntime:FreightDeskX1Contract.validate)(message.command);
        if(!(runtime?FreightDeskX1Contract.runtimeOperations:FreightDeskX1Contract.operations.slice(0,4)).includes(message.command.operation))throw Error('COMMAND_NOT_ALLOWED');
        if(used.has(message.command.request_id))throw Error('DUPLICATE_REQUEST');
        used.add(message.command.request_id);busy=true;check();
        if(message.command.operation==='ASCEND_MAP_WORKSPACE')port.postMessage({kind:'X1_CAPTURE_ACK',document_generation:documentGeneration,document_id:documentId});
        if(['ASCEND_MAP_WORKSPACE','ASCEND_MAP_NAVIGATE_SECTION'].includes(message.command.operation)&&message.command.owner_present){
          clearMapping();mappingExpiry=Math.min(message.command.lease_expires_at,Date.now()/1000+1800);
          mappingStopTimer=setTimeout(clearMapping,Math.max(0,(mappingExpiry-Date.now()/1000)*1000));
        }
        reader=reader||await FreightDeskX1Reader.create(document,location.origin);check();
        const evidence=await (runtime?reader.executeRuntime:reader.executeIdentity)(message.command,check,diagnostic=>port.postMessage({kind:'X1_MAPPING_PROGRESS',document_generation:documentGeneration,document_id:documentId,diagnostic}));check();
        if((message.command.operation==='ASCEND_MAP_WORKSPACE'||message.command.operation==='ASCEND_MAP_NAVIGATE_SECTION'&&message.command.return_to_start)&&message.command.owner_present){
          const observed=FreightDeskWorkspace.observeWorkspace(document,message.command.approved_load_ids,Date.now()/1000);
          if(observed.contract.load_id!==evidence.workspace.load_id||FreightDeskWorkspace.observeSection(observed).name!==evidence.section.section)throw Error('WORKSPACE_CHANGED');
          mappingObserver=new MutationObserver(mappingHint);
          mappingObserver.observe(observed.shell,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['aria-selected','aria-current','class','hidden','data-load-id','data-load-workspace']});
          if(observed.shell.parentElement)mappingObserver.observe(observed.shell.parentElement,{childList:true});
        }
        port.postMessage({kind:'X1_RESULT_V2',document_generation:documentGeneration,document_id:documentId,evidence,error_code:null});
      }catch(error){
        const view=reader?.viewDiagnostic?.(),code=FreightDeskReadErrors.safe(error);
        const schema=code==='BOARD_SCHEMA_INVALID'?reader?.boardDiagnostic?.():null;
        const detail=code.startsWith('DETAIL_')&&['ASCEND_OPEN_LOAD_READONLY','ASCEND_DISCOVER_DETAIL_CONTRACT'].includes(message?.command?.operation)?reader?.detailDiagnostic?.():null;
        const section=['ASCEND_MAP_WORKSPACE','ASCEND_MAP_NAVIGATE_SECTION'].includes(message?.command?.operation)?reader?.mappingSectionDiagnostic?.():null;
        const evidence=view||section?{...(view?{view_contract:view}:{}),...(schema?{schema_diagnostic:schema}:{}),...(detail?{detail_container_diagnostic:detail}:{}),...(section?{section_diagnostic:section}:{})}:null;
        if(alive)port.postMessage({kind:'X1_RESULT_V2',document_generation:documentGeneration,document_id:documentId,evidence,error_code:code});
      }finally{busy=false;}
    });
  };
  chrome.runtime.onConnect.addListener(onConnect);
  globalThis.__freightdeskX1Registration={dispose(){chrome.runtime.onConnect.removeListener(onConnect);if(activePort)activePort.disconnect();activePort=null;reader=null;}};
  chrome.runtime.onMessage.addListener((command,sender,reply)=>{
    if(sender.id!==chrome.runtime.id||sender.tab) return false;
    try {
      FreightDeskX1Contract.validate(command);
      if(!PRODUCTION_CONNECTION_ENABLED) throw Error('production_bridge_disabled');
    } catch { reply({ok:false,error_code:'production_bridge_disabled'}); }
    return false;
  });
})();
