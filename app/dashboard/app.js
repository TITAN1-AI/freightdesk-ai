"use strict";
const $ = (id) => document.getElementById(id);
let state;
let selected = null;
const esc = (v) => String(v ?? "Not available").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const human = (v) => String(v).replaceAll("_", " ");
const date = (v) => v ? new Date(v).toLocaleString([], {timeZone: state?.timezone || "America/Guatemala", month:"short", day:"numeric", hour:"2-digit", minute:"2-digit"}) : "Not available";
const age = (v) => v ? Math.max(0, Math.floor((Date.now()-new Date(v))/60000)) + " min ago" : "No position";
const badge = (v) => '<span class="badge '+esc(v.toLowerCase())+'">'+esc(human(v))+'</span>';
async function api(path, body) {
  const result = await fetch(path, {method: body ? "POST" : "GET",
    headers: {"Content-Type":"application/json", "X-FreightDesk-Local":"1"}, ...(body ? {body:JSON.stringify(body)}:{})});
  const value = await result.json();
  if (!result.ok) throw new Error(typeof value.detail === "string" ? value.detail : "Invalid request");
  return value;
}
function showError(error) { $("error").hidden=false; $("error").textContent=error.message; if(selected) $("detail-feedback").textContent=error.message; }
async function refresh() {
  state = await api("/api/snapshot");
  $("error").hidden = true;
  render();
}
async function act(path, body) {
  const result = await api(path, body);
  await refresh();
  return result;
}
function render() {
  $("clock").textContent=date(state.generated_at)+" · "+state.timezone;
  $("agent-status").textContent=state.agent.status;
  $("agent-status").className="badge "+state.agent.status.toLowerCase();
  $("current-task").textContent=state.agent.status==="ACTIVE" ? state.agent.current_task : "Automation paused. Owner review and read access remain available.";
  $("pause-agent").textContent=state.agent.status==="ACTIVE" ? "Pause Avery" : "Resume Avery";
  $("heartbeat").textContent="Last heartbeat: "+date(state.agent.last_heartbeat)+" · Demo scheduler";
  const m=state.metrics;
  $("agent-outcomes").textContent="Recent: "+m.completed_reviews_recent+" completed reviews · "+m.simulated_actions_recent+" simulated actions · "+m.errors_recent+" errors · "+m.escalations+" exceptions · "+m.retries+" retries";
  $("agent-metrics").innerHTML=[[m.queued_tasks,"queued tasks"],[m.waiting_tasks,"waiting"],[m.pending_approvals,"approvals"],[m.events_processed_today,"events today"]].map(([n,l])=>'<div><b>'+n+'</b><small>'+l+'</small></div>').join("");
  const s=state.summary;
  $("summary").innerHTML=[[s.active_loads,"Active loads","",s.pickups_today+" pickups today"],[s.healthy,"Healthy","good","No routine outreach"],[s.warning,"Warning","","Needs a review"],[s.at_risk,"At risk","alert","Broker attention"],[s.deliveries_today,"Deliveries today","","Local workspace time"],[s.pod_pending,"POD pending","",s.bol_missing+" BOL missing"],[s.billing_ready,"Billing ready","good",s.tracking_stale+" tracking stale"]].map(([n,l,c,d])=>'<div class="stat '+c+'"><span>'+l+'</span><b>'+n+'</b><small>'+d+'</small></div>').join("");
  renderLoads();
  const pending=state.approvals.filter(a=>a.status==="PENDING");
  $("approval-count").textContent=pending.length;
  $("approval-list").innerHTML=pending.length ? pending.map(a=>'<div class="approval-card"><strong>'+esc(a.shipment_id)+'</strong> '+badge(a.status)+'<p>'+esc(human(a.action))+'</p><p>'+esc(a.explanation)+'</p><small class="muted">Expires '+date(a.expires_at)+' · Approval simulates a draft only</small><div class="actions"><button data-decision="APPROVED" data-id="'+esc(a.id)+'">Approve demo action</button><button class="secondary" data-decision="REJECTED" data-id="'+esc(a.id)+'">Reject</button></div></div>').join("") : '<div class="empty">No pending approvals. Request a demo update from a shipment to exercise the policy engine.</div>';
  $("timeline").innerHTML=timeline(state.audit.slice(0,18));
  $("connection-list").innerHTML=state.connections.map(c=>'<article class="connection"><h3>'+esc(c.name)+'</h3>'+badge(c.status)+'<p>'+esc(c.detail)+'</p><small>IMPLEMENTED: '+(c.implemented?"YES":"NO")+' · TESTED: '+(c.tested?"YES":"NO")+' · LIVE: '+(c.name==="CarrierView"?"see historical POC scope":"NO")+'</small></article>').join("");
  if (!$("policy-action").options.length) $("policy-action").innerHTML=Object.keys(state.policies).map(a=>'<option value="'+esc(a)+'">'+esc(human(a))+'</option>').join("");
  if (!["policy-value","policy-action"].includes(document.activeElement?.id)) $("policy-value").value=state.policies[$("policy-action").value];
  $("tasks").innerHTML=state.tasks.map(t=>'<div><strong>'+esc(t.shipment_id)+'</strong> · '+esc(t.kind)+' · '+esc(t.status)+' · '+date(t.due_at)+'</div>').join("");
  if (selected) renderDetail(selected);
}
function renderLoads() {
  const filter=$("risk-filter").value;
  $("load-rows").innerHTML=state.shipments.filter(s=>filter==="ALL" || s.risk===filter).map(s=>'<tr><td><strong>'+esc(s.id)+'</strong><small>'+esc(s.customer.name)+'</small>'+(s.paused?badge("PAUSED"):"")+'</td><td>'+esc(s.origin.location)+' → '+esc(s.destination.location)+'<small>'+esc(s.carrier?.name)+'</small></td><td>'+esc(human(s.status))+'<small>'+esc(s.tracking.status)+' · '+age(s.tracking.last_position_at)+'</small></td><td>'+esc(s.tracking.location)+'<small>'+date(s.tracking.last_position_at)+'</small></td><td>'+date(s.tracking.eta)+'<small>Appt '+date(s.destination.appointment)+'</small></td><td>'+badge(s.risk)+'<small>'+esc(s.next_action)+'</small></td><td><button data-load="'+esc(s.id)+'">Open load</button>'+(state.approvals.some(a=>a.shipment_id===s.id&&a.status==="PENDING")?'<small>Approval pending</small>':'')+'</td></tr>').join("") || '<tr><td colspan="7">No matching loads.</td></tr>';
}
function timeline(events) {
  return events.length ? events.map(e=>'<div class="timeline-item"><small>'+date(e.timestamp)+' · '+esc(e.shipment_id || "Avery")+'</small><strong>'+esc(human(e.event))+'</strong><p>'+esc(e.explanation)+'</p><details><summary>Decision record</summary><pre>'+esc(JSON.stringify(e,null,2))+'</pre></details></div>').join("") : '<p class="empty">No recorded activity.</p>';
}
function renderDetail(id) {
  const s=state.shipments.find(s=>s.id===id);
  if (!s) return;
  $("detail-title").textContent=id+" · "+s.origin.location+" → "+s.destination.location;
  const dl = (pairs) => "<dl>"+pairs.map(([k,v])=>"<dt>"+esc(k)+"</dt><dd>"+esc(v)+"</dd>").join("")+"</dl>";
  $("detail-body").innerHTML='<p>'+badge(s.risk)+' '+esc(s.risk_explanation)+'</p><div class="detail-actions"><button data-update="'+esc(id)+'">Prepare demo customer update</button><button class="secondary" data-load-pause="'+esc(id)+'">'+(s.paused?"Resume load":"Pause load")+'</button><button class="secondary" data-takeover="'+esc(id)+'">Take over load</button><button class="secondary" data-review="'+esc(id)+'">Review tracking</button></div><div class="detail-grid"><article><h2>Canonical shipment</h2>'+dl([["Status",s.status],["Customer",s.customer.name],["Carrier",s.carrier?.name],["Driver",s.driver?.name],["Driver phone",s.driver?.phone],["Truck / trailer",s.driver?.truck+" / "+s.driver?.trailer],["Dispatcher",s.dispatcher?.name],["Pickup",date(s.origin.appointment)],["Delivery",date(s.destination.appointment)],["Workflow",s.workflow],["Control",s.human_takeover?"Human takeover":s.paused?"Paused":"Avery"],["Version",s.version]])+'</article><article><h2>Tracking & reconciliation</h2>'+dl([["Ascend state",s.ascend_state || "Not connected"],["CarrierView state","Not connected — fixture only"],["Fixture status",s.tracking.status],["Accepted",s.tracking.accepted?"Yes (demo)":"No"],["Last position",s.tracking.location],["Freshness",age(s.tracking.last_position_at)],["ETA",date(s.tracking.eta)],["Source",s.tracking.source],["Tracking link",s.tracking.share_link || "Not available"],["Last Avery action",s.last_action],["Next action",s.next_action]])+'</article><article><h2>Documents & communications</h2>'+s.documents.map(d=>'<p>'+esc(d.kind)+' · '+(d.verified?"Verified demo fixture":"Unverified")+'</p>').join("")+'<p class="muted">Required: '+esc(s.required_documents.join(", "))+'</p><p class="muted">'+(s.communications.length?esc(s.communications.map(c=>c.summary).join("; ")):"No external communications recorded.")+'</p><h2>Exceptions</h2><p class="muted">'+(s.exceptions.length?esc(s.exceptions.map(e=>e.reason).join("; ")):"No explicit exceptions recorded; risk rules may still flag attention.")+'</p></article><article><h2>Scheduled tasks</h2>'+state.tasks.filter(t=>t.shipment_id===id).map(t=>'<p>'+esc(t.kind)+' · '+esc(t.status)+'<br><span class="muted">'+date(t.due_at)+'</span></p>').join("")+'<h2>Approvals</h2>'+state.approvals.filter(a=>a.shipment_id===id).map(a=>'<p>'+esc(human(a.action))+' · '+esc(a.status)+'</p>').join("")+'<h2>Tracking timeline</h2><p class="muted">'+s.tracking_timeline.length+' source events received (fixture-only initialization).</p></article></div><h2>Shipment activity</h2>'+timeline(state.audit.filter(a=>a.shipment_id===id).slice(0,12));
}
$("refresh").onclick=()=>refresh().catch(showError);
$("risk-filter").onchange=renderLoads;
$("pause-agent").onclick=()=>act("/api/pause",{paused:state.agent.status==="ACTIVE"}).catch(showError);
$("command-form").onsubmit=async(e)=>{e.preventDefault();try{const r=await act("/api/commands",{command:$("command").value});$("command-result").textContent=r.reply || (r.paused!==undefined ? (r.paused?"Paused":"Resumed")+" "+(r.shipment_id || "Avery") : "Demo review completed.");}catch(error){$("command-result").textContent=error.message;}};
$("policy-action").onchange=()=>{$("policy-value").value=state.policies[$("policy-action").value];};
$("policy-form").onsubmit=async(e)=>{e.preventDefault();try{await act("/api/policies",{action:$("policy-action").value,policy:$("policy-value").value});$("policy-result").textContent="Policy saved. External integrations remain disconnected.";}catch(error){showError(error);}};
$("close-detail").onclick=()=>{$("load-detail").close();selected=null;};
$("load-detail").addEventListener("close",()=>{selected=null;});
document.addEventListener("click",async(e)=>{
  const button=e.target.closest("button");
  if(!button) return;
  try {
    if(button.dataset.load){selected=button.dataset.load;$("detail-feedback").textContent="";renderDetail(selected);$("load-detail").showModal();}
    if(button.dataset.decision){button.disabled=true;const r=await act("/api/approvals/"+button.dataset.id,{decision:button.dataset.decision});if(r.status==="EXPIRED") throw new Error("Approval expired because the shipment changed or the time limit passed. Prepare a fresh update.");}
    if(button.dataset.update){button.disabled=true;const r=await act("/api/actions",{shipment_id:button.dataset.update,action:"routine_customer_update",request_id:crypto.randomUUID()});$("detail-feedback").textContent=r.status==="APPROVAL_REQUIRED"?"Demo update added to the approval queue.":r.status==="FORBIDDEN"?"Action forbidden by current policy.":"Demo update simulated. No message was sent.";}
    if(button.dataset.loadPause){const s=state.shipments.find(s=>s.id===button.dataset.loadPause);await act("/api/pause",{shipment_id:s.id,paused:!s.paused});}
    if(button.dataset.takeover) await act("/api/pause",{shipment_id:button.dataset.takeover,paused:true,takeover:true});
    if(button.dataset.review) await act("/api/commands",{command:"review "+button.dataset.review});
  }catch(error){showError(error);}finally{button.disabled=false;}
});
(async()=>{try{await api("/api/session",{});await refresh();setInterval(()=>{if(!document.hidden)refresh().catch(showError);},30000);}catch(error){showError(error);}})();
