/* Bluetooth scan table */
var btDevices = [];
var currentBtSource = '';

/* Continuous scan state */
var currentBtContinuousSession = null;   // session_id from server
var btContinuousHci = null;              // locked adapter, e.g. "hci0"
var btContinuousState = "stopped";  // "stopped"|"starting"|"running"|"stopping"|"error"

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

/* --------------------------------------------------------------
 * Continuous scan control
 * -------------------------------------------------------------- */

async function startContinuousBt() {
  var src = (document.getElementById('bt-source') || {}).value || '';
  var st = document.getElementById('bt-status');
  if (st) { st.textContent = 'Starting on ' + btContinuousHci + '…'; st.classList.add('scanning'); }
  setHuntStatus('SCANNING', 'scan');
  try {
    var r = await fetch('/api/bt_continuous_start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hci: btContinuousHci || src })
    });
    var j = await r.json();
    if (st) st.classList.remove('scanning');
    if (!j.ok) {
      if (j.error) {
        if (st) st.textContent = j.error;
        setHuntStatus('ERROR', 'hot');
      } else {
        if (st) st.textContent = 'Unknown error';
        setHuntStatus('ERROR', 'hot');
      }
      btContinuousState = "error";
      btContinuousHci = null;
      currentBtContinuousSession = null;
      updateContinuousUI();
      return;
    }
    // Success – update state from response
    currentBtContinuousSession = j.session_id || null;
    btContinuousHci = j.hci || null;
    btContinuousState = j.already_running ? "running" : "running";
    updateContinuousUI();
  } catch (e) {
    if (st) { st.classList.remove('scanning'); st.textContent = e.message; }
    setHuntStatus('ERROR', 'hot');
    btContinuousState = "error";
    btContinuousHci = null;
    currentBtContinuousSession = null;
    updateContinuousUI();
  }
}

async function stopContinuousBt() {
  var st = document.getElementById('bt-status');
  if (st) { st.textContent = 'Stopping hci' + (btContinuousHci ? ' ' + btContinuousHci : '') + '…'; st.classList.add('scanning'); }
  setHuntStatus('SCANNING', 'scan');
  try {
    var r = await fetch('/api/bt_continuous_stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    var j = await r.json();
    if (st) st.classList.remove('scanning');
    if (!j.ok) {
      if (st) st.textContent = j.error || 'Stop failed';
      setHuntStatus('ERROR', 'hot');
      return;
    }
    // Session fully stopped
    currentBtContinuousSession = null;
    btContinuousHci = null;
    btContinuousState = "stopped";
    updateContinuousUI();
  } catch (e) {
    if (st) { st.classList.remove('scanning'); st.textContent = e.message; }
    setHuntStatus('ERROR', 'hot');
  }
}

function updateContinuousUI() {
  // Enable/Disable Start button
  var startBtn = document.querySelector('button[onclick="startContinuousBt"]');
  var stopBtn = document.querySelector('button[onclick="stopContinuousBt"]');
  var sourceSel = document.getElementById('bt-source');

  if (btContinuousState === "stopped") {
    if (startBtn) startBtn.disabled = false;
    if (stopBtn) stopBtn.disabled = true;
    if (sourceSel) sourceSel.disabled = false;
    if (document.getElementById('bt-continuous-status')) {
      document.getElementById('bt-continuous-status').textContent = 'Stopped';
    }
    // Also set bt-status pill
    if (document.getElementById('bt-status')) {
      document.getElementById('bt-status').textContent = 'STATUS · Stopped';
    }
  } else {
    if (startBtn) startBtn.disabled = true;
    if (stopBtn) stopBtn.disabled = false;
    if (sourceSel) sourceSel.disabled = true;
    var statusText = '';
    if (btContinuousHci) {
      statusText = btContinuousState === "starting" ? 'Starting on ' + btContinuousHci + '…' :
                   btContinuousState === "running" ? 'Running on ' + btContinuousHci :
                   btContinuousState === "stopping" ? 'Stopping hci' + btContinuousHci + '…' :
                   'Error: ' + btContinuousHci + ' unavailable';
    }
    if (document.getElementById('bt-continuous-status')) {
      document.getElementById('bt-continuous-status').textContent = statusText || btContinuousState;
    }
    // Also set bt-status pill
    if (document.getElementById('bt-status')) {
      document.getElementById('bt-status').textContent = 'STATUS · ' + (btContinuousHci || 'Stopped');
    }
  }
}

document.addEventListener('DOMContentLoaded', function () {
  // On tab load/refresh, fetch server-side continuous scan status
  // so that a page refresh does not lose the running state.
  (async function loadContinuousStatus() {
    try {
      var r = await fetch('/api/bt_continuous_status');
      var j = await r.json();
      if (j.ok) {
        currentBtContinuousSession = j.session_id || null;
        btContinuousHci = j.hci || null;
        btContinuousState = j.running ? "running" : "stopped";
        updateContinuousUI();
      }
    } catch (e) {
      // If status fetch fails, UI stays in default stopped state
    }
  })();

  // Existing table render
  if (typeof renderBtTable === 'function') renderBtTable();
});