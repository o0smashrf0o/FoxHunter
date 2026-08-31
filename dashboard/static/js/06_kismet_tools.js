/* Kismet, tools, findings, system */
async function kismetStatus() {
  var el = document.getElementById('kismet-status');
  try {
    var r = await fetch('/api/kismet_status');
    var j = await r.json();
    if (el) el.textContent = j.running ? 'Running' : 'Stopped';
    if (el) el.style.color = j.running ? 'var(--accent)' : 'var(--muted)';
  } catch (e) {
    if (el) el.textContent = e.message;
  }
}

async function kismetStart() {
  var el = document.getElementById('kismet-status');
  if (el) el.textContent = 'Starting…';
  try {
    var r = await fetch('/api/kismet_start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    var j = await r.json();
    if (el) el.textContent = j.msg || (j.ok ? 'Started' : 'Failed');
    await kismetRefresh();
  } catch (e) {
    if (el) el.textContent = e.message;
  }
}

async function kismetStop() {
  await fetch('/api/kismet_stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  await kismetStatus();
}

async function kismetRefresh() {
  await kismetStatus();
  try {
    var r = await fetch('/api/kismet_devices_live');
    var j = await r.json();
    var tb = document.querySelector('#kismet-table tbody');
    if (!tb) return;
    var rows = '';
    (j.devices || []).forEach(function (d) {
      rows += '<tr>'
        + '<td>' + escHtml(d.ssid || d.name || '') + '</td>'
        + '<td style="font-family:monospace;font-size:12px">' + escHtml(d.mac || '') + '</td>'
        + '<td>' + (d.rssi_dbm != null ? d.rssi_dbm : '—') + '</td>'
        + '<td>' + escHtml(d.type || '') + '</td>'
        + '<td>' + escHtml(d.vendor || '') + '</td>'
        + '</tr>';
    });
    tb.innerHTML = rows || emptyStateHtml('NO CONTACTS', 'Start Kismet then refresh devices');
  } catch (e) {}
}

async function launchTool() {
  var name = (document.getElementById('tool-name') || {}).value || 'nmap';
  var target = (document.getElementById('tool-target') || {}).value || '';
  var out = document.getElementById('tool-output');
  if (out) out.textContent = 'Launching ' + name + '…';
  try {
    var r = await fetch('/launch_tool', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool: name, target: target, options: { target: target } })
    });
    var j = await r.json();
    if (out) out.textContent = JSON.stringify(j, null, 2);
  } catch (e) {
    if (out) out.textContent = e.message;
  }
}

async function loadFindings() {
  try {
    var r = await fetch('/api/findings');
    var j = await r.json();
    var tb = document.querySelector('#findings-table tbody');
    if (!tb) return;
    var rows = '';
    (j.findings || []).forEach(function (f) {
      var tgt = f.target || '';
      var kind = (f.tool || '').indexOf('bt') >= 0 ? 'bt' : 'wifi';
      rows += '<tr>'
        + '<td>' + escHtml(f.id) + '</td>'
        + '<td>' + escHtml(f.tool || '') + '</td>'
        + '<td>' + escHtml(f.severity || '') + '</td>'
        + '<td>' + escHtml(tgt) + '</td>'
        + '<td>' + escHtml(f.summary || '') + '</td>'
        + '<td><button type="button" class="primary" onclick="markSoi(\'' + escHtml(tgt) + '\',\'' + kind + '\',\'' + escHtml(f.summary || '') + '\')">SOI</button> '
        + '<button type="button" onclick="goHunt(\'' + escHtml(tgt) + '\',\'' + kind + '\')">Hunt</button></td>'
        + '</tr>';
    });
    tb.innerHTML = rows || emptyStateHtml('NO FINDINGS', 'Tool output lands here');
  } catch (e) {}
}

async function loadChecks() {
  var out = document.getElementById('system-output');
  if (out) out.textContent = 'Running checks…';
  try {
    var r = await fetch('/api/checks');
    var j = await r.json();
    if (out) out.textContent = JSON.stringify(j, null, 2);
  } catch (e) {
    if (out) out.textContent = e.message;
  }
}

async function loadSources() {
  var out = document.getElementById('system-output');
  if (out) out.textContent = 'Detecting…';
  try {
    var r = await fetch('/api/sources');
    var j = await r.json();
    if (out) out.textContent = JSON.stringify(j, null, 2);
  } catch (e) {
    if (out) out.textContent = e.message;
  }
}
