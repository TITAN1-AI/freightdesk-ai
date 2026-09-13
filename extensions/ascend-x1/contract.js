(() => {
  'use strict';
  const operations=Object.freeze(['ASCEND_GET_SESSION_STATE','ASCEND_GET_ACTIVE_LOADS','ASCEND_FIND_LOAD',
    'ASCEND_OPEN_LOAD_READONLY','ASCEND_READ_LOAD','ASCEND_READ_STOPS','ASCEND_READ_ASSIGNMENT']);
  const runtimeOperations=Object.freeze([...operations,'ASCEND_NAVIGATE_ACTIVE_LOADS','ASCEND_DISCOVER_DETAIL_CONTRACT','ASCEND_MAP_WORKSPACE','ASCEND_MAP_NAVIGATE_SECTION']);
  const check=(c,allowed)=>{
    const keys=['version','request_id','operation','load_id','tenant_id','actor','expected_revision'];
    if(['ASCEND_MAP_WORKSPACE','ASCEND_MAP_NAVIGATE_SECTION'].includes(c?.operation))keys.push('approved_load_ids','owner_present','lease_expires_at');
    if(['ASCEND_MAP_WORKSPACE','ASCEND_MAP_NAVIGATE_SECTION'].includes(c?.operation))for(const k of ['capture_load_id','capture_section'])if(k in c)keys.push(k);
    if(c?.operation==='ASCEND_MAP_NAVIGATE_SECTION')keys.push('navigation','expected_from_section','return_to_start');
    if(!c||typeof c!=='object'||Object.keys(c).sort().join()!==keys.sort().join()||c.version!==1||
      !allowed.includes(c.operation)||c.tenant_id!=='booking-logistics'||c.actor!=='FreightDesk/Avery'||
      typeof c.request_id!=='string'||c.request_id.length!==32||!/^[a-f0-9]{32}$/.test(c.request_id)||
      !(c.expected_revision===null||typeof c.expected_revision==='string'&&c.expected_revision.length===64&&/^[a-f0-9]{64}$/.test(c.expected_revision)))
      throw Error('invalid_read_command');
    if(['ASCEND_MAP_WORKSPACE','ASCEND_MAP_NAVIGATE_SECTION'].includes(c.operation)&&(!(c.approved_load_ids===null||Array.isArray(c.approved_load_ids)&&c.approved_load_ids.length>=1&&c.approved_load_ids.length<=20&&
      new Set(c.approved_load_ids).size===c.approved_load_ids.length&&c.approved_load_ids.every(id=>typeof id==='string'&&/^[0-9]{1,20}$/.test(id)))||typeof c.owner_present!=='boolean'||
      typeof c.lease_expires_at!=='number'||!Number.isFinite(c.lease_expires_at)||c.lease_expires_at<0))throw Error('invalid_load_scope');
    if(c.capture_load_id!=null||c.capture_section!=null){if(c.operation!=='ASCEND_MAP_WORKSPACE'||!c.approved_load_ids?.includes(c.capture_load_id)||c.capture_section!=null&&c.capture_section!=='Load Basics')throw Error('invalid_load_scope');}
    if(c.operation==='ASCEND_MAP_NAVIGATE_SECTION'){
      const n=c.navigation,v=n?.candidate;
      if(c.expected_revision!==null||typeof c.load_id!=='string'||!/^[0-9]{1,20}$/.test(c.load_id)||typeof c.expected_from_section!=='string'||c.expected_from_section.length>64||typeof c.return_to_start!=='boolean'||
        !n||Object.keys(n).sort().join()!=='candidate,classification,confidence,evidence_map_version,review_source,workspace_fingerprint'||
        n.classification!=='READ_ONLY_NAVIGATION'||n.confidence!=='VERIFIED'||n.review_source!=='OWNER_REVIEWED_PROVIDER_NAVIGATION'||!/^[a-f0-9]{64}$/.test(n.workspace_fingerprint)||!Number.isInteger(n.evidence_map_version)||n.evidence_map_version<1||
        !v||Object.keys(v).sort().join()!=='control_type,fingerprint,reference,relative_path,role,same_document_target,section,tag,target_relative_path'||
        !['button','a'].includes(v.tag)||v.role!=='tab'||!['button','anchor'].includes(v.control_type)||!['ARIA_CONTROLS','FRAGMENT','DATA_TARGET','LABELLEDBY'].includes(v.reference)||
        typeof v.section!=='string'||v.section.length>64||v.same_document_target!==true||!/^[a-f0-9]{64}$/.test(v.fingerprint)||!Array.isArray(v.relative_path)||v.relative_path.length>12||v.relative_path.some(i=>!Number.isInteger(i)||i<0||i>10000)||!Array.isArray(v.target_relative_path)||v.target_relative_path.length>12||v.target_relative_path.some(i=>!Number.isInteger(i)||i<0||i>10000))throw Error('NAVIGATION_CONTRACT_UNVERIFIED');
      return c;
    }
    const load= !['ASCEND_GET_SESSION_STATE','ASCEND_GET_ACTIVE_LOADS','ASCEND_NAVIGATE_ACTIVE_LOADS','ASCEND_MAP_WORKSPACE'].includes(c.operation);
    if(load?typeof c.load_id!=='string'||c.load_id.length>20||!/^[0-9]{1,20}$/.test(c.load_id):c.load_id!==null) throw Error('invalid_load_scope');
    if(load&&c.expected_revision===null) throw Error('board_revision_required');
    if(!load&&c.expected_revision!==null)throw Error('invalid_load_scope');
    return c;
  };
  globalThis.FreightDeskX1Contract=Object.freeze({operations,runtimeOperations,validate:c=>check(c,operations),
    validateRuntime:c=>check(c,runtimeOperations),origin:'https://ascendtms.com'});
})();
