/* OptiFlow — app.js: chat, mode switching, SSE, configurator wiring */

const SESSION_ID = crypto.randomUUID();

// ── DOM refs ─────────────────────────────────────────────────────
const messagesEl  = document.getElementById('messages');
const inputEl     = document.getElementById('input');
const sendBtn     = document.getElementById('btn-send');
const resultsBody = document.getElementById('results-body');
const resultsTitle = document.getElementById('results-title');
const resultsStatus = document.getElementById('results-status');

// Mode panels & tabs
const panels = {
  chat:      document.getElementById('panel-chat'),
  configure: document.getElementById('panel-configure'),
  scenarios: document.getElementById('panel-scenarios'),
  results:   document.getElementById('panel-results'),
};
const tabs = {
  chat:      document.getElementById('tab-chat'),
  configure: document.getElementById('tab-configure'),
  scenarios: document.getElementById('tab-scenarios'),
  results:   document.getElementById('tab-results'),
};
const badges = {
  configure: document.getElementById('badge-configure'),
  scenarios: document.getElementById('badge-scenarios'),
  results:   document.getElementById('badge-results'),
};

let activeMode = 'chat';
let isBusy = false;
let resultsFrame = null;
let resultsFullFrame = null;

// ── Configurator ─────────────────────────────────────────────────
const cfgRoot = document.getElementById('cfg-root');
const cfgEmpty = document.getElementById('cfg-empty');

const configurator = new Configurator(cfgRoot, {
  sessionId: SESSION_ID,
  onRun: handleConfiguredRun,
});

// ── Mode switching ────────────────────────────────────────────────
function switchMode(mode) {
  if (mode === activeMode) return;
  activeMode = mode;
  Object.entries(panels).forEach(([k, el]) => {
    el.classList.toggle('active', k === mode);
  });
  Object.entries(tabs).forEach(([k, el]) => {
    el.classList.toggle('active', k === mode);
  });
  if (badges[mode]) badges[mode].style.display = 'none';
  if (mode === 'scenarios') loadScenarios();
}

Object.entries(tabs).forEach(([mode, tab]) => {
  tab.addEventListener('click', () => {
    if (!tab.disabled) switchMode(mode);
  });
});

// ── Unlock Configure tab when scenario is ready ───────────────────
function onScenarioReady(scenarioJson) {
  // Show configurator
  cfgEmpty.style.display = 'none';
  cfgRoot.style.display = 'block';
  configurator.load(scenarioJson);

  // Enable tab + badge
  tabs.configure.disabled = false;
  if (badges.configure) { badges.configure.style.display = 'inline'; }
}

// ── Run from configurator ─────────────────────────────────────────
async function handleConfiguredRun(yamlText, selectedUpgrades, agent) {
  // Show overlay
  const overlay = document.createElement('div');
  overlay.className = 'cfg-running-overlay';
  overlay.innerHTML = `
    <div class="run-spinner"></div>
    <div class="run-label">Running ${agent === 'dqn' ? 'DQN' : 'Greedy ROI'} optimization…</div>`;
  document.body.appendChild(overlay);

  try {
    const resp = await fetch('/run-configured', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: SESSION_ID,
        yaml_text: yamlText,
        selected_upgrades: selectedUpgrades,
        agent,
        episodes: agent === 'dqn' ? 200 : 0,
      }),
    });

    const data = await resp.json();
    if (data.error) {
      appendSystemMessage(`Optimization error: ${data.error}`);
      return;
    }

    // Show results
    showResultsHtml(data.html, 'Optimization Complete');

    // Enable results tab
    tabs.results.disabled = false;
    if (badges.results) badges.results.style.display = 'inline';
    switchMode('results');

    // Add summary to chat
    const delta = data.profit_delta;
    const summary = `Optimization complete — **+${fmtMoney(delta)}/period** profit improvement, **${fmtMoney(data.capex_total)}** total invested.`;
    appendSystemMessage(summary);

  } catch (err) {
    appendSystemMessage(`Run error: ${err.message}`);
  } finally {
    overlay.remove();
  }
}

