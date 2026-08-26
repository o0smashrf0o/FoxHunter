/* Device detail drawer + Blue Sonar / Locate */
var detailContext = { type: '', mac: '', source: '' };
var _btLocateTimer = null;
var _btLocateMac = '';
var _btLocateSource = '';
var _btSonarTimer = null;
var _btSonarMac = '';
var _btSonarSource = '';

function openDetailPanel(type, dev, source) {
  stopBtLocate();
  stopBlueSonar(true);
  detailContext = { type: type, mac: dev.mac || '', source: source || '' };
  var panel = document.getElementById('detail-panel');
  var title = document.getElementById('detail-title');
  var info = document.getElementById('detail-info');
  var actions = document.getElementById('detail-actions');
  var out = document.getElementById('detail-output');
  if (out) { out.style.display = 'none'; out.innerHTML = ''; }
  var mac = dev.mac || '';
  var isUbertooth = (source || '').toLowerCase().indexOf('ubertooth') >= 0;
  if (title) title.textContent = type === 'wifi' ? (dev.ssid || mac) : (dev.name || mac);

  var rows = '';
  if (type === 'wifi') {
    rows += '<dt>SSID</dt><dd>' + escHtml(dev.ssid || '(hidden)') + '</dd>';
    rows += '<dt>BSSID</dt><dd>' + escHtml(mac) + '</dd>';
    rows += '<dt>RSSI</dt><dd>' + (dev.rssi_dbm != null ? dev.rssi_dbm + ' dBm' : '—') + '</dd>';
    rows += '<dt>Channel</dt><dd>' + escHtml(dev.channel != null ? dev.channel : '—') + '</dd>';
    rows += '<dt>Encryption</dt><dd>' + escHtml(dev.encryption || '') + '</dd>';
    rows += '<dt>Vendor</dt><dd>' + escHtml(dev.vendor || '') + '</dd>';
  } else {
    rows += '<dt>Name</dt><dd>' + escHtml(dev.name || mac) + '</dd>';
    rows += '<dt>MAC</dt><dd>' + escHtml(mac) + '</dd>';
    rows += '<dt>RSSI</dt><dd>' + (dev.rssi_dbm != null ? dev.rssi_dbm + ' dBm' : '—') + '</dd>';
    rows += '<dt>Type</dt><dd>' + escHtml(dev.type || '') + '</dd>';
    rows += '<dt>Vendor</dt><dd>' + escHtml(dev.vendor || '') + '</dd>';
  }
  if (info) info.innerHTML = rows;

  var btns = '';
  if (type === 'wifi') {
    btns += '<button onclick="runAction(\'wifi\',\'' + mac + '\',\'info\',\'' + source + '\')">Info</button>';
    btns += '<button onclick="runAction(\'wifi\',\'' + mac + '\',\'probe\',\'' + source + '\')">Probe</button>';
    btns += '<button class="warn" onclick="runAction(\'wifi\',\'' + mac + '\',\'deauth\',\'' + source + '\')">Deauth</button>';
  } else {
    btns += '<button onclick="runAction(\'bt\',\'' + mac + '\',\'info\',\'' + source + '\')">Info</button>';
    if (!isUbertooth) {
      btns += '<button type="button" id="bt-locate-btn" onclick="toggleBtLocate(\'' + mac + '\',\'' + source + '\')">Locate RSSI</button>';
      btns += '<button type="button" id="bt-sonar-btn" onclick="toggleBlueSonar(\'' + mac + '\',\'' + source + '\')" style="border-color:#6cf">Blue Sonar</button>';
      btns += '<button onclick="runAction(\'bt\',\'' + mac + '\',\'l2ping\',\'' + source + '\')">l2ping</button>';
      btns += '<button onclick="runAction(\'bt\',\'' + mac + '\',\'sdptool\',\'' + source + '\')">SDP</button>';
      btns += '<button onclick="runAction(\'bt\',\'' + mac + '\',\'pair\',\'' + source + '\')">Pair</button>';
    } else {
      btns += '<div class="muted">Ubertooth: passive only</div>';
    }
  }
  if (actions) actions.innerHTML = btns;
  if (panel) panel.classList.add('open');
}

