/**
 * Configurator — interactive investment workspace.
 *
 * Takes a scenario JSON from Claude, renders:
 *   - SVG process flow (clickable steps, bottleneck highlight)
 *   - Upgrade cards per step (toggle to pre-commit investments)
 *   - Live budget & projection bar (pure JS math, no server call)
 *   - YAML editor (editable, synced to model, validated live)
 *   - Run button → calls onRun(yamlText, selectedUpgrades, agent)
 */

class Configurator {
  constructor(container, { onRun, sessionId }) {
    this.container = container;
    this.onRun = onRun;
    this.sessionId = sessionId;

    this.scenario = null;       // source of truth — updated by YAML edits
    this.yamlText = '';         // current editor text
    this.selectedUpgrades = {}; // { "stepIdx:upgradeId": count }
    this.selectedStep = 0;
    this.yamlError = null;
    this._validateTimer = null;
  }

  // ── Public ─────────────────────────────────────────────────────

  load(scenarioJson) {
    this.scenario = JSON.parse(JSON.stringify(scenarioJson)); // deep clone
    this.selectedUpgrades = {};
    this.selectedStep = 0;
    this.yamlError = null;
    this.yamlText = this._toYaml(this.scenario);
    this._render();
  }

  // ── Rendering ──────────────────────────────────────────────────

  _render() {
    this.container.innerHTML = `
      <div class="cfg-layout">
        <div class="cfg-flow-section">
          <div class="cfg-section-label">Process Flow — click a step to see upgrade options</div>
          <div id="cfg-flow"></div>
        </div>
        <div class="cfg-middle">
          <div class="cfg-upgrades-panel">
            <div class="cfg-section-label" id="cfg-upgrades-label">Upgrade Options</div>
            <div id="cfg-upgrade-cards"></div>
          </div>
          <div class="cfg-yaml-panel">
            <div class="cfg-section-label">
              Scenario YAML
              <span class="yaml-hint">— edit to adjust parameters before running</span>
            </div>
            <div class="yaml-editor-wrap">
              <textarea id="cfg-yaml" spellcheck="false"></textarea>
              <div class="yaml-error-bar" id="cfg-yaml-error"></div>
            </div>
          </div>
        </div>
        <div class="cfg-bottom">
          <div class="cfg-projections" id="cfg-projections"></div>
          <div class="cfg-run-controls">
            <select id="cfg-agent-select">
              <option value="greedy">Greedy ROI (instant)</option>
              <option value="dqn">Deep Q-Network (thorough)</option>
            </select>
            <button class="btn-run" id="cfg-run-btn">
              Run Optimization →
            </button>
          </div>
        </div>
      </div>`;

    this._renderFlow();
    this._renderUpgrades();
    this._renderProjections();
    this._bindYaml();
    this._bindRun();
  }

  // ── Process flow (SVG) ─────────────────────────────────────────

