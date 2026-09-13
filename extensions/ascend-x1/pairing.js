(() => {
  'use strict';
  const canonical=value=>JSON.stringify((function sorted(v){
    if(Array.isArray(v))return v.map(sorted);
    if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])]));
    return v;
  })(value)).replace(/[^\x00-\x7f]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
  const hex=b=>[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('');
  const unhex=s=>Uint8Array.from(s.match(/../g)||[],v=>parseInt(v,16));
  async function mac(key,value){return hex(await crypto.subtle.sign('HMAC',key,new TextEncoder().encode(canonical(value))));}
  function validateBundle(bundle,extensionId){
    if(!bundle||Object.keys(bundle).sort().join()!==['extension_id','installation_id','protocol','tenant_id','actor','generation','key','expires_at'].sort().join()||
      typeof bundle.extension_id!=='string'||!/^[a-p]{32}$/.test(bundle.extension_id)||bundle.extension_id.length!==32||bundle.protocol!==1||
      bundle.tenant_id!=='booking-logistics'||bundle.actor!=='FreightDesk/Avery'||!/^[a-f0-9]{64}$/.test(bundle.key)||
      typeof bundle.key!=='string'||bundle.key.length!==64||
      !/^[a-f0-9]{32}$/.test(bundle.installation_id)||!/^[a-f0-9]{32}$/.test(bundle.generation)||
      !Number.isInteger(bundle.expires_at)||bundle.expires_at*1000>Date.now()+601000)
      throw Error('PAIRING_SCHEMA_INVALID');
    if(bundle.extension_id!==extensionId)throw Error('EXTENSION_ID_MISMATCH');
    if(bundle.expires_at*1000<=Date.now())throw Error('PAIRING_EXPIRED');
  }
  async function importBundle(bundle,extensionId){
    validateBundle(bundle,extensionId);
    const key=await crypto.subtle.importKey('raw',unhex(bundle.key),{name:'HMAC',hash:'SHA-256'},false,['sign','verify']);
    return {key,extensionId,installation:bundle.installation_id,generation:bundle.generation,expires:bundle.expires_at,
      session:null,incoming:0,outgoing:0};
  }
  async function proof(pairing,challenge){
    if(pairing.session||pairing.expires*1000<=Date.now()||challenge.protocol!==1||challenge.installation_id!==pairing.installation||challenge.generation!==pairing.generation||
      challenge.extension_origin!==`chrome-extension://${pairing.extensionId}/`||challenge.tenant_id!=='booking-logistics'||
      challenge.actor!=='FreightDesk/Avery'||!/^[a-f0-9]{32}$/.test(challenge.session_id))throw Error('host_binding_invalid');
    pairing.session=challenge.session_id;
    return mac(pairing.key,{session_id:challenge.session_id,extension_origin:challenge.extension_origin,
      tenant_id:challenge.tenant_id,actor:challenge.actor});
  }
  async function verify(pairing,message){
    if(!message||Object.keys(message).sort().join()!==['session_id','sequence','body','mac','direction'].sort().join()||
      message.session_id!==pairing.session||message.direction!=='host_to_extension'||message.sequence!==pairing.incoming+1||
      !/^[a-f0-9]{64}$/.test(message.mac)||pairing.expires*1000<=Date.now())throw Error('host_authentication_failed');
    const signed={session_id:message.session_id,sequence:message.sequence,body:message.body,direction:message.direction};
    if(!await crypto.subtle.verify('HMAC',pairing.key,unhex(message.mac),new TextEncoder().encode(canonical(signed))))throw Error('host_authentication_failed');
    pairing.incoming=message.sequence;
    return message.body;
  }
  async function sign(pairing,body){
    if(!pairing.session||pairing.expires*1000<=Date.now())throw Error('stale_pairing');
    const signed={session_id:pairing.session,sequence:++pairing.outgoing,body,direction:'extension_to_host'};
    return {...signed,mac:await mac(pairing.key,signed)};
  }
  globalThis.FreightDeskPairing=Object.freeze({canonical,validateBundle,importBundle,proof,verify,sign});
})();
