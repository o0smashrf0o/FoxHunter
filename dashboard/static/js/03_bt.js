/* Bluetooth scan table */
var btDevices = [];
var currentBtSource = '';

async function scanBt() {
  var st = document.getElementById('bt-status');
  var src = (document.getElementById('bt-source') || {}).value || '';
  currentBtSource = src;
  if (st) { st.textContent = 'SCANNING…'; st.classList.add('scanning'); }
  setHuntStatus('SCANNING', 'scan');
  try {
    var r = await fetch('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'bt', source: src })
    });
    var j = await r.json();
    if (st) st.classList.remove('scanning');
    if (!j.ok && j.error) {
      if (st) st.textContent = j.error;
      setHuntStatus('IDLE', 'idle');
      return;
    }
    btDevices = j.devices || [];
    renderBtTable();
    updateAcq('bt', btDevices, j.hci || src);
    if (st) st.textContent = (j.count || btDevices.length) + ' device(s) on ' + (j.hci || '?');
  } catch (e) {
    if (st) { st.classList.remove('scanning'); st.textContent = e.message; }
    setHuntStatus('IDLE', 'idle');
  }
}

function renderBtTable() {
  var tb = document.querySelector('#bt-table tbody');
  if (!tb) return;
  if (!btDevices.length) {
    tb.innerHTML = emptyStateHtml('NO CONTACTS', 'Scan for Bluetooth / BLE targets');
    return;
  }
  var rows = '';
  btDevices.forEach(function (d, i) {
    rows += '<tr data-idx="' + i + '">'
      + '<td>' + escHtml(d.name || d.mac || '') + '</td>'
      + '<td style="font-family:monospace;font-size:12px">' + escHtml(d.mac || '') + '</td>'
      + '<td>' + rssiCellHtml(d.rssi_dbm) + '</td>'
      + '<td>' + escHtml(d.type || '') + '</td>'
      + '<td>' + escHtml(d.vendor || '') + '</td>'
      + '</tr>';
  });
  tb.innerHTML = rows;
  tb.querySelectorAll('tr').forEach(function (tr) {
    tr.addEventListener('click', function () {
      var d = btDevices[Number(tr.getAttribute('data-idx'))];
      if (d && typeof openDetailPanel === 'function') {
        openDetailPanel('bt', d, currentBtSource || (document.getElementById('bt-source') || {}).value || '');
      }
    });
  });
}
