/* Wi-Fi scan table */
var wifiDevices = [];
var _wifiReleased = {};

async function ensureWifiCapture(iface) {
  iface = (iface || '').trim();
  if (!iface) return true;
  if (_wifiReleased[iface]) return true;
  var info = (window._wifiLink && window._wifiLink[iface]) || {};
  if (!info.connected && !info.internet) return true;
  var who = iface === 'wlan0' ? 'Onboard Wi-Fi (wlan0)' : iface;
  var ssid = info.ssid ? (' "' + info.ssid + '"') : '';
  var extra = info.internet ? ' This will disconnect the deck from the internet.' : '';
  var ok = window.confirm(
    who + ' is connected' + ssid + '.' + extra +
    '\n\nUse it as a Fox Hunter source? The Pi will drop that AP.'
  );
  if (!ok) return false;
  var st = document.getElementById('wifi-status');
  if (st) st.textContent = 'Releasing ' + iface + '…';
  try {
    var r = await fetch('/api/wifi_release', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ iface: iface })
    });
    var j = await r.json();
    if (!j.ok) {
      alert(j.error || j.msg || ('Could not release ' + iface));
      return false;
    }
    _wifiReleased[iface] = true;
    if (window._wifiLink && window._wifiLink[iface]) {
      window._wifiLink[iface].connected = false;
      window._wifiLink[iface].internet = false;
    }
    return true;
  } catch (e) {
    alert(e.message);
    return false;
  }
}

async function scanWifi() {
  var st = document.getElementById('wifi-status');
  var src = (document.getElementById('wifi-source') || {}).value || '';
  if (!(await ensureWifiCapture(src))) {
    if (st) { st.textContent = 'Cancelled'; st.classList.remove('scanning'); }
    return;
  }
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

var _wifiContTimer = null;

async function syncWifiContinuousBtn() {
  var btn = document.getElementById('wifi-continuous');
  var wrap = document.getElementById('wifi-cont-wrap');
  if (!btn) return;
  var running = false;
  try {
    var r = await fetch('/api/kismet_status');
    var j = await r.json();
    running = !!j.running;
  } catch (e) {}
  if (_wifiContTimer && !running) stopWifiContinuous();
  btn.disabled = !running && !_wifiContTimer;
  if (wrap) wrap.classList.toggle('show-tip', btn.disabled);
  if (running && _wifiContTimer) btn.classList.add('toggle-on');
  else btn.classList.remove('toggle-on');
}

function stopWifiContinuous() {
  if (_wifiContTimer) { clearInterval(_wifiContTimer); _wifiContTimer = null; }
  var btn = document.getElementById('wifi-continuous');
  if (btn) { btn.classList.remove('toggle-on'); btn.textContent = 'Continuous'; }
  setHuntStatus('IDLE', 'idle');
}

async function toggleWifiContinuous() {
  var btn = document.getElementById('wifi-continuous');
  if (btn && btn.disabled) return;
  if (_wifiContTimer) { stopWifiContinuous(); return; }
  var src = (document.getElementById('wifi-source') || {}).value || '';
  if (!(await ensureWifiCapture(src))) return;
  if (btn) { btn.textContent = 'Stop cont.'; btn.classList.add('toggle-on'); }
  setHuntStatus('HUNTING', 'scan');
  await wifiContinuousTick();
  _wifiContTimer = setInterval(wifiContinuousTick, 4000);
}

async function wifiContinuousTick() {
  var st = document.getElementById('wifi-status');
  try {
    var src = (document.getElementById('wifi-source') || {}).value || '';
    var r = await fetch('/api/kismet_devices_live?source=' + encodeURIComponent(src));
    var j = await r.json();
    if (!j.ok && !j.devices) {
      stopWifiContinuous();
      await syncWifiContinuousBtn();
      return;
    }
    wifiDevices = (j.devices || []).filter(function (d) {
      return d.type === 'wifi' || d.ssid || (d.mac && d.type !== 'bt');
    });
    renderWifiTable();
    updateAcq('wifi', wifiDevices, j.iface || src || 'kismet');
    if (st) st.textContent = 'Kismet live · ' + (j.iface || src || '?') + ' · ' + wifiDevices.length + ' device(s)';
  } catch (e) {
    if (st) st.textContent = e.message;
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
