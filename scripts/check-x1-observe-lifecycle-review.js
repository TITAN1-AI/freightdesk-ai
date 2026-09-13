'use strict';
// Desired-behavior lifecycle regression, converted from the workflow-review defect reproduction.
// Real worker + router + content, synthetic Chrome ports / reader / host only.
// Reads packaged source files; no browser, networking, runtime files or provider data.
// Exercises same-document refresh, focus readiness, document replacement and signed job wake.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');

const event = () => ({
  listeners: [],
  addListener(callback) { this.listeners.push(callback); },
  removeListener(callback) { this.listeners = this.listeners.filter(item => item !== callback); },
  emit(...args) { for (const callback of [...this.listeners]) callback(...args); },
});

async function review() {
  const onConnect = event(), observers = [], focus = event(), timers = new Set();
  let worker, queued = true, operation = null, maps = 0, probes = 0;
  let now = Date.now(), nextDue = 0, connections = 0, ownerFocused = false, ownerReady = false, wakeHints = 0, leaseRevision = 1;
  let loadId = '1763', injectNotification = null;
  const traces = [];
  const schedule = (callback, milliseconds) => {
    const timer = setTimeout(() => { timers.delete(timer); callback(); }, milliseconds === 2000 ? 5 : milliseconds);
    timers.add(timer);
    return timer;
  };
  const clear = timer => { clearTimeout(timer); timers.delete(timer); };
  class FixtureDate extends Date { static now() { return now; } }
  const tab = {id: 1, url: 'https://ascendtms.com/loads', status: 'complete'};
  const shell = {parentElement: {}};
  const tabs = {
    onUpdated: event(), onRemoved: event(), onCreated: event(), onActivated: event(),
    async query() { return [tab]; },
    async get() { return tab; },
    connect() {
      connections++;
      const workerPort = {onMessage: event(), onDisconnect: event()};
      const contentPort = {
        name: 'freightdesk-x1-identity', sender: {id: 'fixture'},
        onMessage: event(), onDisconnect: event(),
      };
      let disconnected = false;
      workerPort.postMessage = message => queueMicrotask(() => contentPort.onMessage.emit(message));
      contentPort.postMessage = message => queueMicrotask(() => workerPort.onMessage.emit(message));
      workerPort.disconnect = contentPort.disconnect = () => {
        if (disconnected) return;
        disconnected = true;
        // Chrome delivers port-disconnect asynchronously; late old-port events must not cancel the replacement.
        queueMicrotask(() => { workerPort.onDisconnect.emit(); contentPort.onDisconnect.emit(); });
      };
      queueMicrotask(() => onConnect.emit(contentPort));
      return workerPort;
    },
  };
  const context = {
    URL, Date: FixtureDate, crypto: webcrypto, TextEncoder,
    setTimeout: schedule, clearTimeout: clear,
    location: {origin: 'https://ascendtms.com', pathname: '/loads'},
    document: {visibilityState: 'visible', hasFocus() { return ownerFocused; }},
    addEventListener(name, callback) { if (name === 'focus') focus.addListener(callback); },
    removeEventListener(name, callback) { if (name === 'focus') focus.removeListener(callback); },
    MutationObserver: class {
      constructor(callback) { this.callback = callback; this.active = false; observers.push(this); }
      observe() { this.active = true; }
      disconnect() { this.active = false; }
    },
    chrome: {runtime: {
      id: 'fixture', onConnect, onMessage: event(),
      getManifest() { return {version: context.FreightDeskBuild.extension_version}; },
    }},
  };
  vm.createContext(context);
  const load = name => vm.runInContext(
    fs.readFileSync('extensions/ascend-x1/' + name, 'utf8'), context, {filename: name},
  );
  for (const name of ['build.js', 'contract.js', 'read-errors.js', 'tab-router.js', 'runtime.js']) load(name);
  context.FreightDeskWorkspace = {
    readerRevision: 2,
    observeWorkspace() { return {shell, contract: {load_id: loadId}}; },
    observeSection() { return {name: 'Load Basics'}; },
  };
  context.FreightDeskX1Reader = {
    async create() {
      return {async executeRuntime(command) {
        return command.operation === 'ASCEND_MAP_WORKSPACE'
          ? {workspace: {load_id: loadId}, section: {section: 'Load Basics'}}
          : {session: true};
      }};
    },
  };
  load('content.js');
  const status = () => ({kind: 'RUNTIME_STATUS', status: {
    build: context.FreightDeskBuild, control_revision: leaseRevision,
    state: ownerReady ? 'MAPPING_READY' : 'WAITING_FOR_OWNER_WORKSPACE', lease_expires_at: now / 1000 + 600, read_access: 'ENABLED', session: 'AUTHENTICATED',
    paused: false, error_code: null, mapping_orchestrated: true,
    mapping_scope: 'NORMAL_OWNER_PRESENT', mapping_operation_mode: 'OBSERVE',
    mapping_capture_requested: queued, next_due_at: nextDue,
  }});
  const respond = message => queueMicrotask(() => worker.accept(message));
  async function send(body) {
    if (injectNotification) {
      const notification = injectNotification;
      injectNotification = null;
      await worker.accept(notification);
    }
    if (body.kind === 'RUNTIME_CAUSAL_TRACE') {
      traces.push(body.trace);
      return respond({kind: 'RUNTIME_CAUSAL_TRACE_ACK'});
    }
    if (['RUNTIME_CAPTURE_ACK', 'RUNTIME_MAPPING_PROGRESS'].includes(body.kind)) {
      return respond({kind: 'RUNTIME_MAPPING_PROGRESS_ACK'});
    }
    if (body.kind === 'RUNTIME_RESULT') {
      assert.equal(body.error_code, null);
      if (operation === 'ASCEND_MAP_WORKSPACE') {
        maps++;
        queued = false;
        nextDue = now / 1000 + 60;
      } else probes++;
      return respond(status());
    }
    assert.equal(body.kind, 'RUNTIME_WAKE');
    if (!body.route) {
      if (body.routing_state === 'WAITING_FOR_OWNER_WORKSPACE') ownerReady = false;
      return respond(status());
    }
    ownerReady = body.owner_present === true;
    if (!ownerReady) return respond(status());
    if (body.mapping_hint) { queued = true; nextDue = 0; }
    const next = body.probe_only ? 'ASCEND_GET_SESSION_STATE' : queued ? 'ASCEND_MAP_WORKSPACE' : null;
    if (!next) {
      nextDue = now / 1000 + 60;
      return respond(status());
    }
    operation = next;
    respond({
      kind: 'RUNTIME_DISPATCH', route: body.route, deadline: now / 1000 + 12,
      command: {
        version: 1, request_id: webcrypto.randomUUID().replaceAll('-', ''), operation: next,
        tenant_id: 'booking-logistics', actor: 'FreightDesk/Avery',
        load_id: null, expected_revision: null,
        ...(next === 'ASCEND_MAP_WORKSPACE' ? {
          approved_load_ids: null, owner_present: true, lease_expires_at: now / 1000 + 600,
        } : {}),
      },
    });
  }
  const observation = () => ({
    connections, active_observers: observers.filter(item => item.active).length, maps, probes,
  });
  try {
    worker = context.FreightDeskRuntime.create(tabs, () => true, send, () => { wakeHints++; });
    await worker.wake();
    assert.equal(maps, 0);
    assert.equal(probes, 0);
    assert.equal(worker.status().state, 'WAITING_FOR_OWNER_WORKSPACE');
    assert.equal(connections, 1);
    ownerFocused = true;
    focus.emit();
    await new Promise(resolve => setTimeout(resolve, 10));
    assert(wakeHints > 0, 'Foreground event must immediately wake the existing paired worker.');
    await worker.wake();
    const before = observation();
    assert.deepEqual(before, {connections: 1, active_observers: 1, maps: 1, probes: 1});
    now += 61000;
    await worker.wake();
    const after = observation();
    assert.deepEqual(after, {connections: 1, active_observers: 1, maps: 1, probes: 2});
    loadId = '1769';
    observers.find(item => item.active).callback();
    await new Promise(resolve => setTimeout(resolve, 10));
    await worker.wake();
    assert.equal(maps, 2, 'The preserved observer must capture the next owner-opened workspace.');
    assert.equal(connections, 1);
    // Losing foreground waits without consuming a capture, then resumes on the private focus event.
    ownerFocused = false;
    now += 61000;
    const probesBeforeWait = probes;
    await worker.wake();
    assert.equal(probes, probesBeforeWait);
    assert.equal(worker.status().state, 'WAITING_FOR_OWNER_WORKSPACE');
    assert.equal(observation().active_observers, 1);
    ownerFocused = true;
    focus.emit();
    await new Promise(resolve => setTimeout(resolve, 10));
    await worker.wake();
    assert.equal(maps, 3);
    // Real document replacement invalidates the old private channel, but the navigation hint survives.
    tab.status = 'loading';
    tabs.onUpdated.emit(tab.id, {status: 'loading'});
    const beforeLoading = probes;
    await worker.wake();
    assert.equal(probes, beforeLoading, 'An unfinished document cannot be probed or reinjected.');
    assert.equal(connections, 1);
    assert.equal(worker.status().state, 'WAITING_FOR_OWNER_WORKSPACE');
    delete context.__freightdeskX1Document;
    loadId = '1737';
    load('content.js');
    tab.status = 'complete';
    tabs.onUpdated.emit(tab.id, {status: 'complete'});
    await worker.wake();
    assert.equal(maps, 4);
    assert.equal(connections, 2);
    assert.equal(observation().active_observers, 1);
    const beforeNotification = wakeHints, notification = {kind: 'RUNTIME_JOB_WAKE_NOTIFICATION', notification_sequence: 1, protocol: 1,
      tenant_id: 'booking-logistics', actor: 'FreightDesk/Avery', production_writes: false, state: 'PAIRED', read_dispatch_enabled: false};
    await worker.accept(notification);
    assert.equal(wakeHints, beforeNotification + 1);
    await worker.accept(notification);
    assert.equal(wakeHints, beforeNotification + 1, 'Duplicate signed wake notification must coalesce.');
    await assert.rejects(worker.accept({...notification, notification_sequence: 2, operation: 'SAVE'}));
    injectNotification = {...notification, notification_sequence: 2};
    await worker.wake();
    assert.equal(wakeHints, beforeNotification + 2, 'A notification received during RPC must schedule one immediate follow-up.');
    const beforeFollowup = probes;
    await worker.wake();
    assert.equal(probes, beforeFollowup + 1, 'The coalesced follow-up bypasses idle cadence for fresh host evaluation.');
    assert.equal(maps, 4, 'A wake notification cannot authorize a capture.');
    leaseRevision++;
    queued = true;
    nextDue = 0;
    await worker.wake();
    assert.equal(maps, 5, 'A lease-generation rebind must survive late old-port disconnect delivery.');
    assert.equal(connections, 3);
    assert.equal(observation().active_observers, 1);
    assert(traces.some(trace => trace.event === 'SESSION_PROOF_INVALIDATED' && trace.reason === 'LEASE_GENERATION_CHANGED'));
    assert(traces.some(trace => trace.event === 'SESSION_PROOF_INVALIDATED' && trace.reason === 'DOCUMENT_LOADING'));
    assert(traces.some(trace => trace.reason === 'FOCUS_LOST'));
    assert(traces.some(trace => trace.event === 'OWNER_READINESS_PROVED' && trace.document_generation === 1));
    assert(traces.some(trace => trace.event === 'CONTENT_PORT_PRESENT' && trace.content_trace_revision === 1 && trace.mapping_reader_revision === 2));
    assert(traces.every(trace => trace.trace_revision === 1 && /^[a-f0-9]{32}$/.test(trace.worker_instance)));
    assert(traces.every(trace => Object.keys(trace).every(key => ['trace_revision','content_trace_revision','mapping_reader_revision','event','reason','tab_id','document_id','document_generation','worker_instance'].includes(key))));
    process.stdout.write(JSON.stringify({
      regression: 'OBSERVE_LIFECYCLE_READINESS_AND_WAKE',
      result: 'PASSED', product_validation_passed: true,
      before, after, browser_execution: false, networking: false, runtime_files_written: false,
    }) + '\n');
  } finally {
    for (const timer of timers) clear(timer);
  }
}

review().catch(error => {
  process.stderr.write(String(error.stack) + '\n');
  process.stderr.write('OBSERVE lifecycle readiness regression failed.\n');
  process.exitCode = 1;
});
