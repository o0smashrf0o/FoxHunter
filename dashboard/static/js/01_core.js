/* Fox Hunter core — tabs, helpers, HUD */
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
  if (name === 'wifi' || name === 'bt' || name === 'hunt') loadLiveSources();
  if (name === 'wifi' && typeof syncWifiContinuousBtn === 'function') syncWifiContinuousBtn();
  if (name === 'detect' && typeof loadDetectCapabilities === 'function') loadDetectCapabilities();
  if (name === 'findings' && typeof loadFindings === 'function') loadFindings();
  if (name === 'kismet' && typeof kismetStatus === 'function') kismetStatus();
  if (name === 'system') {
    if (typeof loadChecks === 'function') loadChecks();
    if (typeof loadStorage === 'function') loadStorage();
  }
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
  function forceHudPaint() {
    var b = document.body;
    if (!b) return;
    b.style.transform = 'translate(0,0)';
    void b.offsetHeight;
    b.style.transform = '';
    window.dispatchEvent(new Event('resize'));
  }
  window.addEventListener('load', function () {
    forceHudPaint();
    setTimeout(forceHudPaint, 80);
    setTimeout(forceHudPaint, 300);
  });
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) forceHudPaint();
  });
  loadLiveSources();
  refreshStats();
  setInterval(refreshStats, 5000);
  setInterval(loadLiveSources, 3000);
  if (typeof syncWifiContinuousBtn === 'function') {
    syncWifiContinuousBtn();
    setInterval(syncWifiContinuousBtn, 4000);
  }
  if (typeof loadWifiPcapStatus === 'function') {
    loadWifiPcapStatus();
    setInterval(loadWifiPcapStatus, 5000);
  }
});

function _fillSourceSelect(sel, items, valueOf, labelOf) {
  if (!sel) return;
  var prev = sel.value;
  var next = (items || []).map(function (it) {
    return { v: valueOf(it), l: labelOf(it) };
  });
  var same = sel.options.length === next.length;
  if (same) {
    for (var i = 0; i < next.length; i++) {
      if (sel.options[i].value !== next[i].v || sel.options[i].textContent !== next[i].l) {
        same = false; break;
      }
    }
  }
  if (same) return;
  sel.innerHTML = '';
  next.forEach(function (o) {
    var opt = document.createElement('option');
    opt.value = o.v;
    opt.textContent = o.l;
    sel.appendChild(opt);
  });
  if (prev) {
    for (var j = 0; j < sel.options.length; j++) {
      if (sel.options[j].value === prev) { sel.selectedIndex = j; break; }
    }
  }
}

async function loadLiveSources() {
  try {
    var r = await fetch('/api/sources');
    var j = await r.json();
    var det = j.detected || {};
    var settings = j.settings || {};
    var named = settings.wifi_sources || {};
    var wifi = det.wifi || [];
    var wifiItems = wifi.length ? wifi : Object.keys(named).map(function (k) {
      return { iface: named[k].iface || k, model: named[k].label || k, _key: k };
    });
    window._wifiLink = window._wifiLink || {};
    wifiItems.forEach(function (d) {
      var iface = d.iface || d.id || d._key;
      if (!iface) return;
      window._wifiLink[iface] = {
        connected: !!d.connected,
        internet: !!d.internet,
        ssid: d.ssid || ''
      };
    });
    _fillSourceSelect(
      document.getElementById('wifi-source'),
      wifiItems,
      function (d) { return d.iface || d.id || d._key; },
      function (d) {
        var iface = d.iface || d.id || d._key;
        var label = iface;
        Object.keys(named).forEach(function (k) {
          if (named[k].iface === iface) label = named[k].label + ' (' + iface + ')';
        });
        if (d.model && d.model !== iface) label = d.model + ' (' + iface + ')';
        if (d.connected || d.internet) {
          label += d.ssid ? (' — AP: ' + d.ssid) : ' — in use for internet';
        }
        return label;
      }
    );
    var namedBt = settings.bt_sources || {};
    var bts = det.bt || [];
    var btItems = bts.length ? bts : Object.keys(namedBt).map(function (k) {
      return { hci: namedBt[k].hci || k, model: namedBt[k].label || k, _key: k };
    });
    _fillSourceSelect(
      document.getElementById('bt-source'),
      btItems,
      function (d) { return d.hci || d.id || d._key; },
      function (d) {
        var hci = d.hci || d.id || d._key;
        var label = (d.model && d.model !== hci) ? (d.model + ' (' + hci + ')') : hci;
        Object.keys(namedBt).forEach(function (k) {
          if (namedBt[k].hci === hci) label = namedBt[k].label + ' (' + hci + ')';
        });
        return label;
      }
    );
    if (typeof loadHuntSources === 'function') loadHuntSources();
  } catch (e) {}
}

async function hudWindow(action) {
  if (action === 'maximize') {
    try {
      var el = document.documentElement;
      if (!document.fullscreenElement && el.requestFullscreen) el.requestFullscreen();
    } catch (e) {}
  }
  if (action === 'minimize') {
    try {
      if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen();
    } catch (e) {}
  }
  try {
    await fetch('/api/ui/window', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: action })
    });
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
    var stor = j.storage || {};
    var sp = document.getElementById('pill-storage');
    if (sp) {
      sp.textContent = 'DATA ' + (stor.data_human || '—') + ' · FREE ' + (stor.disk_free_human || '—');
      sp.classList.remove('ok', 'warn', 'hot');
      sp.classList.add(stor.level === 'hot' ? 'hot' : (stor.level === 'warn' ? 'warn' : 'ok'));
      if (stor.level === 'hot' && !window._storAlerted) {
        window._storAlerted = true;
        alert('Scan data is using most of the disk. Open System to export or delete scans.');
      }
    }
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
