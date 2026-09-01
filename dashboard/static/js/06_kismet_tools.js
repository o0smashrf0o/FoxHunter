/* Kismet, tools, findings, system */
async function kismetStatus() {
  var el = document.getElementById('kismet-status');
  try {
    var r = await fetch('/api/kismet_status');
    var j = await r.json();
    renderKismetConsole(j);
    if (el) el.textContent = j.running ? 'Running' : 'Stopped';
    if (el) el.style.color = j.running ? 'var(--accent)' : 'var(--muted)';
    return j;
  } catch (e) {
    if (el) el.textContent = e.message;
    return { running: false };
  }
}

function renderKismetConsole(j) {
  var sum = j.summary || {};
  var run = document.getElementById('kismet-run');
  var devs = document.getElementById('kismet-devs');
  var rate = document.getElementById('kismet-rate');
  var nsrc = document.getElementById('kismet-nsrc');
  var cons = document.getElementById('kismet-console');
  var web = document.getElementById('kismet-web');
  var srcs = sum.sources || [];
  if (run) run.textContent = j.running ? 'UP' : 'DOWN';
  if (devs) devs.textContent = sum.devices != null ? String(sum.devices) : '—';
  if (rate) rate.textContent = sum.packet_rate != null ? String(sum.packet_rate) : '—';
  if (nsrc) nsrc.textContent = String(srcs.length);
  if (web && j.web) { web.href = j.web + '/'; web.textContent = j.web + '/'; }
  var tb = document.querySelector('#kismet-src-table tbody');
  if (tb) {
    var rows = '';
    srcs.forEach(function (s) {
      rows += '<tr>'
        + '<td>' + escHtml(s.name || '') + '</td>'
        + '<td>' + escHtml(s.interface || '') + '</td>'
        + '<td>' + escHtml(s.channel != null ? s.channel : '—') + '</td>'
        + '<td>' + (s.running ? 'yes' : 'no') + '</td>'
        + '<td>' + escHtml(s.packets != null ? s.packets : '—') + '</td>'
        + '</tr>';
    });
    tb.innerHTML = rows || '<tr><td colspan="5" class="muted">No datasources</td></tr>';
  }
  if (cons) {
    var lines = [];
    lines.push(j.running ? 'Kismet server running.' : 'Kismet server stopped.');
    if (j.msg) lines.push(j.msg);
    if (j.error) lines.push('Error: ' + j.error);
    if (sum.version) lines.push('Version: ' + sum.version);
    if (sum.devices != null) lines.push('Devices: ' + sum.devices);
    if (sum.packet_rate != null) lines.push('Packet rate: ' + sum.packet_rate);
    srcs.forEach(function (s) {
      lines.push('Source ' + (s.name || '?') + ' iface=' + (s.interface || '') + ' ch=' + (s.channel || '') + ' running=' + s.running);
    });
    if (j.console) {
      lines.push('');
      lines.push('--- launch log ---');
      lines.push(j.console);
    }
    cons.textContent = lines.join('\n');
  }
}

async function kismetStart() {
  var el = document.getElementById('kismet-status');
  if (el) el.textContent = 'Starting…';
  try {
    var r = await fetch('/api/kismet_start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    var j = await r.json();
    if (el) {
      el.textContent = j.msg || (j.ok ? 'Started' : 'Failed');
      el.style.color = j.ok ? 'var(--accent)' : 'var(--danger)';
    }
    if (typeof syncWifiContinuousBtn === 'function') syncWifiContinuousBtn();
    await kismetStatus();
  } catch (e) {
    if (el) el.textContent = e.message;
  }
}

async function kismetStop() {
  if (typeof stopWifiContinuous === 'function') stopWifiContinuous();
  await fetch('/api/kismet_stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  await kismetStatus();
  if (typeof syncWifiContinuousBtn === 'function') syncWifiContinuousBtn();
}

async function kismetRefresh() {
  await kismetStatus();
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
