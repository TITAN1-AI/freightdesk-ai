const assert = require("node:assert/strict");
const {liveRecordHtml} = require("../app/dashboard/live.js");
const html = liveRecordHtml({
  booking_load_id:"SYNTHETIC-1847", provider_id:"synthetic-provider",
  status:"IN_TRANSIT", app_status:null, last_position_at:null, eta:null,
  time_left_sec:0, distance_left_meters:null, driver_is_late:false,
  current_city_state:"<script>unsafe()</script>", stops:null, credential_class:"agent",
});
assert(html.includes("SYNTHETIC-1847") && html.includes("synthetic-provider"));
assert(html.includes("Unknown / not provided") && html.includes("<dd>0</dd>") && html.includes("<dd>false</dd>"));
assert(!html.includes("<script>") && html.includes("&lt;script&gt;"));
assert(html.includes("Read credential class"));
const historical = liveRecordHtml({
  historical:true, title:"LIVE POC #001 — Historical Production Replay",
  booking_load_id:"TEST-42", provider_id:"fixture", credential_class:"tenant",
  provider_facts:{app_status:"tracking", delivery_arrived:true, delivery_departed:true,
    time_left_sec:null, distance_left_meters:null, history_records_received:10,history_pagination:{total:218}},
  derived:{canonical_status:"DELIVERED",arrival_assessment:"NO_LATE_ARRIVAL_OBSERVED",
    risk:"WARNING",risk_explanation:"Documents unverified",billing_readiness:"UNVERIFIED"},
  stops:[],capability_matrix:{"Historical read":true,"POD":false}
});
assert(historical.includes("CarrierView facts") && historical.includes("FreightDesk-derived assessments"));
assert(historical.includes("10 of 218") && historical.includes("POD</td><td>NO"));
assert(!historical.includes("Tracking age"));
console.log("Live-view synthetic rendering, unknown/null, zero/false, and HTML-escaping checks passed");
