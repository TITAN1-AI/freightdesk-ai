(() => {
  'use strict';
  const handle=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);
  async function importEnrollment(bundle,extensionId){
    if(bundle?.purpose!=='X1_ENROLLMENT')throw Error('PAIRING_SCHEMA_INVALID');
    const {purpose,...bootstrap}=bundle;
    const pairing=await FreightDeskPairing.importBundle(bootstrap,extensionId);
    return {...pairing,enrollment:true};
  }
  async function resume(message,enrollmentHandle,extensionId){
    const c=message?.challenge;
    if(message?.kind!=='RESUME_CHALLENGE'||message.protocol!==1||!handle(enrollmentHandle)||
      typeof message.session_key!=='string'||!/^[a-f0-9]{64}$/.test(message.session_key)||
      !c||c.protocol!==1||c.enrollment_handle!==enrollmentHandle||!handle(c.installation_id)||!handle(c.session_id)||
      c.extension_origin!==`chrome-extension://${extensionId}/`||c.tenant_id!=='booking-logistics'||c.actor!=='FreightDesk/Avery')
      throw Error('PAIRING_BINDING_MISMATCH');
    const key=await crypto.subtle.importKey('raw',Uint8Array.from(message.session_key.match(/../g),x=>parseInt(x,16)),
      {name:'HMAC',hash:'SHA-256'},false,['sign','verify']);
    return {key,extensionId,installation:c.installation_id,generation:c.generation,expires:Math.floor(Date.now()/1000)+600,
      session:null,incoming:0,outgoing:0,enrollment:true,enrollmentHandle};
  }
  // Only this opaque identifier is durable in Edge. Keys and challenges remain worker memory only.
  async function load(storage){const value=(await storage.get('x1Enrollment'))?.x1Enrollment;return handle(value)?value:null;}
  async function save(storage,value){if(!handle(value))throw Error('PAIRING_ACK_INVALID');await storage.set({x1Enrollment:value});}
  globalThis.FreightDeskEnrollment=Object.freeze({importEnrollment,resume,load,save,validHandle:handle});
})();
