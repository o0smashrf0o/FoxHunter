/* Wi-Fi scan table */
var wifiDevices = [];

async function scanWifi() {
  var st = document.getElementById('wifi-status');
  var src = (document.getElementById('wifi-source') || {}).value || '';
  if (st) { st.textContent = 'SCANNING…'; st.classList.add('scanning'); }
  setHuntStatus('SCANNING', 'scan');
  try {
    var r = await fetch('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'wifi', source: src })
    });
    var j = await r.json();
    if (st) st.classList.remove('scanning');
    if (!j.ok && j.error) {
      if (st) st.textContent = j.error;
      setHuntStatus('IDLE', 'idle');
      return;
    }
    wifiDevices = j.devices || [];
    renderWifiTable();
    updateAcq('wifi', wifiDevices, j.iface || src);
    if (st) st.textContent = (j.count || wifiDevices.length) + ' AP(s) on ' + (j.iface || '?');
  } catch (e) {
    if (st) { st.classList.remove('scanning'); st.textContent = e.message; }
    setHuntStatus('IDLE', 'idle');
  }
}

function renderWifiTable() {
  var tb = document.querySelector('#wifi-table tbody');
  if (!tb) return;
  if (!wifiDevices.length) {
    tb.innerHTML = emptyStateHtml('NO CONTACTS', 'Scan the spectrum for access points');
    return;
  }
  var rows = '';
  wifiDevices.forEach(function (d, i) {
    rows += '<tr data-idx="' + i + '">'
      + '<td>' + escHtml(d.ssid || '(hidden)') + '</td>'
      + '<td style="font-family:monospace;font-size:12px">' + escHtml(d.mac || '') + '</td>'
      + '<td>' + rssiCellHtml(d.rssi_dbm) + '</td>'
      + '<td>' + escHtml(d.channel != null ? d.channel : '—') + '</td>'
      + '<td>' + escHtml(d.encryption || '') + '</td>'
      + '<td>' + escHtml(d.vendor || '') + '</td>'
      + '</tr>';
  });
  tb.innerHTML = rows;
  tb.querySelectorAll('tr').forEach(function (tr) {
    tr.addEventListener('click', function () {
      var d = wifiDevices[Number(tr.getAttribute('data-idx'))];
      if (d && typeof openDetailPanel === 'function') {
        openDetailPanel('wifi', d, (document.getElementById('wifi-source') || {}).value || '');
      }
    });
  });
}