  _renderFlow() {
    const el = document.getElementById('cfg-flow');
    if (!el || !this.scenario) return;

    const steps = this.scenario.steps;
    const n = steps.length;
    const BOX_W = 150, BOX_H = 88, GAP = 40;
    const ARROW = 28;
    const totalW = n * BOX_W + (n - 1) * (GAP + ARROW);
    const H = BOX_H + 24;

    // Find bottleneck (min capacity step after applying selected upgrades)
    const proj = this._projectLine();
    const bnIdx = proj.bottleneckIdx;

    let svg = `<svg viewBox="0 0 ${totalW} ${H}" xmlns="http://www.w3.org/2000/svg"
      style="width:100%;max-height:130px;overflow:visible">
      <defs>
        <marker id="arr" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0,8 3,0 6" fill="#2a2a3e"/>
        </marker>
      </defs>`;

    steps.forEach((step, i) => {
      const x = i * (BOX_W + GAP + ARROW);
      const projStep = proj.steps[i];
      const isBottleneck = i === bnIdx;
      const isSelected = i === this.selectedStep;

      // Count selected upgrades for this step
      const hasSelected = Object.keys(this.selectedUpgrades)
        .some(k => k.startsWith(`${i}:`) && this.selectedUpgrades[k] > 0);

      const stroke = isBottleneck ? '#f38ba8' : isSelected ? '#89b4fa' : '#2a2a3e';
      const strokeW = (isBottleneck || isSelected) ? 2.5 : 1.5;
      const capPct = Math.min(100, (projStep.capacity / proj.maxCapacity) * 100);
      const yieldPct = projStep.yield_rate * 100;

      svg += `
        <g class="flow-step${isSelected ? ' selected' : ''}" data-idx="${i}"
           style="cursor:pointer" tabindex="0">
          <rect x="${x}" y="12" width="${BOX_W}" height="${BOX_H}" rx="8"
            fill="#1a1a2a" stroke="${stroke}" stroke-width="${strokeW}"/>
          ${isBottleneck ? `<rect x="${x}" y="12" width="${BOX_W}" height="4" rx="2" fill="#f38ba8" opacity=".7"/>` : ''}
          ${hasSelected ? `<circle cx="${x + BOX_W - 10}" cy="22" r="5" fill="#a6e3a1"/>` : ''}
          <text x="${x + BOX_W/2}" y="36" text-anchor="middle"
            fill="${isBottleneck ? '#f38ba8' : '#cdd6f4'}"
            font-size="12" font-weight="600" font-family="system-ui">${this._truncate(step.name, 16)}</text>
          ${isBottleneck ? `<text x="${x + BOX_W/2}" y="50" text-anchor="middle"
            fill="#f38ba8" font-size="9" font-family="system-ui">◄ BOTTLENECK</text>` : ''}
          <!-- Capacity bar -->
          <rect x="${x+10}" y="${isBottleneck ? 56 : 46}" width="${BOX_W-20}" height="6" rx="3" fill="#2a2a3e"/>
          <rect x="${x+10}" y="${isBottleneck ? 56 : 46}" width="${((BOX_W-20)*capPct/100).toFixed(1)}" height="6" rx="3" fill="#89b4fa"/>
          <text x="${x + BOX_W/2}" y="${isBottleneck ? 74 : 64}" text-anchor="middle"
            fill="#6c7086" font-size="10" font-family="monospace">
            ${projStep.capacity.toFixed(0)} u/h · ${yieldPct.toFixed(1)}%
          </text>
          <text x="${x + BOX_W/2}" y="${isBottleneck ? 88 : 78}" text-anchor="middle"
            fill="#45475a" font-size="9" font-family="monospace">
            OPEX ${this._fmtMoney(projStep.opex)}/pd
          </text>
        </g>`;

      // Arrow to next step
      if (i < n - 1) {
        const ax = x + BOX_W;
        const ay = 12 + BOX_H / 2;
        svg += `<line x1="${ax}" y1="${ay}" x2="${ax + GAP + ARROW - 6}" y2="${ay}"
          stroke="#2a2a3e" stroke-width="2" marker-end="url(#arr)"/>`;
      }
    });

    svg += '</svg>';
    el.innerHTML = svg;

    // Click handlers
    el.querySelectorAll('.flow-step').forEach(g => {
      g.addEventListener('click', () => {
        this.selectedStep = parseInt(g.dataset.idx);
        this._renderFlow();
        this._renderUpgrades();
      });
    });
  }

  // ── Upgrade cards ───────────────────────────────────────────────

