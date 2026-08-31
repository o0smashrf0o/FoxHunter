/* Heatmap — tap imported map to drop Hunt RSSI */
var _heatMarks = [];

async function loadHeatMaps() {
  try {
    var r = await fetch('/api/heatmap/maps');
    var j = await r.json();
    fillSelect(document.getElementById('heat-map'), j.maps || [], 'id', function (m) {
      return (m.name || m.id) + ' · ' + (m.id || '');
    });
    if ((j.maps || []).length) heatShow();
  } catch (e) {}
}

async function heatUpload() {
  var inp = document.getElementById('heat-file');
  if (!inp || !inp.files || !inp.files[0]) return;
  var fd = new FormData();
  fd.append('map', inp.files[0]);
  fd.append('name', inp.files[0].name);
  var r = await fetch('/api/heatmap/maps', { method: 'POST', body: fd });
  var j = await r.json();
  var st = document.getElementById('heat-status');
  if (st) st.textContent = j.ok ? 'Imported ' + (j.map && j.map.id) : (j.error || 'fail');
  await loadHeatMaps();
  if (j.map && j.map.id) {
    var sel = document.getElementById('heat-map');
    if (sel) sel.value = j.map.id;
    heatShow();
  }
}

async function heatShow() {
  var id = (document.getElementById('heat-map') || {}).value || '';
  var img = document.getElementById('heat-img');
  var wrap = document.getElementById('heat-wrap');
  if (!id || !img) return;
  img.onload = function () { sizeHeatCanvas(); heatDraw(); };
  img.src = '/api/heatmap/maps/' + id + '/image?t=' + Date.now();
  var mac = (document.getElementById('heat-soi') || {}).value || '';
  var r = await fetch('/api/heatmap/marks?map_id=' + encodeURIComponent(id) + '&mac=' + encodeURIComponent(mac));
  var j = await r.json();
  _heatMarks = j.marks || [];
}

function sizeHeatCanvas() {
  var img = document.getElementById('heat-img');
  var c = document.getElementById('heat-canvas');
  if (!img || !c) return;
  c.width = img.clientWidth || img.naturalWidth;
  c.height = img.clientHeight || img.naturalHeight;
}

function heatDraw() {
  var c = document.getElementById('heat-canvas');
  if (!c || !c.getContext) return;
  var ctx = c.getContext('2d');
  ctx.clearRect(0, 0, c.width, c.height);
  _heatMarks.forEach(function (m) {
    var x = m.x * c.width;
    var y = m.y * c.height;
    var rssi = m.rssi;
    var col = rssiColor(rssi);
    ctx.beginPath();
    ctx.fillStyle = col;
    ctx.globalAlpha = 0.45;
    var r = 10 + rssiPct(rssi) / 8;
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.strokeStyle = col;
    ctx.stroke();
    ctx.fillStyle = '#e8e4f4';
    ctx.font = '11px monospace';
    ctx.fillText(rssi != null ? String(rssi) : '?', x + 8, y - 8);
  });
}

async function heatClick(ev) {
  var wrap = document.getElementById('heat-wrap');
  var img = document.getElementById('heat-img');
  var id = (document.getElementById('heat-map') || {}).value || '';
  var mac = (document.getElementById('heat-soi') || {}).value || '';
  if (!wrap || !img || !id) return;
  var rect = img.getBoundingClientRect();
  var x = (ev.clientX - rect.left) / rect.width;
  var y = (ev.clientY - rect.top) / rect.height;
  var r = await fetch('/api/heatmap/mark', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ map_id: id, x: x, y: y, mac: mac })
  });
  var j = await r.json();
  if (j.mark) _heatMarks.push(j.mark);
  heatDraw();
}

async function heatClear() {
  var id = (document.getElementById('heat-map') || {}).value || '';
  var mac = (document.getElementById('heat-soi') || {}).value || '';
  await fetch('/api/heatmap/marks/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ map_id: id, mac: mac })
  });
  _heatMarks = [];
  heatDraw();
}

document.addEventListener('DOMContentLoaded', function () {
  var wrap = document.getElementById('heat-wrap');
  if (wrap) wrap.addEventListener('click', heatClick);
  var sel = document.getElementById('heat-map');
  if (sel) sel.addEventListener('change', heatShow);
});
