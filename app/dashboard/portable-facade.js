/* Portable harvest freshness only. Text nodes; never HTML from the facade. */
(() => {
  const node = document.querySelector('#portable-harvest-status');
  if (!node) return;
  fetch('/v1/ascend/status', {headers: {'X-FreightDesk-Local': '1'}}).then(async (response) => {
    if (!response.ok) {
      node.textContent = 'Portable harvest: local session required · CANDIDATE facade · not LIVE_VALIDATED';
      return;
    }
    const data = await response.json();
    if (!data.harvest_available) {
      node.textContent = 'Portable harvest: none yet · ' + (data.lease_status || 'NONE') +
        ' lease · CANDIDATE facade · not LIVE_VALIDATED';
      return;
    }
    node.textContent = 'Portable harvest: ' + data.row_count + ' visible rows · ' +
      (data.last_harvest_at || 'unknown time') + ' · lease ' + data.lease_status +
      ' · CANDIDATE · not LIVE_VALIDATED';
  }).catch(() => {
    node.textContent = 'Portable harvest: facade unavailable · not LIVE_VALIDATED';
  });
})();
