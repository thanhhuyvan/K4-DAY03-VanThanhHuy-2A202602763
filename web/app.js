const $ = id => document.getElementById(id);
let snapshot = null, summary = null, busy = false;

const fmt = ts => new Intl.DateTimeFormat('vi-VN', {
  timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit'
}).format(new Date(ts));

function fmtLatency(ms) {
  if (ms == null || isNaN(ms)) return null;
  if (ms >= 1000) return (ms / 1000).toFixed(2) + 's';
  return Math.round(ms) + 'ms';
}

function node(tag, cls, text) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text !== undefined) el.textContent = text;
  return el;
}

async function api(url, options) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) {
    const err = new Error(data.error || 'Không thể kết nối máy chủ.');
    err.events = data.events || [];
    err.total_latency_ms = data.total_latency_ms;
    throw err;
  }
  return data;
}

/* ===== Tab switching ===== */
function switchTab(tabName) {
  document.querySelectorAll('.panel-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === tabName);
  });
  document.querySelectorAll('.tab-content').forEach(tc => {
    tc.classList.toggle('active', tc.id === 'tab-' + tabName);
  });
}

document.querySelectorAll('.panel-tab').forEach(tab => {
  tab.onclick = () => switchTab(tab.dataset.tab);
});

/* ===== Messages ===== */
function showMessages() {
  $('messageList').replaceChildren();
  snapshot.messages.forEach(m => {
    const row = node('article', 'message-row');
    row.id = m.id;
    row.append(node('div', 'when', fmt(m.timestamp)));
    const body = node('div', 'body');
    body.append(node('div', 'author', m.author));
    body.append(node('div', 'content', m.content));
    const idLine = node('div', 'msg-id', m.id);
    if (m.reply_to) {
      const reply = node('button', 'reply-link', '↳ ' + m.reply_to);
      reply.onclick = () => jump(m.reply_to);
      idLine.append(reply);
    }
    body.append(idLine);
    row.append(body);
    $('messageList').append(row);
  });
}

function jump(id) {
  const target = document.getElementById(id);
  if (!target) return;
  target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  target.classList.add('highlight');
  setTimeout(() => target.classList.remove('highlight'), 2500);
}