  _renderUpgrades() {
    const label = document.getElementById('cfg-upgrades-label');
    const cards = document.getElementById('cfg-upgrade-cards');
    if (!cards || !this.scenario) return;

    const step = this.scenario.steps[this.selectedStep];
    if (label) label.textContent = `${step.name} — Upgrade Options`;

    if (!step.upgrades || step.upgrades.length === 0) {
      cards.innerHTML = '<p class="cfg-no-upgrades">No upgrades defined for this step.</p>';
      return;
    }

    cards.innerHTML = step.upgrades.map((u, ui) => {
      const key = `${this.selectedStep}:${u.id}`;
      const count = this.selectedUpgrades[key] || 0;
      const maxApps = u.max_applications || 1;
      const isSelected = count > 0;
      const isFull = count >= maxApps;

      const impactLines = [];
      if (u.capacity_delta) impactLines.push(
        `<span class="tag-blue">+${u.capacity_delta} u/h</span>`);
      if (u.yield_delta) impactLines.push(
        `<span class="tag-green">+${(u.yield_delta*100).toFixed(1)}% yield</span>`);
      if (u.opex_delta > 0) impactLines.push(
        `<span class="tag-red">+${this._fmtMoney(u.opex_delta)}/pd OPEX</span>`);
      if (u.opex_delta < 0) impactLines.push(
        `<span class="tag-green">${this._fmtMoney(u.opex_delta)}/pd OPEX</span>`);

      const roi = this._estimateROI(u, this.selectedStep);
      const roiStr = roi !== null
        ? `<div class="upgrade-roi">Est. payback: <strong>${roi < 0 ? 'N/A' : roi.toFixed(1) + ' pd'}</strong></div>`
        : '';

      return `
        <div class="upgrade-card${isSelected ? ' selected' : ''}" data-step="${this.selectedStep}" data-uid="${u.id}">
          <div class="upgrade-card-top">
            <div class="upgrade-name">${u.name}</div>
            ${maxApps > 1 ? `<div class="upgrade-count">${count}/${maxApps}</div>` : ''}
          </div>
          ${u.description ? `<div class="upgrade-desc">${u.description}</div>` : ''}
          <div class="upgrade-impacts">${impactLines.join(' ')}</div>
          <div class="upgrade-costs">
            <span class="cost-capex">CAPEX: ${this._fmtMoney(u.capex)}</span>
            ${u.opex_delta ? `<span class="cost-opex">OPEX Δ: ${this._fmtMoney(u.opex_delta)}/pd</span>` : ''}
          </div>
          ${roiStr}
          <div class="upgrade-actions">
            ${count > 0 ? `<button class="btn-remove" data-step="${this.selectedStep}" data-uid="${u.id}">− Remove</button>` : ''}
            ${!isFull ? `<button class="btn-add" data-step="${this.selectedStep}" data-uid="${u.id}">+ Add${maxApps > 1 ? ` (${count+1}/${maxApps})` : ''}</button>` : ''}
            ${isFull ? `<span class="tag-green" style="font-size:.75rem">✓ Max applied</span>` : ''}
          </div>
        </div>`;
    }).join('');

    cards.querySelectorAll('.btn-add').forEach(btn => {
      btn.addEventListener('click', () => {
        const stepIdx = parseInt(btn.dataset.step);
        const uid = btn.dataset.uid;
        const upg = this.scenario.steps[stepIdx].upgrades.find(u => u.id === uid);
        const key = `${stepIdx}:${uid}`;
        const curr = this.selectedUpgrades[key] || 0;
        if (curr < (upg.max_applications || 1)) {
          this.selectedUpgrades[key] = curr + 1;
          this._renderUpgrades();
          this._renderFlow();
          this._renderProjections();
        }
      });
    });

    cards.querySelectorAll('.btn-remove').forEach(btn => {
      btn.addEventListener('click', () => {
        const key = `${btn.dataset.step}:${btn.dataset.uid}`;
        const curr = this.selectedUpgrades[key] || 0;
        if (curr > 1) this.selectedUpgrades[key] = curr - 1;
        else delete this.selectedUpgrades[key];
        this._renderUpgrades();
        this._renderFlow();
        this._renderProjections();
      });
    });
  }

  // ── Projections bar ─────────────────────────────────────────────