function closeDetailPanel() {
  stopBtLocate();
  stopBlueSonar(true);
  var panel = document.getElementById('detail-panel');
  if (panel) panel.classList.remove('open');
}

async function runAction(type, mac, action, source) {
  var out = document.getElementById('detail-output');
  if (out) {
    out.style.display = 'block';
    out.textContent = 'Running ' + action + '…';
  }
  try {
    var r = await fetch('/api/device_action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: type, mac: mac, action: action, source: source || '' })
    });
    var j = await r.json();
    var lines = [];
    if (j.msg) lines.push(j.msg);
    if (j.error) lines.push('Error: ' + j.error);
    if (j.output) lines.push(j.output);
    if (j.info) {
      if (typeof j.info === 'object') lines.push(JSON.stringify(j.info, null, 2));
      else lines.push(String(j.info));
    }
    if (j.rssi != null) lines.push('RSSI: ' + j.rssi);
    if (j.rtt_ms != null) lines.push('RTT: ' + j.rtt_ms + ' ms');
    if (out) out.textContent = lines.join('\n') || JSON.stringify(j, null, 2);
  } catch (e) {
    if (out) out.textContent = e.message;
  }
}

function _rssiBarHtml(rssi) {
  var pct = 10;
  if (rssi != null && !isNaN(rssi)) pct = Math.max(0, Math.min(100, Math.round((rssi + 100) * 1.6)));
  var color = pct > 65 ? '#0f0' : (pct > 35 ? '#fa0' : '#f66');
  return '<div class="rssi-meter">'
    + '<div class="rssi-meter-track"><div class="rssi-meter-fill" style="width:' + pct + '%;background:' + color + '"></div></div>'
    + '<div class="rssi-meter-label">' + (rssi != null ? (rssi + ' dBm') : '—') + ' · strength ' + pct + '%</div>'
    + '</div>';
}

function stopBtLocate() {
  if (_btLocateTimer) { clearInterval(_btLocateTimer); _btLocateTimer = null; }
  _btLocateMac = '';
  var btn = document.getElementById('bt-locate-btn');
  if (btn) { btn.innerText = 'Locate RSSI'; btn.classList.remove('toggle-on'); }
}

async function toggleBtLocate(mac, source) {
  if (_btLocateTimer && _btLocateMac === mac) { stopBtLocate(); return; }
  stopBtLocate();
  stopBlueSonar(true);
  _btLocateMac = mac;
  _btLocateSource = source || '';
  var btn = document.getElementById('bt-locate-btn');
  if (btn) { btn.innerText = 'Stop locate'; btn.classList.add('toggle-on'); }
  var out = document.getElementById('detail-output');
  if (out) {
    out.style.display = 'block';
    out.innerHTML = '<strong>Locate</strong> — stronger RSSI = closer<br><div id="bt-locate-meter"></div><pre id="bt-locate-log" style="font-size:0.8em;max-height:28vh;overflow:auto"></pre>';
  }
  await _btLocateOnce();
  _btLocateTimer = setInterval(function () { _btLocateOnce(); }, 1800);
}

async function _btLocateOnce() {
  if (!_btLocateMac) return;
  var meter = document.getElementById('bt-locate-meter');
  var log = document.getElementById('bt-locate-log');
  try {
    var r = await fetch('/api/device_action', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'bt', mac: _btLocateMac, action: 'rssi_ping', source: _btLocateSource })
    });
    var j = await r.json();
    var line = new Date().toLocaleTimeString() + ' ';
    if (j.rssi != null) {
      line += 'RSSI ' + j.rssi + ' dBm (' + (j.method || '') + ')';
      if (meter) meter.innerHTML = _rssiBarHtml(j.rssi);
    } else if (j.rtt_ms != null) {
      line += 'RTT ' + j.rtt_ms + ' ms';
      if (meter) meter.innerHTML = _rssiBarHtml(Math.max(-95, Math.min(-40, -40 - j.rtt_ms * 2)));
    } else {
      line += 'no signal — ' + (j.msg || j.error || '');
      if (meter) meter.innerHTML = _rssiBarHtml(null);
    }
    if (log) log.textContent = line + '\n' + (log.textContent || '');
  } catch (e) {
    if (log) log.textContent = 'Error: ' + e.message + '\n' + (log.textContent || '');
  }
}