// ── Results display ───────────────────────────────────────────────
function showResultsHtml(html, label) {
  // Chat panel results
  const empty = resultsBody.querySelector('.results-empty');
  if (empty) empty.remove();

  if (!resultsFrame) {
    resultsFrame = document.createElement('iframe');
    resultsFrame.id = 'results-frame';
    resultsFrame.setAttribute('sandbox', 'allow-same-origin allow-scripts');
    resultsBody.appendChild(resultsFrame);
  }
  resultsFrame.srcdoc = html;
  if (label) {
    resultsTitle.textContent = label;
    resultsStatus.innerHTML = '<span class="status-dot"></span> Ready';
  }

  // Full results panel
  const fullBody = document.getElementById('results-full-body');
  const fe = fullBody.querySelector('.results-empty');
  if (fe) fe.remove();
  if (!resultsFullFrame) {
    resultsFullFrame = document.createElement('iframe');
    resultsFullFrame.id = 'results-full-frame';
    resultsFullFrame.setAttribute('sandbox', 'allow-same-origin allow-scripts');
    fullBody.appendChild(resultsFullFrame);
  }
  resultsFullFrame.srcdoc = html;
}

// ── Tool labels ───────────────────────────────────────────────────
const TOOL_LABELS = {
  load_plant:               'Loading plant model…',
  create_scenario:          'Creating scenario…',
  build_custom_scenario:    'Building custom scenario…',
  save_current_as_scenario: 'Saving scenario…',
  list_scenarios:           'Loading saved scenarios…',
  load_saved_scenario:      'Loading scenario…',
  compare_scenarios:        'Comparing scenarios…',
  run_baseline:             'Running baseline simulation…',
  run_optimizer:            'Optimizing investment strategy…',
  compare_agents:           'Comparing all agents…',
};

// ── Chat utilities ────────────────────────────────────────────────
function setBusy(busy) {
  isBusy = busy;
  sendBtn.disabled = busy;
  inputEl.disabled = busy;
}

