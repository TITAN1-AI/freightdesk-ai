/* Offline integration only. Not packaged in X1; no new browser command or permission. */
(() => {
  'use strict';
  globalThis.FreightDeskV2Compatibility=Object.freeze({install({mode}={}) {
    if(mode!=='OFFLINE'||globalThis.chrome?.runtime?.id!=='fixture')throw Error('V2_OFFLINE_ONLY');
    const original=globalThis.FreightDeskWebBridge,W=globalThis.FreightDeskWorkspace,S=globalThis.FreightDeskMappingScope;
    const vocabulary=[...new Set([...S.sections,...Object.keys(S.fields),...S.actions])];
    async function mapWorkspace(doc,allowed,check,progress,started,command) {
      check();
      // The existing collector supplies monotonic stage receipts and provider diagnostics.
      // V2 adds a mandatory graph/proof gate before any persistence, not a second stage sequence.
      const legacy=await W.capture(doc,allowed,check,progress,started,command);
      const before=W.observeWorkspace(doc,allowed,Date.now()/1000,check);
      const section=W.observeSection(before),documentBinding={...globalThis.__freightdeskX1Document};
      const stop=(predicate,stage,bound=null)=>{
        const error=Error('WORKSPACE_SECTION_UNVERIFIED');
        error.section_diagnostic={...section.diagnostic,v2_diagnostic:{schema_version:2,stage,predicate,
          bound_category:bound?.category||null,measured:bound?Math.ceil(bound.measured):null,maximum:bound?.maximum??null}};
        throw error;
      };
      const harness=FreightDeskWebBridgeV2.createOfflineHarness({mode:'OFFLINE',origin:'https://ascendtms.com',
        vocabulary,sections:S.sections,stateClasses:['active','selected'],limits:{payloadBytes:32000},
        readProof(){
          check();
          if(globalThis.__freightdeskX1Document.id!==documentBinding.id||globalThis.__freightdeskX1Document.generation!==documentBinding.generation)throw Error('DOCUMENT_CHANGED');
          return {schemaVersion:2,document:doc,root:before.shell,epoch:documentBinding.id,realm:String(documentBinding.generation),
            leaseRef:'lease-'+Math.trunc(command.lease_expires_at*1000),sessionRef:'dispatch-'+command.request_id,
            provider:'AscendTMS',entityType:'LOAD',entityId:before.contract.load_id,identityVerified:true,
            ownerPresent:doc.hasFocus(),foreground:doc.visibilityState==='visible',sessionVerified:true,leaseValid:true,revoked:false};
        }});
      try {
        const captured=await harness.capture(command.request_id);
        if(captured.status!=='CAPTURED')stop(captured.error_code,captured.last_completed_stage,captured.bound);
        const proof=harness.section(captured.graph);
        if(proof.status!=='VERIFIED')stop(proof.failed_predicate,'RELATIONSHIPS_RESOLVED');
        if(proof.section!==section.name||harness.resolveNode(captured.graph,proof.root)!==section.root)
          stop('COMPATIBILITY_ROOT_MISMATCH','SECTION_VERIFIED');
        // Reuse the audited V1 metadata collector and its fresh identity/section/drift checks.
        const after=W.observeWorkspace(doc,allowed,Date.now()/1000,check),current=W.observeSection(after);
        if(after.shell!==before.shell||after.contract.load_id!==before.contract.load_id||current.root!==section.root||current.name!==section.name)
          throw Error('WORKSPACE_CHANGED');
        const output={...legacy,webbridge_v2:{compatibility_version:2,graph:captured.graph,section:proof}};
        if(new TextEncoder().encode(JSON.stringify(output)).length>45000)throw Error('MAPPING_PAYLOAD_BOUND');
        check();return output;
      } finally {harness.close();}
    }
    globalThis.FreightDeskWebBridge=Object.freeze({...original,BrowserSensor:Object.freeze({...original.BrowserSensor,mapWorkspace})});
  }});
})();
