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

function kismetWifiSource() {
  return ((document.getElementById('wifi-source') || {}).value || '').trim();
}

async function kismetStart() {
  var el = document.getElementById('kismet-status');
  var src = kismetWifiSource();
  if (typeof ensureWifiCapture === 'function' && !(await ensureWifiCapture(src))) {
    if (el) el.textContent = 'Cancelled';
    return;
  }
  if (el) el.textContent = 'Starting…';
  try {
    var r = await fetch('/api/kismet_start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: kismetWifiSource() })
    });
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
  var el = document.getElementById('kismet-status');
  if (el) el.textContent = 'Stopping…';
  if (typeof stopWifiContinuous === 'function') stopWifiContinuous();
  try {
    var r = await fetch('/api/kismet_stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    var j = await r.json();
    if (el) {
      el.textContent = j.msg || (j.ok ? 'Stopped' : 'Stop failed');
      el.style.color = j.ok ? 'var(--muted)' : 'var(--danger)';
    }
  } catch (e) {
    if (el) el.textContent = e.message;
  }
  await kismetStatus();
  if (typeof syncWifiContinuousBtn === 'function') syncWifiContinuousBtn();
}

async function kismetRefresh() {
  var el = document.getElementById('kismet-status');
  if (el) el.textContent = 'Restarting…';
  await kismetStop();
  await kismetStart();
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

async function setHudPassword() {
  var p1 = window.prompt("New HUD password (min 4 characters)");
  if (p1 == null) return;
  var p2 = window.prompt("Confirm password");
  if (p1 !== p2) { alert("Passwords did not match"); return; }
  var r = await fetch('/api/auth', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: p1 })
  });
  var j = await r.json();
  var el = document.getElementById('auth-status');
  if (el) el.textContent = j.ok ? 'Password set — used next unlock' : (j.error || 'failed');
}

async function clearHudPassword() {
  if (!window.confirm("Remove HUD password?")) return;
  var r = await fetch('/api/auth', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ clear: true })
  });
  var j = await r.json();
  var el = document.getElementById('auth-status');
  if (el) el.textContent = j.ok ? 'No password' : 'failed';
}

async function loadStorage() {
  try {
    var r = await fetch('/api/storage');
    var j = await r.json();
    window._storMounts = j.mounts || [];
    var path = document.getElementById('stor-path');
    var label = document.getElementById('stor-label');
    var bar = document.getElementById('stor-bar');
    var fill = document.getElementById('stor-fill');
    if (path) path.textContent = j.data_dir || '';
    if (label) {
      label.textContent = (j.data_human || '0') + ' of scans/data  ·  disk ' +
        (j.used_pct != null ? j.used_pct + '% used' : '') + '  ·  ' + (j.disk_free_human || '?') + ' free';
    }
    if (bar) {
      bar.classList.remove('warn', 'hot');
      if (j.level === 'warn' || j.level === 'hot') bar.classList.add(j.level);
    }
    if (fill) fill.style.width = Math.min(100, Number(j.data_pct) || 0) + '%';
    var tb = document.querySelector('#stor-table tbody');
    if (tb) {
      var rows = '';
      (j.scans || []).forEach(function (s) {
        var p = encodeURIComponent(s.path);
        rows += '<tr>'
          + '<td>' + escHtml(s.name) + '</td>'
          + '<td>' + escHtml(s.kind) + '</td>'
          + '<td>' + escHtml(s.human) + '</td>'
          + '<td><a href="/api/storage/export?path=' + p + '" style="color:var(--accent2)">JSON</a> '
          + (s.csv ? '<a href="/api/storage/export?path=' + encodeURIComponent(s.csv) + '" style="color:var(--accent2)">CSV</a> ' : '')
          + '<button type="button" onclick="deleteScanFile(\'' + p + '\')">Del</button></td>'
          + '</tr>';
      });
      tb.innerHTML = rows || '<tr><td colspan="4" class="muted">No saved scans yet</td></tr>';
    }
  } catch (e) {}
}

async function deleteScanFile(encPath) {
  if (!window.confirm('Delete this scan file?')) return;
  await fetch('/api/storage/delete', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: decodeURIComponent(encPath) })
  });
  loadStorage();
}

async function deleteAllScans() {
  if (!window.confirm('Delete ALL saved Wi-Fi and Bluetooth scans?')) return;
  await fetch('/api/storage/delete', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ all: true })
  });
  loadStorage();
}

async function copyAllScans() {
  var mounts = window._storMounts || [];
  var dest = mounts[0] || window.prompt('Path to USB / external drive (e.g. /media/smash/USB)');
  if (mounts.length > 1) dest = window.prompt('Copy scans to:\n' + mounts.join('\n'), mounts[0]);
  if (!dest) return;
  var r = await fetch('/api/storage/copy', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dest: dest })
  });
  var j = await r.json();
  alert(j.ok ? ('Copied to ' + j.msg) : (j.error || j.msg || 'copy failed'));
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
