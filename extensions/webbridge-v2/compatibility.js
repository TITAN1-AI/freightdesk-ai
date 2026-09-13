/* Offline compatibility revision 3: coherent capture, document ledger, compact metadata wire. */
(() => {
  'use strict';
  globalThis.FreightDeskV2Compatibility=Object.freeze({install({mode}={}) {
    if(mode!=='OFFLINE'||globalThis.chrome?.runtime?.id!=='fixture')throw Error('V2_OFFLINE_ONLY');
    const original=globalThis.FreightDeskWebBridge,W=globalThis.FreightDeskWorkspace,S=globalThis.FreightDeskMappingScope;
    const vocabulary=[...new Set([...S.sections,...Object.keys(S.fields),...S.actions])];
    let entry=null,busy=false,disposed=false;
    const dispose=()=>{entry?.harness.close();entry=null;};
    // A bfcache suspension retains the physical document and therefore its WeakMap ledger.
    const pagehide=event=>{if(event.persisted){entry?.harness.release();if(entry)entry.proof=null;}else dispose();};
    globalThis.addEventListener('pagehide',pagehide);
    async function mapWorkspace(doc,allowed,check,progress,started,command) {
      if(disposed)throw Error('V2_CLOSED');
      if(busy)throw Error('MAPPING_CAPTURE_PENDING');busy=true;
      let observer=null,dirty=false,before=null,section=null;
      const documentBinding={...globalThis.__freightdeskX1Document};
      const guard=()=>{
        check();if(performance.now()-started>=3000)throw Error('READ_TIMEOUT');
        if(globalThis.__freightdeskX1Document.id!==documentBinding.id||globalThis.__freightdeskX1Document.generation!==documentBinding.generation)throw Error('DOCUMENT_CHANGED');
        if(dirty||observer?.takeRecords().length)throw Error('WORKSPACE_CHANGED');
      };
      const stop=(predicate,stage,bound=null)=>{
        const error=Error('WORKSPACE_SECTION_UNVERIFIED');
        error.section_diagnostic={...section.diagnostic,v2_diagnostic:{schema_version:2,stage,predicate,
          bound_category:bound?.category||null,measured:bound?Math.ceil(bound.measured):null,maximum:bound?.maximum??null}};
        throw error;
      };
      try {
        guard();
        const legacy=await W.capture(doc,allowed,guard,progress,started,command,{onVerified(value){
          before=value.workspace;section=value.section;
          observer=new doc.defaultView.MutationObserver(()=>{dirty=true;});
          observer.observe(before.shell,{subtree:true,childList:true,attributes:true,characterData:true});
          if(before.shell.parentElement)observer.observe(before.shell.parentElement,{childList:true});
        }});
        guard();if(!before||!section)throw Error('WORKSPACE_CHANGED');
        if(!entry||entry.doc!==doc||entry.epoch!==documentBinding.id||entry.realm!==documentBinding.generation){
          dispose();
          const current={doc,epoch:documentBinding.id,realm:documentBinding.generation,proof:null,harness:null};
          current.harness=FreightDeskWebBridgeV2.createOfflineHarness({mode:'OFFLINE',origin:'https://ascendtms.com',
            vocabulary,sections:S.sections,stateClasses:['active','selected'],readProof(){
              if(!current.proof)throw Error('V2_AUTHORITY_UNAVAILABLE');return current.proof();
            }});entry=current;
        }
        entry.proof=()=>{guard();return {schemaVersion:2,document:doc,root:before.shell,epoch:documentBinding.id,realm:String(documentBinding.generation),
          leaseRef:'lease-'+Math.trunc(command.lease_expires_at*1000),sessionRef:'dispatch-'+command.request_id,
          provider:'AscendTMS',entityType:'LOAD',entityId:before.contract.load_id,identityVerified:true,
          ownerPresent:doc.hasFocus(),foreground:doc.visibilityState==='visible',sessionVerified:true,leaseValid:true,revoked:false};};
        const harness=entry.harness,captured=await harness.capture(command.request_id);guard();
        if(captured.status!=='CAPTURED')stop(captured.error_code,captured.last_completed_stage,captured.bound);
        const proof=harness.section(captured.graph);
        if(proof.status!=='VERIFIED')stop(proof.failed_predicate,'RELATIONSHIPS_RESOLVED');
        if(proof.section!==section.name||harness.resolveNode(captured.graph,proof.root)!==section.root)
          stop('COMPATIBILITY_ROOT_MISMATCH','SECTION_VERIFIED');
        const after=W.observeWorkspace(doc,allowed,Date.now()/1000,guard,()=>{},before.shell),current=W.observeSection(after);
        if(after.shell!==before.shell||after.contract.load_id!==before.contract.load_id||current.root!==section.root||current.name!==section.name)
          throw Error('WORKSPACE_CHANGED');
        const fresh=await W.fields(current,after.contract.load_id,legacy.workspace.observed_at,guard);
        if(JSON.stringify(fresh)!==JSON.stringify(legacy.section.fields))throw Error('WORKSPACE_CHANGED');
        const fields=legacy.section.fields.map((field,index)=>{
          let element=section.root;for(const step of field.locator_graph.relative_path)element=element?.children[step];
          const id=harness.nodeRef(captured.graph,element),node=captured.graph.nodes.find(n=>n.id===id);
          if(!node||!node.visible||field.field_name_candidate!=='UNKNOWN'&&S.fields[node.name]!==field.field_name_candidate)
            stop('FIELD_GRAPH_MISMATCH','SECTION_VERIFIED');
          return {index,node:id,fingerprint:field.contract_fingerprint};
        });
        const graph=FreightDeskWebBridgeV2.toWire(captured.graph),graphBytes=new TextEncoder().encode(JSON.stringify(graph)).length;
        if(graphBytes>32000)stop('V2_BOUND_EXCEEDED','SECTION_VERIFIED',{category:'payloadBytes',measured:graphBytes,maximum:32000});
        const output={...legacy,webbridge_v2:{compatibility_version:3,graph,section:proof,fields}};
        if(new TextEncoder().encode(JSON.stringify(output)).length>45000)throw Error('MAPPING_PAYLOAD_BOUND');
        guard();return output;
      } finally {observer?.disconnect();if(entry){entry.proof=null;entry.harness.release();}busy=false;}
    }
    globalThis.FreightDeskWebBridge=Object.freeze({...original,BrowserSensor:Object.freeze({...original.BrowserSensor,mapWorkspace})});
    return Object.freeze({dispose(){disposed=true;dispose();globalThis.removeEventListener('pagehide',pagehide);}});
  }});
})();
