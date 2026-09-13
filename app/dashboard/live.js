"use strict";
function liveRecordHtml(record) {
  const safe = value => String(value ?? "Unknown / not provided").replace(/[&<>"']/g,
    char => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[char]));
  const time = value => value || "Unknown / not provided";
  if (record.historical) {
    const facts = record.provider_facts, derived = record.derived;
    const definitions = rows => "<dl>" + rows.map(([k,v]) =>
      "<dt>"+safe(k)+"</dt><dd>"+safe(v)+"</dd>").join("")+"</dl>";
    const local = value => value ? value.replace("T"," ").replace(/:00-05:00$/, " CDT").replace("-05:00"," CDT") : null;
    return '<h2>'+safe(record.title)+'</h2><p class="muted">Owner-reconciled historical snapshot · '+
      'Read only · Automated actions disabled</p><div class="detail-grid"><article><h2>CarrierView facts</h2>'+
      definitions([["Booking load ID",record.booking_load_id],["CarrierView provider ID",record.provider_id],
        ["Read credential class",record.credential_class],["Provider app status",facts.app_status],
        ["Delivery arrived",facts.delivery_arrived],["Delivery departed",facts.delivery_departed],
        ["Time remaining (seconds)",facts.time_left_sec],["Distance remaining (meters)",facts.distance_left_meters],
        ["Last-position record returned",facts.last_position_returned],
        ["GPS history received",facts.history_records_received+" of "+facts.history_pagination.total+" records"],
        ["GPS history scope","First page only; full replay not validated"],["Snapshot captured",facts.last_sync_at]])+
      '</article><article><h2>FreightDesk-derived assessments</h2>'+
      definitions([["Canonical status",derived.canonical_status],["Historical arrival assessment",derived.arrival_assessment],
        ["Review classification",derived.risk],["Classification basis",derived.risk_explanation],
        ["Billing readiness",derived.billing_readiness],["Numeric GPS timestamp units",derived.numeric_timestamp_units]])+
      '<p class="muted">DELIVERED maps the reconciled provider delivery flags. It does not verify POD, signed RC, or billing readiness.</p>'+
      '</article></div><h2>Owner-reconciled stop timeline</h2><div class="table-scroll"><table><thead><tr>'+
      '<th>Stop</th><th>Appointment window</th><th>Arrival</th><th>Departure</th><th>Derived arrival assessment</th>'+
      '</tr></thead><tbody>'+record.stops.map(stop=>"<tr><td>"+safe(stop.kind==="destination"?"Delivery":"Pickup")+
        "</td><td>"+safe(local(stop.appointment_start))+" — "+safe(local(stop.appointment_end))+
        "</td><td>"+safe(local(stop.arrived_at))+"</td><td>"+safe(local(stop.departed_at))+
        "</td><td>"+safe(stop.arrival_vs_window)+"</td></tr>").join("")+
      '</tbody></table></div><h2>LIVE_VALIDATED capability scope</h2><div class="table-scroll"><table><thead>'+
      '<tr><th>Capability</th><th>LIVE_VALIDATED</th></tr></thead><tbody>'+
      Object.entries(record.capability_matrix).map(([key,value])=>"<tr><td>"+safe(key)+"</td><td>"+
        (value?"YES — historical scope":"NO")+"</td></tr>").join("")+'</tbody></table></div>';
  }
  const freshness = value => value ? Math.floor((Date.now()-new Date(value).getTime())/60000)+" minutes" : null;
  const rows = [
    ["Booking load ID",record.booking_load_id], ["CarrierView provider ID",record.provider_id],
    ["Shipment status",record.status], ["Tracking state",record.tracking_status], ["App status",record.app_status],
    ["Tracking age",freshness(record.last_position_at)], ["Last position timestamp",time(record.last_position_at)],
    ["City / state",record.current_city_state], ["ETA",time(record.eta)],
    ["Time remaining (seconds)",record.time_left_sec], ["Distance remaining (meters)",record.distance_left_meters],
    ["Late flag",record.driver_is_late], ["Delivery arrived",record.delivery_arrived],
    ["Delivery departed",record.delivery_departed], ["Risk",record.risk], ["Risk explanation",record.risk_explanation],
    ["Last CarrierView sync",time(record.last_sync_at)], ["Read credential class",record.credential_class],
  ];
  return '<div class="detail-grid"><article><h2>Verified source facts</h2><dl>'+
    rows.map(([key,value])=>"<dt>"+safe(key)+"</dt><dd>"+safe(value)+"</dd>").join("")+
    '</dl></article><article><h2>Pickup / delivery stop state</h2><pre>'+
    safe(record.stops === null || record.stops === undefined ? null : JSON.stringify(record.stops,null,2))+
    '</pre><p class="muted">Unknown values stay unknown. CarrierView documents/POD API capability is not established.</p></article></div>';
}
if (typeof module !== "undefined") module.exports = {liveRecordHtml};
if (typeof document !== "undefined") {
  async function showLive(headers={}) {
    const response=await fetch("/api/carrierview/poc",{headers});
    if (!response.ok) return false;
    const result=await response.json();
    if (!result.imported) return false;
    document.getElementById("live-badge").textContent="LIVE · HISTORICAL";
    document.getElementById("live-badge").className="badge active";
    document.getElementById("live-record").innerHTML=liveRecordHtml(result.shipment);
    document.dispatchEvent(new Event("freightdesk-live-ready"));
    document.getElementById("live-message").textContent="Owner reconciliation recorded. LIVE_VALIDATED applies only to the capabilities listed below.";
    return true;
  }
  async function initializeLive() {
    const fragment = new URLSearchParams(location.hash.slice(1));
    let grant = fragment.get("live-grant");
    if (grant) {
      history.replaceState(null,"",location.pathname+location.search+"#live-poc");
      const response = await fetch("/api/carrierview/live-session",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({grant})});
      grant=null;
      if (!response.ok) {
        document.getElementById("live-message").textContent="Owner launch link expired. Run the private live-view launcher again.";
        return;
      }
    }
    await showLive();
  }
  initializeLive().catch(()=>{document.getElementById("live-message").textContent="Live view unavailable; retry the private launcher.";});
  document.getElementById("live-form").addEventListener("submit", async event => {
    event.preventDefault();
    const field=document.getElementById("live-access");
    let secret=field.value;
    field.value="";
    const message=document.getElementById("live-message");
    try {
      const response=await fetch("/api/carrierview/poc",{headers:{"Authorization":"Bearer "+secret}});
      secret="";
      const result=await response.json();
      if (!response.ok) throw new Error(typeof result.detail==="string"?result.detail:"Live read view unavailable");
      if (!result.imported) {
        document.getElementById("live-badge").textContent="NO VERIFIED IMPORT";
        document.getElementById("live-record").textContent="";
        message.textContent="LIVE POC #001 has not been imported.";
        return;
      }
      document.getElementById("live-badge").textContent="LIVE";
      document.getElementById("live-badge").className="badge active";
      document.getElementById("live-record").innerHTML=liveRecordHtml(result.shipment);
    document.dispatchEvent(new Event("freightdesk-live-ready"));
      message.textContent="Read-only local snapshot · UI reconciliation: "+(result.live_validated?"recorded":"pending")+
        ". This view does not initiate a CarrierView network call.";
    } catch(error) { message.textContent=error.message; }
    finally { secret=""; }
  });
}
