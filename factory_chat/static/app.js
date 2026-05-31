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
  results:   document.getElementById('panel-results'),
};
const tabs = {
  chat:      document.getElementById('tab-chat'),
  configure: document.getElementById('tab-configure'),
  results:   document.getElementById('tab-results'),
};
const badges = {
  configure: document.getElementById('badge-configure'),
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
  // Clear badge for the now-active tab
  if (badges[mode]) badges[mode].style.display = 'none';
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
  create_scenario: 'Building simulation model…',
  run_baseline:    'Running baseline simulation…',
  run_optimizer:   'Optimizing investment strategy…',
  compare_agents:  'Comparing all agents…',
  update_scenario: 'Re-running with updated parameters…',
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