/* ===== Trace log rendering ===== */
function renderTrace(events, totalLatencyMs) {
  const body = $('traceBody');
  body.replaceChildren();
  if (!events || events.length === 0) {
    body.innerHTML = '<div class="trace-empty"><div class="icon">📋</div><div>Chưa có log sự kiện</div></div>';
    $('traceCount').textContent = '0';
    return;
  }
  $('traceCount').textContent = events.length;

  // Header stats for trace
  const totalLat = totalLatencyMs || events.reduce((sum, e) => sum + (e.latency_ms || 0), 0);
  const headerCard = node('div', '', '');
  headerCard.style.cssText = 'padding: 8px 12px; margin-bottom: 12px; background: rgba(99,145,255,0.06); border: 1px solid var(--border-glow); border-radius: var(--radius-sm); font-size: 11.5px; color: var(--text-secondary); display: flex; justify-content: space-between; align-items: center;';
  
  const stepInfo = node('span', '', `${events.length} bước thực thi`);
  const latInfo = node('span', '', `⏱ Tổng: ${fmtLatency(totalLat) || '—'}`);
  latInfo.style.fontWeight = '600';
  latInfo.style.color = 'var(--accent)';
  headerCard.append(stepInfo, latInfo);
  body.append(headerCard);

  events.forEach((ev, i) => {
    const step = document.createElement('div');
    step.className = 'trace-step';
    step.style.animationDelay = (i * 0.04) + 's';

    // Dot column
    const dotCol = node('div', 'trace-dot-col');
    let dotType = 'llm';
    if (ev.type === 'TOOL_EXECUTION') dotType = 'tool';
    else if (ev.type === 'FINAL_ANSWER') dotType = 'answer';
    else if (ev.type === 'ERROR' || ev.type === 'VALIDATION_ERROR' || ev.type === 'BUDGET_EXCEEDED') dotType = 'error';
    dotCol.append(node('div', 'trace-dot ' + dotType));
    if (i < events.length - 1) dotCol.append(node('div', 'trace-line'));
    step.append(dotCol);

    // Content
    const content = node('div', 'trace-content');
    const label = node('div', 'trace-label');
    const typeSpan = node('span', 'type ' + dotType);

    const typeNames = {
      'LLM_RESPONSE': 'LLM Think',
      'TOOL_EXECUTION': 'Tool Call',
      'FINAL_ANSWER': 'Final Answer',
      'ERROR': 'API Error',
      'VALIDATION_ERROR': 'Validation Error',
      'BUDGET_EXCEEDED': 'Budget Exceeded'
    };
    typeSpan.textContent = typeNames[ev.type] || ev.type;
    label.append(typeSpan);

    const latText = fmtLatency(ev.latency_ms);
    if (latText) {
      const lat = node('span', 'latency', '⏱ ' + latText);
      if (ev.latency_ms > 2000) lat.style.color = 'var(--purple)';
      else if (ev.latency_ms > 500) lat.style.color = 'var(--amber)';
      else lat.style.color = 'var(--green)';
      label.append(lat);
    }
    content.append(label);

    const detail = node('div', 'trace-detail');

    if (ev.type === 'LLM_RESPONSE') {
      const calls = ev.tool_count || 0;
      detail.innerHTML = calls > 0
        ? `Đã quyết định gọi <code>${calls}</code> tool`
        : 'Đã sinh câu trả lời hoàn tất';
      if (ev.usage && (ev.usage.input_tokens || ev.usage.output_tokens)) {
        detail.innerHTML += `<br><span style="color:var(--text-muted)">Token: ${ev.usage.input_tokens || 0} in → ${ev.usage.output_tokens || 0} out</span>`;
      }
    } else if (ev.type === 'TOOL_EXECUTION') {
      const statusClass = ev.status === 'SUCCESS' ? 'success' : (ev.status === 'NO_DATA' ? 'warn' : 'fail');
      const argsStr = ev.args ? Object.entries(ev.args).map(([k,v]) => `${k}="${v}"`).join(' ') : '';
      detail.innerHTML = `<code>${ev.tool || 'tool'}</code>(${argsStr})<br>`;
      detail.innerHTML += `<span class="trace-tag ${statusClass}">${ev.status}</span>`;
      if (ev.msg_count > 0) detail.innerHTML += ` ${ev.msg_count} tin nhắn trả về`;
    } else if (ev.type === 'FINAL_ANSWER') {
      const ids = ev.source_ids || [];
      detail.innerHTML = `<span class="trace-tag success">SUCCESS</span> `;
      detail.innerHTML += ids.length > 0
        ? `Đã trích dẫn ${ids.length} nguồn: ${ids.map(id => `<code>${id}</code>`).join(' ')}`
        : 'Hoàn tất';
    } else if (ev.type === 'ERROR' || ev.type === 'VALIDATION_ERROR') {
      detail.innerHTML = `<span class="trace-tag fail">${ev.type}</span> <span style="color:var(--red)">${ev.message || ''}</span>`;
    } else if (ev.type === 'BUDGET_EXCEEDED') {
      detail.innerHTML = '<span class="trace-tag warn">BUDGET</span> Đã hết số lượt gọi tool/LLM tối đa.';
    }

    content.append(detail);
    step.append(content);
    body.append(step);
  });
}

