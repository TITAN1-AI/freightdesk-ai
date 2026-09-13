/* Offline Chrome API/native-pipe boundary. Production worker/router/content/reader stay real. */
(() => {
  const event=()=>({listeners:[],addListener(f){this.listeners.push(f);},removeListener(f){this.listeners=this.listeners.filter(v=>v!==f);},emit(...args){for(const f of [...this.listeners])f(...args);}});
  const connect=event(),windowsFocus=event();
  let focused=false,connections=0,worker=null,pairing=null,wire=Promise.resolve(),incoming=Promise.resolve(),wakes=Promise.resolve();
  const errors=[],operations=[],observers=new Set(),nativeObserver=MutationObserver,nativeDate=Date;
  let offset=0;
  globalThis.Date=class extends nativeDate {static now(){return nativeDate.now()+offset*1000;}};
  Object.defineProperty(document,'hasFocus',{value:()=>focused});
  globalThis.MutationObserver=class extends nativeObserver {
    observe(...args){observers.add(this);return super.observe(...args);}
    disconnect(){observers.delete(this);return super.disconnect();}
  };
  const tab={id:7,url:'https://ascendtms.com/loads',status:'complete'};
  const tabs={onUpdated:event(),onRemoved:event(),onCreated:event(),onActivated:event(),
    async query(query){return query?.active&&!focused?[{id:8,url:'http://localhost:8787'}]:[{...tab}];},
    async get(id){if(id!==7)throw Error('FIXTURE_TAB');return {...tab};},
    connect(){
      connections++;
      const a={onMessage:event(),onDisconnect:event()},b={name:'freightdesk-x1-identity',sender:{id:'fixture'},onMessage:event(),onDisconnect:event()};
      let closed=false;
      a.postMessage=m=>queueMicrotask(()=>{if(!closed)b.onMessage.emit(structuredClone(m));});
      b.postMessage=m=>queueMicrotask(()=>{if(!closed)a.onMessage.emit(structuredClone(m));});
      a.disconnect=b.disconnect=()=>{if(closed)return;closed=true;a.onDisconnect.emit();b.onDisconnect.emit();};
      queueMicrotask(()=>connect.emit(b));return a;
    }};
  globalThis.chrome={tabs,windows:{onFocusChanged:windowsFocus},runtime:{id:'fixture',onConnect:connect,onMessage:event(),
    getManifest:()=>({version:FreightDeskBuild.extension_version})}};
  const enqueueWake=()=>{wakes=wakes.then(()=>worker.wake()).catch(()=>errors.push('WORKER_WAKE_FAILED'));};
  const receive=message=>{
    incoming=incoming.then(async()=>{
      const body=await FreightDeskPairing.verify(pairing,message.envelope);
      if(body.kind==='RUNTIME_DISPATCH')operations.push(body.command.operation);
      await worker.accept(body);
    }).catch(()=>errors.push('NATIVE_RECEIPT_FAILED'));
    return incoming;
  };
  const send=body=>{
    wire=wire.then(async()=>{
      const envelope=await FreightDeskPairing.sign(pairing,body);
      const response=await globalThis.fixtureHostWire({kind:'AUTHENTICATED',protocol:1,envelope});
      await receive(response);
    });return wire;
  };
  globalThis.x1Chain={
    async init(auth){
      const key=await crypto.subtle.importKey('raw',Uint8Array.from(auth.key.match(/../g),v=>parseInt(v,16)),{name:'HMAC',hash:'SHA-256'},false,['sign','verify']);
      pairing={key,session:auth.session,incoming:auth.incoming,outgoing:0,expires:auth.expires};
      worker=FreightDeskRuntime.create(tabs,()=>true,send,enqueueWake);
    },
    receive,
    async flush(){for(let i=0;i<20;i++){const current=wakes;await current;await wire;await incoming;if(current===wakes)break;}},
    wake(){enqueueWake();},
    focus(value){focused=value;windowsFocus.emit(value?1:-1);dispatchEvent(new Event(value?'focus':'blur'));},
    advance(seconds){offset+=seconds;},
    replaceDocument(){tab.status='loading';tabs.onUpdated.emit(7,{status:'loading'});globalThis.__freightdeskX1Registration?.dispose();delete globalThis.__freightdeskX1Document;},
    documentReady(){tab.status='complete';tabs.onUpdated.emit(7,{status:'complete'});},
    summary(){return {connections,active_observers:observers.size,operations:[...operations],errors:[...errors],worker:worker.status()};},
    close(){worker.reset();globalThis.__freightdeskX1Registration?.dispose();},
  };
})();
