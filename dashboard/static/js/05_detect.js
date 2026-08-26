/* TSCM Detect tab */
var detectTools = [];

async function loadDetectCapabilities() {
  var sum = document.getElementById('detect-hw-summary');
  try {
    var r = await fetch('/api/detect/capabilities');
    var j = await r.json();
    detectTools = j.tools || [];
    var caps = j.capabilities || {};
    if (sum) {
      var parts = [];
      parts.push(caps.wifi_monitor ? 'Wi-Fi capture OK' : 'No USB Wi-Fi');
      parts.push(caps.bt_hci_scan ? 'BT OK' : 'No BT');
      parts.push(caps.sdr_rx ? 'SDR OK' : 'No SDR');
      sum.textContent = parts.join(' | ');
      sum.style.color = (caps.wifi_monitor || caps.bt_hci_scan) ? 'var(--accent)' : 'var(--danger)';
    }
    renderDetectCards();
  } catch (e) {
    if (sum) sum.textContent = 'Failed to load capabilities: ' + e.message;
  }
}

function renderDetectCards() {
  var root = document.getElementById('detect-cards');
  if (!root) return;
  var html = '';
  detectTools.forEach(function (t) {
    var id = t.tool_id || '';
    var ok = !!t.ok;
    html += '<div class="card' + (ok ? '' : ' disabled') + '">'
      + '<div class="title">' + escHtml(t.name || id) + '</div>'
      + '<div class="blurb">' + escHtml(ok ? (t.kind || 'detect') : (t.message || 'Unavailable')) + '</div>'
      + '<div class="actions">'
      + '<button class="primary" ' + (ok ? '' : 'disabled ') + 'onclick="runDetector(\'' + id + '\')">Run</button>'
      + '</div></div>';
  });
  root.innerHTML = html || '<p class="muted">No detectors configured.</p>';
}

function renderDetectHits(hits, msg) {
  var st = document.getElementById('detect-status-text');
  var tb = document.querySelector('#detect-table tbody');
  if (st) st.textContent = msg || '';
  if (!tb) return;
  var rows = '';
  (hits || []).forEach(function (h) {
    var id = h.mac || h.src || h.bssid || '—';
    var name = h.ssid || h.name || (h.names ? h.names.join(', ') : '') || '—';
    rows += '<tr>'
      + '<td>' + escHtml(h.label || h.category || '') + '</td>'
      + '<td style="font-family:monospace;font-size:12px">' + escHtml(id) + '</td>'
      + '<td>' + escHtml(name) + '</td>'
      + '<td>' + escHtml(h.rssi_dbm != null ? h.rssi_dbm : (h.rssi != null ? h.rssi : '—')) + '</td>'
      + '<td>' + escHtml(h.confidence != null ? h.confidence : '—') + '</td>'
      + '<td style="font-size:12px">' + escHtml((h.match_reasons || []).join(', ') || '—') + '</td>'
      + '</tr>';
  });
  tb.innerHTML = rows || emptyStateHtml('NO HITS', 'Run a detector to search the RF picture');
}

async function runDetector(toolId) {
  var st = document.getElementById('detect-status-text');
  var title = document.getElementById('detect-results-title');
  if (title) title.textContent = 'Results — ' + toolId;
  if (st) st.textContent = 'Running ' + toolId + '…';
  try {
    var r = await fetch('/api/detect/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool_id: toolId })
    });
    var j = await r.json();
    if (r.status === 409 || (j.gate && !j.gate.ok)) {
      renderDetectHits([], j.error || j.message || 'Hardware required');
      return;
    }
    renderDetectHits(j.hits || [], j.msg || j.error || ('OK — ' + (j.count || 0) + ' hit(s)'));
  } catch (e) {
    if (st) st.textContent = e.message;
  }
}

document.addEventListener('DOMContentLoaded', function () {
  var clearBtn = document.getElementById('detect-clear-btn');
  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      renderDetectHits([], 'Cleared.');
    });
  }
});
