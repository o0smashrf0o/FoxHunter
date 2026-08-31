/* SmashDeck core — tabs, helpers, HUD */
function escHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function setHuntStatus(text, mode) {
  var el = document.getElementById('pill-hunt');
  if (!el) return;
  el.textContent = 'STATUS · ' + text;
  el.classList.remove('ok', 'warn', 'hot', 'scanning');
  if (mode === 'scan') el.classList.add('ok', 'scanning');
  else if (mode === 'live') el.classList.add('ok');
  else el.classList.add('hot');
}

function emptyStateHtml(title, sub) {
  return '<tr class="empty-row"><td colspan="8">'
    + '<div class="empty-state">'
    + '<div class="empty-msg">' + escHtml(title || 'NO CONTACTS') + '</div>'
    + '<div class="empty-sub">' + escHtml(sub || 'Run a scan to acquire targets') + '</div>'
    + '</div></td></tr>';
}

function rssiPct(rssi) {
  if (rssi == null || isNaN(rssi)) return 0;
  return Math.max(0, Math.min(100, Math.round((Number(rssi) + 100) * 1.6)));
}

function rssiColor(rssi) {
  if (rssi == null || isNaN(rssi)) return 'var(--muted)';
  if (rssi > -55) return 'var(--accent)';
  if (rssi > -70) return 'var(--warn)';
  return 'var(--danger)';
}

function rssiCellHtml(rssi) {
  var pct = rssiPct(rssi);
  var color = rssiColor(rssi);
  var label = rssi != null && !isNaN(rssi) ? (rssi + ' dBm') : '—';
  return '<div class="rssi-cell">'
    + '<div class="rssi-bar"><span style="width:' + pct + '%;background:' + color + '"></span></div>'
    + '<div class="rssi-n">' + label + '</div></div>';
}

function strongestRssi(devices) {
  var best = null;
  (devices || []).forEach(function (d) {
    if (d.rssi_dbm == null || isNaN(d.rssi_dbm)) return;
    if (best == null || d.rssi_dbm > best) best = d.rssi_dbm;
  });
  return best;
}

function updateAcq(prefix, devices, iface) {
  var n = (devices || []).length;
  var best = strongestRssi(devices);
  var c = document.getElementById(prefix + '-acq-count');
  var i = document.getElementById(prefix + '-acq-iface');
  var b = document.getElementById(prefix + '-acq-best');
  if (c) c.textContent = String(n);
  if (i) i.textContent = iface || '—';
  if (b) b.textContent = best != null ? (best + ' dBm') : '—';
  if (n > 0) setHuntStatus('HUNTING', 'live');
}

function showTab(name) {
  document.querySelectorAll('.tab-pane').forEach(function (p) {
    p.classList.toggle('active', p.id === 'tab-' + name);
  });
  document.querySelectorAll('.tab').forEach(function (t) {
    t.classList.toggle('active', t.getAttribute('data-tab') === name);
  });
  if (name === 'detect' && typeof loadDetectCapabilities === 'function') loadDetectCapabilities();
  if (name === 'findings' && typeof loadFindings === 'function') loadFindings();
  if (name === 'kismet' && typeof kismetStatus === 'function') kismetStatus();
  if (name === 'system' && typeof loadChecks === 'function') loadChecks();
  if (name === 'hunt') {
    if (typeof loadSoiLists === 'function') loadSoiLists();
    if (typeof loadHuntSources === 'function') loadHuntSources();
  }
  if (name === 'heatmap') {
    if (typeof loadSoiLists === 'function') loadSoiLists();
    if (typeof loadHeatMaps === 'function') loadHeatMaps();
  }
}

document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      showTab(tab.getAttribute('data-tab'));
    });
  });
  fetch('/api/version').then(function (r) { return r.json(); }).then(function (j) {
    var el = document.getElementById('header-version');
    if (el) el.textContent = 'v' + (j.version || '?');
  }).catch(function () {});
  if (typeof renderWifiTable === 'function') renderWifiTable();
  if (typeof renderBtTable === 'function') renderBtTable();
  loadLiveSources();
  refreshStats();
  setInterval(refreshStats, 5000);
});

async function loadLiveSources() {
  try {
    var r = await fetch('/api/sources');
    var j = await r.json();
    var det = j.detected || {};
    var settings = j.settings || {};
    var wifiSel = document.getElementById('wifi-source');
    var btSel = document.getElementById('bt-source');
    if (wifiSel) {
      wifiSel.innerHTML = '';
      var wifi = det.wifi || [];
      var named = settings.wifi_sources || {};
      if (wifi.length) {
        wifi.forEach(function (d) {
          var iface = d.iface || d.id;
          var opt = document.createElement('option');
          opt.value = iface;
          var label = iface;
          Object.keys(named).forEach(function (k) {
            if (named[k].iface === iface) label = named[k].label + ' (' + iface + ')';
          });
          if (d.model && d.model !== iface) label = d.model + ' (' + iface + ')';
          opt.textContent = label;
          wifiSel.appendChild(opt);
        });
      } else {
        Object.keys(named).forEach(function (k) {
          var opt = document.createElement('option');
          opt.value = k;
          opt.textContent = named[k].label || k;
          wifiSel.appendChild(opt);
        });
      }
    }
    if (btSel) {
      btSel.innerHTML = '';
      var bts = det.bt || [];
      var namedBt = settings.bt_sources || {};
      if (bts.length) {
        bts.forEach(function (d) {
          var hci = d.hci || d.id;
          var opt = document.createElement('option');
          opt.value = hci;
          opt.textContent = (d.model && d.model !== hci) ? (d.model + ' (' + hci + ')') : hci;
          Object.keys(namedBt).forEach(function (k) {
            if (namedBt[k].hci === hci) opt.textContent = namedBt[k].label + ' (' + hci + ')';
          });
          btSel.appendChild(opt);
        });
      } else {
        Object.keys(namedBt).forEach(function (k) {
          var opt = document.createElement('option');
          opt.value = k;
          opt.textContent = namedBt[k].label || k;
          btSel.appendChild(opt);
        });
      }
    }
  } catch (e) {}
}

async function refreshStats() {
  try {
    var r = await fetch('/api/system_stats');
    var j = await r.json();
    var el = document.getElementById('header-stats');
    if (!el) return;
    var parts = [];
    if (j.temp_c != null) parts.push(j.temp_c + '°C');
    if (j.mem_used_pct != null) parts.push('RAM ' + j.mem_used_pct + '%');
    if (j.load && j.load.length) parts.push('LOAD ' + Number(j.load[0]).toFixed(2));
    el.textContent = parts.join(' · ') || 'DECK · READY';
    el.classList.remove('ok', 'warn');
    if (j.temp_c != null && j.temp_c >= 70) el.classList.add('warn');
    else el.classList.add('ok');
  } catch (e) {}
}

async function clearDevices(type) {
  await fetch('/api/clear_devices', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: type || 'all' })
  });
  if (type === 'wifi' || type === 'all') {
    wifiDevices = [];
    if (typeof renderWifiTable === 'function') renderWifiTable();
    updateAcq('wifi', [], '—');
  }
  if (type === 'bt' || type === 'all') {
    btDevices = [];
    if (typeof renderBtTable === 'function') renderBtTable();
    updateAcq('bt', [], '—');
  }
  setHuntStatus('IDLE', 'idle');
}