function autoResize() {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function fmtMoney(v) {
  if (Math.abs(v) >= 1_000_000) return `$${(v/1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v/1_000).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

function createMessage(role) {
  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'user' ? 'YOU' : 'OF';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  wrap.appendChild(avatar);
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  scrollToBottom();
  return bubble;
}

function appendUserMessage(text) {
  createMessage('user').textContent = text;
}

function appendSystemMessage(md) {
  const bubble = createMessage('assistant');
  bubble.innerHTML = marked.parse(md);
  scrollToBottom();
}

function createToolCallEl(toolName) {
  const el = document.createElement('div');
  el.className = 'tool-call';
  el.innerHTML = `<div class="spinner"></div>
    <span class="tool-name">${toolName}</span>
    <span>${TOOL_LABELS[toolName] || 'Running…'}</span>`;
  messagesEl.appendChild(el);
  scrollToBottom();
  return el;
}

function markToolDone(el) {
  el.classList.add('done');
  const s = el.querySelector('.spinner');
  if (s) { s.style.animation = 'none'; s.style.borderTopColor = 'var(--green)'; }
}

// ── Main send ─────────────────────────────────────────────────────
async function send(text) {
  if (!text.trim() || isBusy) return;
  setBusy(true);
  appendUserMessage(text);
  inputEl.value = '';
  autoResize();

  const bubble = createMessage('assistant');
  const cursor = document.createElement('span');
  cursor.className = 'cursor';
  bubble.appendChild(cursor);

  let assistantText = '';
  const toolEls = {};

  try {
    const resp = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, session_id: SESSION_ID }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        let ev;
        try { ev = JSON.parse(line.slice(6)); } catch { continue; }

        switch (ev.type) {
          case 'text':
            assistantText += ev.delta;
            bubble.innerHTML = marked.parse(assistantText);
            bubble.appendChild(cursor);
            scrollToBottom();
            break;

          case 'tool_start': {
            const el = createToolCallEl(ev.name);
            toolEls[ev.name] = el;
            // Show loading in results panel
            resultsStatus.innerHTML = `<span class="status-dot"></span> ${TOOL_LABELS[ev.name] || 'Running…'}`;
            break;
          }

          case 'tool_result_html':
            showResultsHtml(ev.html, ev.tool_name.replace(/_/g, ' '));
            if (toolEls[ev.tool_name]) markToolDone(toolEls[ev.tool_name]);
            break;

          case 'scenario_ready':
            onScenarioReady(ev.scenario_json);
            onScenarioSaved();
            break;

          case 'done':
            break;
        }
      }
    }
  } catch (err) {
    bubble.innerHTML = `<span style="color:var(--red)">Error: ${err.message}</span>`;
  } finally {
    cursor.remove();
    if (assistantText) bubble.innerHTML = marked.parse(assistantText);
    setBusy(false);
    scrollToBottom();
  }
}

// ── Scenarios tab ────────────────────────────────────────────────
let compareSelected = new Set(); // scenario IDs selected for comparison

async function loadScenarios() {
  const grid = document.getElementById('scenarios-grid');
  const empty = document.getElementById('scenarios-empty');
  if (!grid) return;

  try {
    const resp = await fetch('/scenarios');
    const records = await resp.json();

    if (!records || records.length === 0) {
      grid.style.display = 'none';
      empty.style.display = 'flex';
      return;
    }

    empty.style.display = 'none';
    grid.style.display = 'grid';
    grid.innerHTML = records.map(r => renderScenarioCard(r)).join('');

    grid.querySelectorAll('.btn-sc-load').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        const name = btn.dataset.name;
        switchMode('chat');
        send(`Load scenario ${id} — ${name}`);
      });
    });

    grid.querySelectorAll('.btn-sc-compare-toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        const name = btn.dataset.name;
        if (compareSelected.has(id)) {
          compareSelected.delete(id);
          btn.classList.remove('active');
        } else {
          compareSelected.add(id);
          btn.classList.add('active');
        }
        updateCompareBar();
      });
    });

    grid.querySelectorAll('.btn-sc-delete').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.dataset.id;
        if (!confirm(`Delete scenario "${btn.dataset.name}"?`)) return;
        await fetch(`/scenarios/${id}`, { method: 'DELETE' });
        compareSelected.delete(id);
        updateCompareBar();
        loadScenarios();
      });
    });

    // Restore compare selections visually
    compareSelected.forEach(id => {
      const btn = grid.querySelector(`.btn-sc-compare-toggle[data-id="${id}"]`);
      if (btn) btn.classList.add('active');
    });

  } catch (e) {
    if (empty) empty.innerHTML = `<p style="color:var(--red)">Error loading scenarios: ${e.message}</p>`;
  }
}

function renderScenarioCard(r) {
  const TAG_CLASSES = {
    'vendor-deal': 'sc-tag-vendor',
    'market-change': 'sc-tag-market',
    'budget': 'sc-tag-budget',
    'in-flight': 'sc-tag-inflight',
  };

  const tags = (r.tags || []).map(t =>
    `<span class="sc-tag ${TAG_CLASSES[t] || ''}">${t}</span>`
  ).join('');

  const changes = r.changes || {};
  const changeParts = [];
  if (changes.budget) changeParts.push(`Budget: ${fmtMoney(changes.budget)}`);
  if (changes.unit_value) changeParts.push(`Price: $${changes.unit_value.toFixed(2)}`);
  if (changes.upgrade_cost_overrides) {
    const n = Object.keys(changes.upgrade_cost_overrides).length;
    changeParts.push(`${n} upgrade repriced`);
  }
  const changesHtml = changeParts.length
    ? `<div class="sc-changes">Changes: ${changeParts.join(' · ')}</div>`
    : '';

  const inFlight = r.in_flight || [];
  const inflightHtml = inFlight.length
    ? `<div class="sc-inflight">In-flight: ${inFlight.slice(0,2).map(i => i.upgrade_id).join(', ')}${inFlight.length > 2 ? '…' : ''}</div>`
    : '';

  const opt = r.optimization || {};
  const optHtml = opt.profit_delta
    ? `<div class="sc-optimization">▲ +${fmtMoney(opt.profit_delta)}/period optimized</div>`
    : '';

  const created = (r.created_at || '').slice(0, 10);
  const nameSafe = (r.name || '').replace(/"/g, '&quot;');

  return `
<div class="scenario-card" data-id="${r.id}">
  <div class="sc-header">
    <div class="sc-name">${r.name}</div>
    <div class="sc-date">${created}</div>
  </div>
  ${tags ? `<div class="sc-tags">${tags}</div>` : ''}
  <div class="sc-rationale">${(r.rationale || '').slice(0, 140)}</div>
  <div class="sc-id">ID: ${r.id}</div>
  ${changesHtml}
  ${inflightHtml}
  ${optHtml}
  <div class="sc-actions">
    <button class="btn-sc-load" data-id="${r.id}" data-name="${nameSafe}">Load into session</button>
    <button class="btn-sc-compare-toggle" data-id="${r.id}" data-name="${nameSafe}">Compare</button>
    <button class="btn-sc-delete" data-id="${r.id}" data-name="${nameSafe}">✕</button>
  </div>
</div>`;
}

function updateCompareBar() {
  const bar = document.getElementById('scenarios-compare-bar');
  const namesEl = document.getElementById('compare-selected-names');
  if (!bar || !namesEl) return;

  if (compareSelected.size < 2) {
    bar.style.display = 'none';
    return;
  }

  bar.style.display = 'flex';
  const ids = [...compareSelected];
  namesEl.textContent = ids.join(', ');
}

document.getElementById('btn-refresh-scenarios')?.addEventListener('click', loadScenarios);

document.getElementById('btn-do-compare')?.addEventListener('click', () => {
  if (compareSelected.size < 2) return;
  const ids = [...compareSelected];
  switchMode('chat');
  send(`Compare scenarios: ${ids.join(' and ')}`);
});

document.getElementById('btn-clear-compare')?.addEventListener('click', () => {
  compareSelected.clear();
  updateCompareBar();
  document.querySelectorAll('.btn-sc-compare-toggle.active').forEach(b => b.classList.remove('active'));
});

// Show scenarios badge when a new scenario is saved
function onScenarioSaved() {
  if (activeMode !== 'scenarios' && badges.scenarios) {
    badges.scenarios.style.display = 'inline';
  }
}

// ── Events ───────────────────────────────────────────────────────
sendBtn.addEventListener('click', () => send(inputEl.value));
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(inputEl.value); }
});
inputEl.addEventListener('input', autoResize);

document.getElementById('btn-new').addEventListener('click', async () => {
  if (isBusy) return;
  await fetch('/reset', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: SESSION_ID }),
  });
  location.reload();
});

document.getElementById('btn-load-example').addEventListener('click', () => {
  if (isBusy) return;
  inputEl.value = `I run a 5-step widget manufacturing operation.

Step 1 — Raw Material Prep: 160 units/hour, 98% yield. $2,000/month labor and materials.

Step 2 — CNC Machining: this is our problem area. 80 units/hour and 9% scrap rate (91% yield). $7,000/month.

Step 3 — Heat Treatment: 130 units/hour, 97% yield, $4,500/month.

Step 4 — Quality Inspection: 110 units/hour, 99% yield, $3,200/month.

Step 5 — Packaging: 220 units/hour, 100% yield, $1,800/month.

Each widget sells for $85. Standard 176 working hours/month. $350,000 available for investment over 24 months.`;
  autoResize();
  inputEl.focus();
});

inputEl.focus();
