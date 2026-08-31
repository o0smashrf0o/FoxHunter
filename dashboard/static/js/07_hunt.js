/* Hunt — SOI walk-down + RSSI histogram */
var _huntTimer = null;

function fillSelect(sel, items, valueKey, labelFn) {
  if (!sel) return;
  var cur = sel.value;
  sel.innerHTML = '';
  (items || []).forEach(function (it) {
    var opt = document.createElement('option');
    opt.value = typeof it === 'string' ? it : (it[valueKey] || '');
    opt.textContent = labelFn ? labelFn(it) : opt.value;
    sel.appendChild(opt);
  });
  if (cur) sel.value = cur;
}

async function loadSoiLists() {
  try {
    var r = await fetch('/api/soi?active=1');
    var j = await r.json();
    var items = j.soi || [];
    var lab = function (s) {
      return (s.name ? s.name + ' · ' : '') + s.mac + ' (' + (s.kind || '') + ')';
    };
    fillSelect(document.getElementById('hunt-soi'), items, 'mac', lab);
    fillSelect(document.getElementById('heat-soi'), items, 'mac', lab);
  } catch (e) {}
}

async function loadHuntSources() {
  try {
    var r = await fetch('/api/sources');
    var j = await r.json();
    var kind = (document.getElementById('hunt-kind') || {}).value || 'wifi';
    var sel = document.getElementById('hunt-source');
    if (!sel) return;
    sel.innerHTML = '';
    var list = kind === 'bt' ? (j.detected && j.detected.bt) || [] : (j.detected && j.detected.wifi) || [];
    if (!list.length) {
      var opt = document.createElement('option');
      opt.value = kind === 'bt' ? 'hci0' : 'wlan1';
      opt.textContent = opt.value;
      sel.appendChild(opt);
      return;
    }
    list.forEach(function (d) {
      var opt = document.createElement('option');
      opt.value = kind === 'bt' ? (d.hci || d.id) : (d.iface || d.id);
      opt.textContent = (d.model && d.model !== opt.value) ? (d.model + ' (' + opt.value + ')') : opt.value;
      sel.appendChild(opt);
    });
  } catch (e) {}
}

async function markSoi(mac, kind, name) {
  await fetch('/api/soi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mac: mac, kind: kind || 'wifi', name: name || '', active: 1 })
  });
  await loadSoiLists();
}

async function huntStart() {
  var mac = (document.getElementById('hunt-soi') || {}).value || '';
  var kind = (document.getElementById('hunt-kind') || {}).value || 'wifi';
  var src = (document.getElementById('hunt-source') || {}).value || '';
  if (!mac) return;
  await fetch('/api/hunt/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mac: mac, kind: kind, source: src })
  });
  setHuntStatus('HUNTING', 'scan');
  if (_huntTimer) clearInterval(_huntTimer);
  huntTick();
  _huntTimer = setInterval(huntTick, 2200);
}

async function huntStop() {
  if (_huntTimer) { clearInterval(_huntTimer); _huntTimer = null; }
  await fetch('/api/hunt/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  setHuntStatus('IDLE', 'idle');
  var lab = document.getElementById('hunt-meter-label');
  if (lab) lab.textContent = 'STOPPED';
}

async function huntTick() {
  try {
    var r = await fetch('/api/hunt/sample', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    var j = await r.json();
    renderHunt(j);
  } catch (e) {}
}

function renderHunt(j) {
  var rssi = j.last_rssi;
  var pct = rssiPct(rssi);
  var fill = document.getElementById('hunt-meter-fill');
  var lab = document.getElementById('hunt-meter-label');
  if (fill) {
    fill.style.width = pct + '%';
    fill.style.background = rssiColor(rssi);
  }
  if (lab) lab.textContent = (rssi != null ? rssi + ' dBm' : (j.error || 'no signal')) + ' · ' + (j.mac || '');
  var n = document.getElementById('hunt-now');
  var mn = document.getElementById('hunt-min');
  var mx = document.getElementById('hunt-max');
  var ns = document.getElementById('hunt-n');
  if (n) n.textContent = rssi != null ? rssi + ' dBm' : '—';
  if (mn) mn.textContent = j.min_rssi != null ? j.min_rssi + ' dBm' : '—';
  if (mx) mx.textContent = j.max_rssi != null ? j.max_rssi + ' dBm' : '—';
  if (ns) ns.textContent = String(j.samples || 0);
  drawHuntHist(j.histogram || []);
}

function drawHuntHist(hist) {
  var c = document.getElementById('hunt-hist');
  if (!c || !c.getContext) return;
  var ctx = c.getContext('2d');
  var w = c.width, h = c.height;
  ctx.fillStyle = '#0a0712';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = '#3a2060';
  ctx.beginPath();
  ctx.moveTo(0, h / 2);
  ctx.lineTo(w, h / 2);
  ctx.stroke();
  if (!hist.length) return;
  var n = hist.length;
  ctx.beginPath();
  ctx.strokeStyle = '#b8ff2a';
  ctx.lineWidth = 2;
  hist.forEach(function (p, i) {
    var rssi = p.rssi;
    if (rssi == null) rssi = -100;
    var x = (i / Math.max(n - 1, 1)) * w;
    var y = h - ((rssi + 100) / 70) * h;
    y = Math.max(2, Math.min(h - 2, y));
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function goHunt(mac, kind) {
  markSoi(mac, kind, '');
  showTab('hunt');
  setTimeout(function () {
    var sel = document.getElementById('hunt-soi');
    if (sel) sel.value = (mac || '').toUpperCase();
    var k = document.getElementById('hunt-kind');
    if (k) k.value = kind || 'wifi';
    loadHuntSources();
  }, 200);
}

document.addEventListener('DOMContentLoaded', function () {
  var k = document.getElementById('hunt-kind');
  if (k) k.addEventListener('change', loadHuntSources);
});