  _renderProjections() {
    const el = document.getElementById('cfg-projections');
    if (!el || !this.scenario) return;

    const base = this._projectLine(false);  // no selected upgrades
    const proj = this._projectLine(true);   // with selected upgrades
    const totalCapex = this._selectedCapex();
    const budget = this.scenario.budget;
    const budgetPct = Math.min(100, (totalCapex / budget) * 100);

    const deltaProfit = proj.profitPerPeriod - base.profitPerPeriod;
    const payback = deltaProfit > 0 ? (totalCapex / deltaProfit).toFixed(1) : '—';
    const roi = deltaProfit > 0 && totalCapex > 0
      ? (((deltaProfit * this.scenario.periods) - totalCapex) / totalCapex * 100).toFixed(0)
      : '—';

    el.innerHTML = `
      <div class="proj-budget">
        <div class="proj-label">Budget committed</div>
        <div class="proj-bar-wrap">
          <div class="proj-bar" style="width:${budgetPct.toFixed(1)}%"></div>
        </div>
        <div class="proj-budget-text">
          <strong>${this._fmtMoney(totalCapex)}</strong> of ${this._fmtMoney(budget)}
          <span class="proj-remaining">(${this._fmtMoney(budget - totalCapex)} remaining for RL)</span>
        </div>
      </div>
      <div class="proj-metrics">
        <div class="proj-metric">
          <div class="proj-metric-label">Throughput</div>
          <div class="proj-metric-value ${proj.throughput > base.throughput ? 'green' : ''}">
            ${proj.throughput.toFixed(0)} u/h
            ${proj.throughput > base.throughput ? `<span class="delta">+${(proj.throughput-base.throughput).toFixed(0)}</span>` : ''}
          </div>
        </div>
        <div class="proj-metric">
          <div class="proj-metric-label">Eff. Yield</div>
          <div class="proj-metric-value ${proj.yield > base.yield ? 'green' : ''}">
            ${(proj.yield*100).toFixed(1)}%
            ${proj.yield > base.yield ? `<span class="delta">+${((proj.yield-base.yield)*100).toFixed(1)}pp</span>` : ''}
          </div>
        </div>
        <div class="proj-metric">
          <div class="proj-metric-label">Profit/period</div>
          <div class="proj-metric-value ${deltaProfit > 0 ? 'green' : ''}">
            ${this._fmtMoney(proj.profitPerPeriod)}
            ${deltaProfit > 0 ? `<span class="delta">+${this._fmtMoney(deltaProfit)}</span>` : ''}
          </div>
        </div>
        <div class="proj-metric">
          <div class="proj-metric-label">Payback</div>
          <div class="proj-metric-value">${payback}${payback !== '—' ? ' pd' : ''}</div>
        </div>
        <div class="proj-metric">
          <div class="proj-metric-label">ROI (${this.scenario.periods}pd)</div>
          <div class="proj-metric-value ${roi !== '—' && parseFloat(roi) > 0 ? 'green' : ''}">${roi}${roi !== '—' ? '%' : ''}</div>
        </div>
      </div>`;
  }

  // ── YAML editor ────────────────────────────────────────────────

  _bindYaml() {
    const ta = document.getElementById('cfg-yaml');
    if (!ta) return;
    ta.value = this.yamlText;

    ta.addEventListener('input', () => {
      this.yamlText = ta.value;
      clearTimeout(this._validateTimer);
      this._validateTimer = setTimeout(() => this._validateYaml(), 600);
    });
  }

