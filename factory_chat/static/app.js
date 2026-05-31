/* OptiFlow frontend — streaming chat + live results panel */

const SESSION_ID = crypto.randomUUID();

const messagesEl = document.getElementById('messages');
const inputEl    = document.getElementById('input');
const sendBtn    = document.getElementById('btn-send');
const resultsBody = document.getElementById('results-body');
const resultsTitle = document.getElementById('results-title');
const resultsStatus = document.getElementById('results-status');

let isBusy = false;

// ── Tool label map ──────────────────────────────────────────────
const TOOL_LABELS = {
  create_scenario: 'Building simulation model…',
  run_baseline:    'Running baseline simulation…',
  run_optimizer:   'Optimizing investment strategy…',
  compare_agents:  'Running all agents for comparison…',
  update_scenario: 'Updating scenario and re-optimizing…',
};

// ── Utilities ───────────────────────────────────────────────────

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setBusy(busy) {
  isBusy = busy;
  sendBtn.disabled = busy;
  inputEl.disabled = busy;
}

function autoResize() {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
}

// ── Message creation ─────────────────────────────────────────────

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
  const bubble = createMessage('user');
  bubble.textContent = text;
}

function createAssistantBubble() {
  return createMessage('assistant');
}

function renderMarkdown(bubble, text) {
  bubble.innerHTML = marked.parse(text);
}

// ── Tool call indicators ─────────────────────────────────────────

function createToolCallEl(toolName) {
  const el = document.createElement('div');
  el.className = 'tool-call';
  el.dataset.toolId = toolName + '_' + Date.now();
  el.innerHTML = `
    <div class="spinner"></div>
    <span class="tool-name">${toolName}</span>
    <span>${TOOL_LABELS[toolName] || 'Running…'}</span>`;
  messagesEl.appendChild(el);
  scrollToBottom();
  return el;
}

function markToolDone(el) {
  el.classList.add('done');
  el.querySelector('.spinner').style.animation = 'none';
  el.querySelector('.spinner').style.borderTopColor = 'var(--green)';
}

// ── Results panel ────────────────────────────────────────────────

let resultsFrame = null;
let loadingOverlay = null;
let activeToolEls = {};

function showResultsLoading(toolName) {
  resultsTitle.textContent = TOOL_LABELS[toolName] || 'Running…';
  resultsStatus.innerHTML = '<span class="status-dot"></span> Running';

  if (!loadingOverlay) {
    loadingOverlay = document.createElement('div');
    loadingOverlay.className = 'results-loading';
    loadingOverlay.innerHTML = `
      <div class="loading-ring"></div>
      <div class="loading-label">${TOOL_LABELS[toolName] || 'Running simulation…'}</div>`;
    resultsBody.appendChild(loadingOverlay);
  } else {
    loadingOverlay.querySelector('.loading-label').textContent =
      TOOL_LABELS[toolName] || 'Running…';
    loadingOverlay.style.display = 'flex';
  }
}

function hideResultsLoading() {
  if (loadingOverlay) loadingOverlay.style.display = 'none';
}

function setResultsHtml(html, toolName) {
  hideResultsLoading();

  // Remove empty state
  const empty = resultsBody.querySelector('.results-empty');
  if (empty) empty.remove();

  // Replace or create iframe
  if (!resultsFrame) {
    resultsFrame = document.createElement('iframe');
    resultsFrame.id = 'results-frame';
    resultsFrame.setAttribute('sandbox', 'allow-same-origin allow-scripts');
    resultsBody.appendChild(resultsFrame);
  }

  resultsFrame.srcdoc = html;
  resultsTitle.textContent = TOOL_LABELS[toolName]?.replace('…', '') || 'Simulation Output';
  resultsStatus.innerHTML = '<span class="status-dot"></span> Ready';
}

// ── Main send logic ──────────────────────────────────────────────

async function send(text) {
  if (!text.trim() || isBusy) return;
  setBusy(true);

  appendUserMessage(text);
  inputEl.value = '';
  autoResize();

  // Prepare Claude's response bubble
  const bubble = createAssistantBubble();
  const cursor = document.createElement('span');
  cursor.className = 'cursor';
  bubble.appendChild(cursor);

  let assistantText = '';
  let toolElMap = {};

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
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        let event;
        try { event = JSON.parse(line.slice(6)); } catch { continue; }

        switch (event.type) {
          case 'text':
            assistantText += event.delta;
            renderMarkdown(bubble, assistantText);
            bubble.appendChild(cursor);
            scrollToBottom();
            break;

          case 'tool_start': {
            const el = createToolCallEl(event.name);
            toolElMap[event.name] = el;
            showResultsLoading(event.name);
            break;
          }

          case 'tool_result_html':
            setResultsHtml(event.html, event.tool_name);
            if (toolElMap[event.tool_name]) {
              markToolDone(toolElMap[event.tool_name]);
            }
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
    // Final markdown render without cursor
    if (assistantText) renderMarkdown(bubble, assistantText);
    hideResultsLoading();
    setBusy(false);
    scrollToBottom();
  }
}

// ── Events ───────────────────────────────────────────────────────

sendBtn.addEventListener('click', () => send(inputEl.value));

inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    send(inputEl.value);
  }
});

inputEl.addEventListener('input', autoResize);

document.getElementById('btn-new').addEventListener('click', async () => {
  if (isBusy) return;
  await fetch('/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: SESSION_ID }),
  });
  location.reload();
});

document.getElementById('btn-load-example').addEventListener('click', () => {
  if (isBusy) return;
  const example = `I run a 5-step widget manufacturing operation.

Step 1 — Raw Material Prep: runs at about 160 units/hour, 98% yield. Labor and materials cost around $2,000/month.

Step 2 — CNC Machining: this is our problem area. We're only getting 80 units/hour and our scrap rate is around 9% (so 91% yield). Machine time and tooling runs about $7,000/month.

Step 3 — Heat Treatment: 130 units/hour, 97% yield, $4,500/month in energy and labor.

Step 4 — Quality Inspection: 110 units/hour, 99% yield, $3,200/month.

Step 5 — Packaging & Dispatch: 220 units/hour, 100% yield, $1,800/month.

Each widget sells for $85. We work standard hours — about 176 hours a month. We have $350,000 available for capital investment and want to understand where to put it over the next 2 years.`;

  inputEl.value = example;
  autoResize();
  inputEl.focus();
});

// ── Init ─────────────────────────────────────────────────────────
inputEl.focus();