function stopBlueSonar(silent) {
  if (_btSonarTimer) { clearInterval(_btSonarTimer); _btSonarTimer = null; }
  var mac = _btSonarMac;
  var src = _btSonarSource;
  _btSonarMac = '';
  var btn = document.getElementById('bt-sonar-btn');
  if (btn) { btn.innerText = 'Blue Sonar'; btn.classList.remove('toggle-on'); }
  if (mac) {
    fetch('/api/device_action', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'bt', mac: mac, action: 'blue_sonar_stop', source: src || '' })
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (silent) return;
      var out = document.getElementById('detail-output');
      if (!out) return;
      var lines = ['Blue Sonar stopped.'];
      if (j.min_rssi != null) lines.push('MIN RSSI: ' + j.min_rssi);
      if (j.max_rssi != null) lines.push('MAX RSSI: ' + j.max_rssi);
      if (j.samples != null) lines.push('Samples: ' + j.samples);
      out.style.display = 'block';
      out.innerText = (out.innerText ? out.innerText + '\n' : '') + lines.join('\n');
    }).catch(function () {});
  }
}

async function toggleBlueSonar(mac, source) {
  if (_btSonarTimer && _btSonarMac === mac) { stopBlueSonar(false); return; }
  stopBtLocate();
  stopBlueSonar(true);
  _btSonarMac = mac;
  _btSonarSource = source || '';
  var btn = document.getElementById('bt-sonar-btn');
  if (btn) { btn.innerText = 'Stop Sonar'; btn.classList.add('toggle-on'); }
  var out = document.getElementById('detail-output');
  if (out) {
    out.style.display = 'block';
    out.innerHTML = '<strong>Blue Sonar</strong> — walk toward stronger RSSI<br>'
      + 'Tracking <code>' + escHtml(mac) + '</code><br>'
      + '<div id="bt-sonar-meter"></div>'
      + '<div id="bt-sonar-minmax" class="muted"></div>'
      + '<pre id="bt-sonar-log" style="font-size:0.8em;max-height:28vh;overflow:auto"></pre>';
  }
  try {
    var r = await fetch('/api/device_action', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'bt', mac: mac, action: 'blue_sonar', source: _btSonarSource, sleep: 1 })
    });
    var j = await r.json();
    if (!r.ok || j.ok === false) {
      if (out) out.innerText = 'Blue Sonar failed: ' + (j.error || j.msg || r.status);
      stopBlueSonar(true);
      return;
    }
  } catch (e) {
    if (out) out.innerText = 'Blue Sonar error: ' + e.message;
    stopBlueSonar(true);
    return;
  }
  await _btSonarOnce();
  _btSonarTimer = setInterval(function () { _btSonarOnce(); }, 1200);
}

async function _btSonarOnce() {
  if (!_btSonarMac) return;
  var meter = document.getElementById('bt-sonar-meter');
  var log = document.getElementById('bt-sonar-log');
  var mm = document.getElementById('bt-sonar-minmax');
  try {
    var r = await fetch('/api/device_action', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'bt', mac: _btSonarMac, action: 'blue_sonar_status', source: _btSonarSource })
    });
    var j = await r.json();
    var line = new Date().toLocaleTimeString() + ' ';
    if (j.rssi != null) {
      line += 'RSSI ' + j.rssi + ' dBm (blue_sonar)';
      if (meter) meter.innerHTML = _rssiBarHtml(j.rssi);
    } else {
      line += 'Out of range or not connected';
      if (meter) meter.innerHTML = _rssiBarHtml(null);
    }
    if (mm) {
      var parts = [];
      if (j.min_rssi != null) parts.push('MIN ' + j.min_rssi);
      if (j.max_rssi != null) parts.push('MAX ' + j.max_rssi);
      if (j.samples != null) parts.push(j.samples + ' samples');
      if (j.hci) parts.push(j.hci);
      mm.textContent = parts.join(' · ');
    }
    if (log) {
      log.textContent = line + '\n' + (log.textContent || '');
      if (log.textContent.length > 2500) log.textContent = log.textContent.slice(0, 2500);
    }
  } catch (e) {
    if (log) log.textContent = 'Error: ' + e.message + '\n' + (log.textContent || '');
  }
}