  async _validateYaml() {
    const errBar = document.getElementById('cfg-yaml-error');
    try {
      const resp = await fetch('/validate-yaml', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml_text: this.yamlText }),
      });
      const data = await resp.json();
      if (data.valid) {
        if (errBar) errBar.textContent = `✓ Valid — ${data.steps} steps · budget ${this._fmtMoney(data.budget)} · bottleneck: ${data.bottleneck}`;
        if (errBar) errBar.className = 'yaml-error-bar ok';
        // Sync scenario from YAML for projection recalculation
        this._syncScenarioFromYaml();
      } else {
        if (errBar) errBar.textContent = `✗ ${data.error}`;
        if (errBar) errBar.className = 'yaml-error-bar error';
      }
    } catch (e) {
      if (errBar) { errBar.textContent = `✗ Parse error`; errBar.className = 'yaml-error-bar error'; }
    }
  }

  _syncScenarioFromYaml() {
    // Best-effort: parse YAML client-side with jsyaml to update scenario for live projections
    try {
      const raw = jsyaml.load(this.yamlText);
      const sc = raw.scenario || raw;
      const steps = sc.steps || raw.steps || [];
      // Update only the numeric fields that affect projections
      this.scenario.unit_value = sc.unit_value || this.scenario.unit_value;
      this.scenario.budget = sc.budget || this.scenario.budget;
      this.scenario.hours_per_period = sc.hours_per_period || this.scenario.hours_per_period;
      this.scenario.periods = sc.periods || this.scenario.periods;
      steps.forEach((rawStep, i) => {
        if (this.scenario.steps[i]) {
          this.scenario.steps[i].capacity = rawStep.capacity || this.scenario.steps[i].capacity;
          this.scenario.steps[i].yield_rate = rawStep.yield_rate || this.scenario.steps[i].yield_rate;
        }
      });
      this._renderFlow();
      this._renderProjections();
    } catch (e) { /* invalid yaml mid-edit, ignore */ }
  }

  // ── Run button ─────────────────────────────────────────────────

  _bindRun() {
    const btn = document.getElementById('cfg-run-btn');
    const sel = document.getElementById('cfg-agent-select');
    if (!btn) return;

    btn.addEventListener('click', () => {
      const agent = sel ? sel.value : 'greedy';
      const selected = Object.entries(this.selectedUpgrades)
        .filter(([, count]) => count > 0)
        .map(([key, count]) => {
          const [stepIdx, upgradeId] = key.split(':');
          return { step_idx: parseInt(stepIdx), upgrade_id: upgradeId, count };
        });
      this.onRun(this.yamlText, selected, agent);
    });
  }

  // ── Pure-JS projection math ─────────────────────────────────────

  _projectLine(withSelected = true) {
    if (!this.scenario) return { throughput: 0, yield: 0, profitPerPeriod: 0, steps: [], bottleneckIdx: 0, maxCapacity: 1 };

    const steps = this.scenario.steps.map((s, i) => {
      let capacity = s.capacity;
      let yield_rate = s.yield_rate;
      let opex = s.base_opex || 0;

      if (withSelected) {
        (s.upgrades || []).forEach(u => {
          const key = `${i}:${u.id}`;
          const count = this.selectedUpgrades[key] || 0;
          capacity += u.capacity_delta * count;
          yield_rate = Math.min(1, yield_rate + u.yield_delta * count);
          opex += u.opex_delta * count;
        });
      }
      return { name: s.name, capacity, yield_rate, opex };
    });

    const bnIdx = steps.reduce((bi, s, i) => s.capacity < steps[bi].capacity ? i : bi, 0);
    const throughput = steps[bnIdx].capacity;
    const effYield = steps.reduce((y, s) => y * s.yield_rate, 1);
    const netOutput = throughput * effYield * (this.scenario.hours_per_period || 176);
    const revenue = netOutput * (this.scenario.unit_value || 0);
    const opex = steps.reduce((sum, s) => sum + s.opex, 0);
    const profit = revenue - opex;
    const maxCapacity = Math.max(...steps.map(s => s.capacity));

    return { throughput, yield: effYield, profitPerPeriod: profit, steps, bottleneckIdx: bnIdx, maxCapacity };
  }

  _selectedCapex() {
    let total = 0;
    for (const [key, count] of Object.entries(this.selectedUpgrades)) {
      const [stepIdx, uid] = key.split(':');
      const step = this.scenario.steps[parseInt(stepIdx)];
      const upg = (step?.upgrades || []).find(u => u.id === uid);
      if (upg) total += upg.capex * count;
    }
    return total;
  }

  _estimateROI(upgrade, stepIdx) {
    if (!upgrade.capex || upgrade.capex === 0) return null;
    const before = this._projectLine(true);

    // Temporarily add this upgrade
    const key = `${stepIdx}:${upgrade.id}`;
    const wasCount = this.selectedUpgrades[key] || 0;
    const step = this.scenario.steps[stepIdx];
    const maxApps = upgrade.max_applications || 1;
    if (wasCount >= maxApps) return null;

    this.selectedUpgrades[key] = wasCount + 1;
    const after = this._projectLine(true);
    this.selectedUpgrades[key] = wasCount; // restore
    if (wasCount === 0) delete this.selectedUpgrades[key];

    const delta = after.profitPerPeriod - before.profitPerPeriod;
    if (delta <= 0) return -1;
    return upgrade.capex / delta; // periods to payback
  }

  // ── Helpers ────────────────────────────────────────────────────

  _fmtMoney(v) {
    if (Math.abs(v) >= 1_000_000) return `$${(v/1_000_000).toFixed(1)}M`;
    if (Math.abs(v) >= 1_000) return `$${(v/1_000).toFixed(0)}K`;
    return `$${v.toFixed(0)}`;
  }

  _truncate(str, n) {
    return str.length > n ? str.slice(0, n - 1) + '…' : str;
  }

  _toYaml(scenario) {
    // Build YAML string from scenario JSON
    const sc = {
      name: scenario.name,
      ...(scenario.description ? { description: scenario.description } : {}),
      unit: scenario.unit || 'unit',
      unit_value: scenario.unit_value,
      budget: scenario.budget,
      hours_per_period: scenario.hours_per_period || 176,
      periods: scenario.periods || 24,
    };

    const stepsData = scenario.steps.map(s => ({
      id: s.id,
      name: s.name,
      capacity: s.capacity,
      yield_rate: s.yield_rate,
      base_opex: s.base_opex || 0,
      upgrades: (s.upgrades || []).map(u => ({
        id: u.id,
        name: u.name,
        capex: u.capex,
        ...(u.opex_delta ? { opex_delta: u.opex_delta } : {}),
        ...(u.capacity_delta ? { capacity_delta: u.capacity_delta } : {}),
        ...(u.yield_delta ? { yield_delta: u.yield_delta } : {}),
        ...(u.max_applications > 1 ? { max_applications: u.max_applications } : {}),
        ...(u.description ? { description: u.description } : {}),
      })),
    }));

    // Manual YAML construction for readability (no extra library needed)
    const lines = ['scenario:'];
    for (const [k, v] of Object.entries(sc)) {
      if (typeof v === 'string' && v.includes('\n')) {
        lines.push(`  ${k}: |`);
        v.split('\n').forEach(l => lines.push(`    ${l}`));
      } else {
        lines.push(`  ${k}: ${JSON.stringify(v)}`);
      }
    }
    lines.push('', 'steps:');
    stepsData.forEach(s => {
      lines.push(`  - id: ${s.id}`);
      lines.push(`    name: ${JSON.stringify(s.name)}`);
      lines.push(`    capacity: ${s.capacity}`);
      lines.push(`    yield_rate: ${s.yield_rate}`);
      lines.push(`    base_opex: ${s.base_opex}`);
      if (s.upgrades.length) {
        lines.push(`    upgrades:`);
        s.upgrades.forEach(u => {
          lines.push(`      - id: ${u.id}`);
          lines.push(`        name: ${JSON.stringify(u.name)}`);
          lines.push(`        capex: ${u.capex}`);
          if (u.opex_delta) lines.push(`        opex_delta: ${u.opex_delta}`);
          if (u.capacity_delta) lines.push(`        capacity_delta: ${u.capacity_delta}`);
          if (u.yield_delta) lines.push(`        yield_delta: ${u.yield_delta}`);
          if (u.max_applications) lines.push(`        max_applications: ${u.max_applications}`);
          if (u.description) lines.push(`        description: ${JSON.stringify(u.description)}`);
        });
      }
    });
    return lines.join('\n');
  }
}