/* ===== Summary rendering ===== */
function renderSummary(result) {
  if (result.success === false) {
    $('summaryBody').replaceChildren(node('p', 'error-text', '⚠ ' + (result.error || 'Có lỗi khi phân tích')));
    renderTrace(result.events || [], result.total_latency_ms);
    $('generateBtn').textContent = 'Thử lại ✦';
    $('regenBtn').style.display = '';
    $('genMeta').textContent = `Lỗi (${result.status || 'ERROR'}) · ${result.tool_calls || 0} tool calls`;
    $('latencyBadge').style.display = 'none';
    return;
  }

  summary = result;
  $('summaryBody').replaceChildren();
  const text = node('div', 'summary-text');

  result.summary.split(/(demo_msg_\d+|\*\*[^*]+\*\*|`[^`]+`)/g).forEach(part => {
    const id = part.match(/^(demo_msg_\d+)$/)?.[1];
    if (id && snapshot.messages.some(m => m.id === id)) {
      const link = node('button', 'source-link', part);
      link.onclick = () => jump(id);
      text.append(link);
    } else if (part.startsWith('**') && part.endsWith('**')) {
      text.append(node('strong', '', part.slice(2, -2)));
    } else if (part.startsWith('`') && part.endsWith('`')) {
      text.append(node('code', '', part.slice(1, -1)));
    } else {
      text.append(document.createTextNode(part));
    }
  });

  $('summaryBody').append(text);
  $('downloadBtn').disabled = false;
  $('regenBtn').style.display = '';
  $('generateBtn').textContent = '✓ Đã tóm tắt';

  // Total latency
  const totalLatMs = result.total_latency_ms || (result.events || []).reduce((s, e) => s + (e.latency_ms || 0), 0);
  const latDisplay = fmtLatency(totalLatMs);

  // Status bar latency badge
  if (latDisplay) {
    $('latencyBadge').textContent = '⏱ ' + latDisplay;
    $('latencyBadge').style.display = '';
  }

  // Always render trace log
  renderTrace(result.events || [], totalLatMs);

  const meta = result.cached ? 'Bản lưu Cache' : 'Vừa tạo trực tiếp';
  const tokens = result.usage ? ` · ${((result.usage.input_tokens||0)+(result.usage.output_tokens||0)).toLocaleString()} tokens` : '';
  const latStr = latDisplay ? ` · ⏱ ${latDisplay}` : '';
  $('genMeta').textContent = `${meta}${latStr} · ${result.tool_calls || 0} tool calls${tokens}`;
}

/* ===== Generate / Regenerate ===== */
async function generate(force = false) {
  if (busy || !snapshot) return;
  if (!force && summary && summary.success !== false) {
    $('summaryBody').scrollTop = 0;
    return;
  }

  busy = true;
  $('generateBtn').disabled = true;
  $('regenBtn').style.display = 'none';
  $('generateBtn').textContent = force ? '⟳ Đang chạy lại…' : '⏳ Đang phân tích…';
  $('latencyBadge').style.display = 'none';

  const loadingEl = node('p', 'loading-text');
  loadingEl.innerHTML = '<span class="spinner"></span>' +
    (force ? 'Đang gửi yêu cầu và chạy lại ReAct Agent…' : 'AI đang đọc dữ liệu qua MCP Server…');
  $('summaryBody').replaceChildren(loadingEl);

  // Show live loading state in Trace tab
  $('traceBody').innerHTML = '<div class="trace-empty"><div class="spinner" style="margin:0 auto"></div><div style="margin-top:10px">ReAct Agent đang suy luận và gọi Tool…</div></div>';
  $('traceCount').textContent = '...';

  try {
    const payload = force ? { force: true } : {};
    const res = await api('/api/summarize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    renderSummary(res);
  } catch (error) {
    $('summaryBody').replaceChildren(node('p', 'error-text', '⚠ ' + error.message));
    $('generateBtn').textContent = 'Thử lại ✦';
    $('regenBtn').style.display = '';
    const errEvents = error.events && error.events.length > 0
      ? error.events
      : [{ type: 'ERROR', message: error.message }];
    renderTrace(errEvents, error.total_latency_ms);
  } finally {
    busy = false;
    $('generateBtn').disabled = false;
  }
}

$('generateBtn').onclick = () => generate(false);
$('regenBtn').onclick = () => generate(true);

$('downloadBtn').onclick = () => {
  if (!summary || !summary.summary) return;
  const blob = new Blob([summary.summary], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = 'discord-summary-2026-09-13.md'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

$('dataBtn').onclick = () => {
  if (!snapshot) return;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(snapshot, null, 2)], { type: 'application/json' })
  );
  const link = document.createElement('a');
  link.href = url; link.download = 'discord-demo.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

/* ===== Init ===== */
async function init() {
  try {
    const data = await api('/api/data');
    snapshot = data.snapshot;
    $('statusText').innerHTML = '<strong>' + snapshot.messages.length + '</strong> tin nhắn · 4 ảnh chụp · 1 kênh';
    $('statusDot').classList.add('ok');
    $('channelName').textContent = '# ' + snapshot.channel_name;
    $('count').textContent = snapshot.messages.length + ' msgs';
    $('modelName').textContent = data.model || 'Gemini Flash Lite';
    $('generateBtn').disabled = !data.configured;
    if (!data.configured) $('genMeta').textContent = '⚠ Chưa cấu hình API key';
    showMessages();
    const cache = await api('/api/summary');
    if (cache.result) renderSummary(cache.result);
  } catch (error) {
    $('statusText').textContent = error.message;
  }
}

init();
