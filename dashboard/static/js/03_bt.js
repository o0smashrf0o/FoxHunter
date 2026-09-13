/* Bluetooth scan table */
var btDevices = [];
var currentBtSource = '';

/* Continuous scan state */
var currentBtContinuousSession = null;   // session_id from server
var btContinuousHci = null;              // locked adapter, e.g. "hci0"
var btContinuousState = "stopped";  // "stopped"|"starting"|"running"|"stopping"|"error"
var btContinuousPollTimer = null;

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

function resolveBtSource() {
  var sel = document.getElementById('bt-source');
  var fromSel = '';
  if (sel && sel.options && sel.options.length) {
    var opt = sel.options[sel.selectedIndex >= 0 ? sel.selectedIndex : 0] || sel.options[0];
    fromSel = (opt && opt.value) || '';
    if (!fromSel && opt) {
      fromSel = (opt.getAttribute('data-hci') || '').trim();
    }
    if (!fromSel && opt) {
      var m = String(opt.textContent || '').match(/hci\d+/i);
      if (m) fromSel = m[0].toLowerCase();
    }
  }
  var src = currentBtSource || fromSel || (sel && sel.value) || '';
  if (src) currentBtSource = src;
  return src;
}

async function startContinuousBt() {
  var src = resolveBtSource();
  var st = document.getElementById('bt-status');
  if (st) { st.textContent = 'Starting on ' + (src || btContinuousHci || '?') + '…'; st.classList.add('scanning'); }
  setHuntStatus('SCANNING', 'scan');
  try {
    var r = await fetch('/api/bt_continuous_start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hci: src || btContinuousHci || '' })
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

function startContinuousDevicePoll() {
  if (btContinuousPollTimer) return;
  pollContinuousDevices();
  btContinuousPollTimer = setInterval(pollContinuousDevices, 2000);
}

function stopContinuousDevicePoll() {
  if (!btContinuousPollTimer) return;
  clearInterval(btContinuousPollTimer);
  btContinuousPollTimer = null;
}

async function pollContinuousDevices() {
  if (btContinuousState !== 'running' && btContinuousState !== 'starting') {
    stopContinuousDevicePoll();
    return;
  }
  try {
    var r = await fetch('/api/bt_continuous_devices');
    var j = await r.json();
    if (!j.ok) return;
    if (!j.running) {
      btContinuousState = 'stopped';
      stopContinuousDevicePoll();
      updateContinuousUI();
      return;
    }
    btDevices = j.devices || [];
    renderBtTable();
    updateAcq('bt', btDevices, j.hci || btContinuousHci || '');
    var c = document.getElementById('bt-acq-count');
    if (c && j.active_device_count != null) c.textContent = String(j.active_device_count);
  } catch (e) {}
}

function updateContinuousUI() {
  var startBtn = document.getElementById('bt-continuous-start');
  var stopBtn = document.getElementById('bt-continuous-stop');
  var sourceSel = document.getElementById('bt-source');
  var src = resolveBtSource();
  var active = btContinuousState !== 'stopped';

  if (startBtn) startBtn.disabled = active || !src;
  if (stopBtn) stopBtn.disabled = !active;
  if (sourceSel) sourceSel.disabled = active;
  if (active) startContinuousDevicePoll();
  else stopContinuousDevicePoll();

  var contSt = document.getElementById('bt-continuous-status');
  var btSt = document.getElementById('bt-status');
  if (!active) {
    if (contSt) contSt.textContent = 'Stopped';
    if (btSt) btSt.textContent = 'STATUS · Stopped';
  } else {
    var statusText = btContinuousState;
    if (btContinuousHci) {
      statusText = btContinuousState === "starting" ? 'Starting on ' + btContinuousHci + '…' :
                   btContinuousState === "running" ? 'Running on ' + btContinuousHci :
                   btContinuousState === "stopping" ? 'Stopping hci' + btContinuousHci + '…' :
                   'Error: ' + btContinuousHci + ' unavailable';
    }
    if (contSt) contSt.textContent = statusText || btContinuousState;
    if (btSt) btSt.textContent = 'STATUS · ' + (btContinuousHci || 'Stopped');
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
    }
    updateContinuousUI();
  })();

  var srcSel = document.getElementById('bt-source');
  if (srcSel) {
    srcSel.addEventListener('change', updateContinuousUI);
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver(updateContinuousUI).observe(srcSel, { childList: true, subtree: true });
    }
  }
  if (typeof loadLiveSources === 'function') {
    var _loadLiveSources = loadLiveSources;
    loadLiveSources = function () {
      var ret = _loadLiveSources.apply(this, arguments);
      if (ret && typeof ret.then === 'function') {
        return ret.then(function (v) { updateContinuousUI(); return v; });
      }
      updateContinuousUI();
      return ret;
    };
  }
  setInterval(updateContinuousUI, 3000);

  if (typeof renderBtTable === 'function') renderBtTable();
});