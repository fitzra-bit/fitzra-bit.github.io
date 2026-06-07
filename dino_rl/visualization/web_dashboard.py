"""Real-time training dashboard served at http://localhost:8765

Starts automatically when DQN training begins.  A background daemon thread
runs a plain-stdlib HTTP server — no new dependencies.  The page auto-refreshes
every 2 seconds by polling /data which returns the full episode history as JSON.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

PORT = 8765


class DashboardServer:
    """Thread-safe episode history store + HTTP server."""

    def __init__(self, port: int = PORT):
        self._history: list[dict] = []
        self._lock = threading.Lock()
        self._current: dict = {}
        self._port = port
        self._server: Optional[HTTPServer] = None

    # ------------------------------------------------------------------
    # Data API (called from training thread)
    # ------------------------------------------------------------------

    def push(self, stats: dict):
        """Append an episode-end stats dict.  Safe to call from any thread."""
        with self._lock:
            self._history.append(dict(stats))
            self._current = dict(stats)

    def get_data(self) -> dict:
        with self._lock:
            return {
                "history": list(self._history[-400:]),   # keep last 400 eps
                "current": dict(self._current),
                "total_episodes": len(self._history),
            }

    # ------------------------------------------------------------------
    # HTTP server
    # ------------------------------------------------------------------

    def start(self):
        srv = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("", "/"):
                    body = _HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/data":
                    body = json.dumps(srv.get_data(), default=str).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *_):  # silence request logs
                pass

        try:
            self._server = HTTPServer(("localhost", self._port), _Handler)
            t = threading.Thread(target=self._server.serve_forever, daemon=True)
            t.start()
            print(f"  Dashboard → http://localhost:{self._port}")
        except OSError as exc:
            print(f"  Dashboard unavailable (port {self._port} busy): {exc}")

    def stop(self):
        if self._server:
            self._server.shutdown()


# ---------------------------------------------------------------------------
# Single-page dashboard HTML (inlined so no static-file path issues)
# ---------------------------------------------------------------------------
_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Dino RL — Training Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6edf3;font-family:'Segoe UI',monospace;font-size:13px}

/* ---- header ---- */
#hdr{background:#161b22;border-bottom:1px solid #30363d;padding:10px 18px;
     display:flex;align-items:center;gap:20px;flex-wrap:wrap}
#hdr h1{font-size:15px;color:#58a6ff;letter-spacing:1px;white-space:nowrap}
.kpi{text-align:center;min-width:72px}
.kpi .v{font-size:20px;font-weight:bold;color:#f0f6fc}
.kpi .l{font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px}
.g .v{color:#3fb950} .c .v{color:#39d2fc} .y .v{color:#e3b341}
.r .v{color:#f85149} .p .v{color:#bc8cff}
#hdr-time{margin-left:auto;font-size:10px;color:#484f58}

/* ---- main grid ---- */
#main{display:grid;grid-template-columns:2fr 1fr;gap:10px;padding:10px}

.panel{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:12px}
.panel h2{font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:.8px;
          margin-bottom:8px}

.chart-wrap{position:relative}

/* ---- action distribution ---- */
#act-pct{display:flex;gap:0;margin-bottom:10px}
.act-chip{flex:1;text-align:center;padding:6px 0}
.act-chip .pv{font-size:26px;font-weight:bold}
.act-chip .pl{font-size:10px;color:#8b949e;text-transform:uppercase}
.an .pv{color:#8b949e} .aj .pv{color:#39d2fc} .ad .pv{color:#bc8cff}

/* ---- reward breakdown ---- */
.rw-row{display:flex;justify-content:space-between;padding:4px 2px;
        border-bottom:1px solid #21262d;font-size:12px}
.rw-row:last-child{border-bottom:none}
.rw-lbl{color:#8b949e}
.pos{color:#3fb950;font-weight:bold} .neg{color:#f85149;font-weight:bold}

/* ---- feature bars ---- */
.fb{display:flex;align-items:center;gap:6px;margin-bottom:4px;height:17px}
.fb-name{width:32px;color:#8b949e;font-size:10px;text-align:right;flex-shrink:0}
.fb-track{flex:1;background:#21262d;border-radius:2px;height:9px;overflow:hidden}
.fb-fill{height:100%;border-radius:2px;transition:width .4s}
.fb-val{width:38px;text-align:right;font-size:10px;color:#c9d1d9;flex-shrink:0}

/* ---- Q-value bars ---- */
.qb{display:flex;align-items:center;gap:6px;margin-bottom:8px}
.qb-name{width:36px;color:#8b949e;font-size:12px;flex-shrink:0}
.qb-track{flex:1;background:#21262d;border-radius:3px;height:20px;overflow:hidden;
          position:relative}
.qb-fill{height:100%;border-radius:3px;transition:width .4s}
.qb-val{width:56px;text-align:right;font-size:12px;flex-shrink:0;font-weight:bold}
.qb-chosen .qb-track{outline:2px solid #f0f6fc;border-radius:3px}

/* ---- state grid (row 3) ---- */
#state-row{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr;gap:10px}

#footer{padding:4px 12px;font-size:10px;color:#484f58;text-align:right}
</style>
</head>
<body>

<div id="hdr">
  <h1>&#11035; DINO RL</h1>
  <div class="kpi g"><div class="v" id="H-best">—</div><div class="l">Best Score</div></div>
  <div class="kpi c"><div class="v" id="H-ep">—</div><div class="l">Episode</div></div>
  <div class="kpi y"><div class="v" id="H-avg">—</div><div class="l">Avg (50ep)</div></div>
  <div class="kpi" ><div class="v" id="H-steps">—</div><div class="l">Total Steps</div></div>
  <div class="kpi g"><div class="v" id="H-clr">—</div><div class="l">Total Clears</div></div>
  <div class="kpi r"><div class="v" id="H-loss">—</div><div class="l">Loss</div></div>
  <div class="kpi p"><div class="v" id="H-eps">—</div><div class="l">Epsilon</div></div>
  <div id="hdr-time"></div>
</div>

<div id="main">

  <!-- col 1 row 1: score chart -->
  <div class="panel">
    <h2>Score Progression</h2>
    <div class="chart-wrap" style="height:180px"><canvas id="cScore"></canvas></div>
  </div>

  <!-- col 2 row 1: action distribution -->
  <div class="panel">
    <h2>Action Distribution — latest episode</h2>
    <div id="act-pct">
      <div class="act-chip an"><div class="pv" id="A-noop">—</div><div class="pl">Noop</div></div>
      <div class="act-chip aj"><div class="pv" id="A-jump">—</div><div class="pl">Jump</div></div>
      <div class="act-chip ad"><div class="pv" id="A-duck">—</div><div class="pl">Duck</div></div>
    </div>
    <h2>Action Trend — last 60 episodes</h2>
    <div class="chart-wrap" style="height:100px"><canvas id="cAction"></canvas></div>
  </div>

  <!-- col 1 row 2: loss + epsilon -->
  <div class="panel">
    <h2>Loss &amp; Epsilon Decay</h2>
    <div class="chart-wrap" style="height:150px"><canvas id="cLoss"></canvas></div>
  </div>

  <!-- col 2 row 2: reward breakdown -->
  <div class="panel">
    <h2>Reward Breakdown — latest episode</h2>
    <div id="rw-list">
      <div class="rw-row"><span class="rw-lbl">Survival reward</span> <span class="pos" id="R-surv">—</span></div>
      <div class="rw-row"><span class="rw-lbl">Obstacle cleared  (+50)</span><span class="pos" id="R-clr">—</span></div>
      <div class="rw-row"><span class="rw-lbl">Jump approach  (+15)</span> <span class="pos" id="R-jb">—</span></div>
      <div class="rw-row"><span class="rw-lbl">Idle action  (−8/step)</span><span class="neg" id="R-idle">—</span></div>
      <div class="rw-row"><span class="rw-lbl">Airborne spam  (−20)</span> <span class="neg" id="R-airb">—</span></div>
      <div class="rw-row"><span class="rw-lbl">Wrong duck  (−30)</span>    <span class="neg" id="R-wdck">—</span></div>
      <div class="rw-row"><span class="rw-lbl">Wrong jump  (−10)</span>    <span class="neg" id="R-wjmp">—</span></div>
      <div class="rw-row"><span class="rw-lbl">Death penalty  (−100)</span><span class="neg" id="R-dth">—</span></div>
    </div>
  </div>

  <!-- row 3 full-width: features + Q-values -->
  <div id="state-row">
    <div class="panel">
      <h2>Feature Vector — state at episode end</h2>
      <div id="feat-bars"></div>
    </div>
    <div class="panel">
      <h2>Q-Values — last network decision</h2>
      <div id="q-bars"></div>
      <h2 style="margin-top:14px">Speed at Death — last 60 episodes</h2>
      <div class="chart-wrap" style="height:80px"><canvas id="cSpeed"></canvas></div>
    </div>
  </div>

</div>
<div id="footer">auto-refresh every 2 s</div>

<script>
// ---- feature / Q-value metadata ----
const FEATS = [
  {n:'d1',  c:'#39d2fc', tip:'obs1 distance'},
  {n:'h1',  c:'#5c9eff', tip:'obs1 height'},
  {n:'w1',  c:'#5c9eff', tip:'obs1 width'},
  {n:'b1',  c:'#bc8cff', tip:'obs1 is bird'},
  {n:'d2',  c:'#39d2fc60',tip:'obs2 distance'},
  {n:'h2',  c:'#5c9eff60',tip:'obs2 height'},
  {n:'b2',  c:'#bc8cff60',tip:'obs2 is bird'},
  {n:'spd', c:'#e3b341', tip:'game speed'},
  {n:'dy',  c:'#3fb950', tip:'dino height above ground'},
  {n:'vy',  c:'#f0a050', tip:'dino vertical velocity'},
  {n:'jmp', c:'#ff7b72', tip:'dino jumping (0/1)'},
  {n:'duc', c:'#ff7b72', tip:'dino ducking (0/1)'},
  {n:'ttc', c:'#58a6ff', tip:'time-to-collision (d1/spd)'},
];
const Q_COLS = ['#8b949e','#39d2fc','#bc8cff'];
const Q_LABS = ['noop','jump','duck'];

// ---- build static DOM for feature bars ----
(function initFeatBars() {
  const el = document.getElementById('feat-bars');
  FEATS.forEach(f => {
    el.insertAdjacentHTML('beforeend', `
      <div class="fb" title="${f.tip}">
        <span class="fb-name">${f.n}</span>
        <div class="fb-track"><div class="fb-fill" id="ff-${f.n}" style="width:0%;background:${f.c}"></div></div>
        <span class="fb-val"  id="fv-${f.n}">—</span>
      </div>`);
  });
})();

(function initQBars() {
  const el = document.getElementById('q-bars');
  Q_LABS.forEach((lab, i) => {
    el.insertAdjacentHTML('beforeend', `
      <div class="qb" id="qrow-${lab}">
        <span class="qb-name">${lab}</span>
        <div class="qb-track"><div class="qb-fill" id="qf-${lab}" style="width:0%;background:${Q_COLS[i]}"></div></div>
        <span class="qb-val" id="qv-${lab}">—</span>
      </div>`);
  });
})();

// ---- Chart helpers ----
const darkGrid   = '#21262d';
const darkTick   = '#484f58';
const labelColor = '#8b949e';
const baseOpts = (extra={}) => ({
  responsive:true, maintainAspectRatio:false, animation:false,
  plugins:{ legend:{ labels:{ color:labelColor, font:{size:10}, boxWidth:10 } } },
  scales:{
    x:{ ticks:{color:darkTick, maxTicksLimit:8, font:{size:10}}, grid:{color:darkGrid} },
    y:{ ticks:{color:labelColor, font:{size:10}},                grid:{color:darkGrid}, ...extra.y },
    ...(extra.y2 ? {y2:{type:'linear',position:'right',
                        ticks:{color:'#e3b341',font:{size:10}},
                        grid:{drawOnChartArea:false},
                        min:0, max:1, ...extra.y2}} : {}),
  },
  ...extra.top,
});

function mkChart(id, type, datasets, extra={}) {
  return new Chart(document.getElementById(id), {
    type,
    data:{ labels:[], datasets },
    options: baseOpts(extra),
  });
}

const cScore = mkChart('cScore','line',[
  {label:'Score',   data:[], borderColor:'#39d2fc', backgroundColor:'#39d2fc15',
   borderWidth:1, pointRadius:1, fill:true,  tension:.3},
  {label:'Best',    data:[], borderColor:'#3fb950', backgroundColor:'transparent',
   borderWidth:2, pointRadius:0, fill:false, tension:0},
  {label:'Avg 50',  data:[], borderColor:'#e3b341', backgroundColor:'transparent',
   borderWidth:1.5, pointRadius:0, fill:false, tension:.4, borderDash:[4,4]},
]);

const cAction = mkChart('cAction','bar',[
  {label:'Noop', data:[], backgroundColor:'#8b949e80'},
  {label:'Jump', data:[], backgroundColor:'#39d2fc80'},
  {label:'Duck', data:[], backgroundColor:'#bc8cff80'},
],{
  y:{ stacked:true, min:0, max:100 },
  top:{ plugins:{ legend:{ labels:{ color:labelColor, font:{size:9}, boxWidth:8 } } } },
});
cAction.options.scales.x.stacked = true;
cAction.options.scales.y.stacked = true;

const cLoss = mkChart('cLoss','line',[
  {label:'Loss',    data:[], borderColor:'#f85149', backgroundColor:'transparent',
   borderWidth:1.5, pointRadius:0, tension:.3, yAxisID:'y'},
  {label:'Epsilon', data:[], borderColor:'#e3b341', backgroundColor:'transparent',
   borderWidth:1.5, pointRadius:0, tension:.1, yAxisID:'y2'},
],{ y2:{} });

const cSpeed = mkChart('cSpeed','line',[
  {label:'Speed at death', data:[], borderColor:'#f0a050', backgroundColor:'#f0a05025',
   borderWidth:1.5, pointRadius:2, fill:true, tension:.3},
]);

// ---- utilities ----
function rollingAvg(arr, n) {
  return arr.map((_, i) => {
    const sl = arr.slice(Math.max(0, i - n + 1), i + 1);
    return sl.reduce((a, b) => a + b, 0) / sl.length;
  });
}
const fmt1 = v => (v >= 0 ? '+' : '') + v.toFixed(1);
const fmtK = v => v >= 1000 ? (v/1000).toFixed(1)+'k' : String(v);

// ---- main render ----
function render(data) {
  const h = data.history;
  const c = data.current || {};
  if (!h.length) return;

  // Header
  const scr50  = h.slice(-50).map(e => e.score || 0);
  const avg50  = scr50.length ? (scr50.reduce((a,b)=>a+b,0)/scr50.length).toFixed(0) : '—';
  const totClr = h.reduce((s,e) => s + (e.cleared||0), 0);
  document.getElementById('H-best').textContent  = (c.best||0).toFixed(0);
  document.getElementById('H-ep').textContent    = data.total_episodes;
  document.getElementById('H-avg').textContent   = avg50;
  document.getElementById('H-steps').textContent = fmtK(c.total_steps||0);
  document.getElementById('H-clr').textContent   = totClr;
  document.getElementById('H-loss').textContent  = (c.loss||0).toFixed(2);
  document.getElementById('H-eps').textContent   = (c.epsilon||1).toFixed(3);
  document.getElementById('hdr-time').textContent= new Date().toLocaleTimeString();

  // Score chart
  const eps    = h.map(e => e.episode);
  const scores = h.map(e => e.score||0);
  const bests  = h.map(e => e.best||0);
  cScore.data.labels           = eps;
  cScore.data.datasets[0].data = scores;
  cScore.data.datasets[1].data = bests;
  cScore.data.datasets[2].data = rollingAvg(scores, 50);
  cScore.update('none');

  // Action trend (last 60 ep)
  const act60 = h.slice(-60);
  const apOf  = (e, k) => (e.action_pct||{})[k]||0;
  cAction.data.labels           = act60.map(e=>e.episode);
  cAction.data.datasets[0].data = act60.map(e=>apOf(e,'noop'));
  cAction.data.datasets[1].data = act60.map(e=>apOf(e,'jump'));
  cAction.data.datasets[2].data = act60.map(e=>apOf(e,'duck'));
  cAction.update('none');

  // Action chips (latest ep)
  const ap = c.action_pct || {};
  document.getElementById('A-noop').textContent = (ap.noop||0).toFixed(1)+'%';
  document.getElementById('A-jump').textContent = (ap.jump||0).toFixed(1)+'%';
  document.getElementById('A-duck').textContent = (ap.duck||0).toFixed(1)+'%';

  // Loss + Epsilon (last 100 ep)
  const l100 = h.slice(-100);
  cLoss.data.labels           = l100.map(e=>e.episode);
  cLoss.data.datasets[0].data = l100.map(e=>e.loss||0);
  cLoss.data.datasets[1].data = l100.map(e=>e.epsilon||1);
  cLoss.update('none');

  // Speed at death (last 60 ep)
  const s60 = h.slice(-60);
  cSpeed.data.labels           = s60.map(e=>e.episode);
  cSpeed.data.datasets[0].data = s60.map(e=>e.speed_at_death||0);
  cSpeed.update('none');

  // Reward breakdown
  const sr = c.shaped_rewards || {};
  document.getElementById('R-surv').textContent = fmt1(sr.survival||0);
  document.getElementById('R-clr').textContent  = fmt1(sr.clearing||0);
  document.getElementById('R-jb').textContent   = fmt1(sr.jump_bonus||0);
  document.getElementById('R-idle').textContent = fmt1(sr.idle||0);
  document.getElementById('R-airb').textContent = fmt1(sr.airborne||0);
  document.getElementById('R-wdck').textContent = fmt1(sr.wrong_duck||0);
  document.getElementById('R-wjmp').textContent = fmt1(sr.wrong_jump||0);
  document.getElementById('R-dth').textContent  = fmt1(sr.death||0);

  // Feature vector
  const obs = c.obs_vector || [];
  FEATS.forEach((f, i) => {
    const v   = obs[i] != null ? obs[i] : 0;
    const pct = Math.min(Math.max(v, 0), 1) * 100;
    document.getElementById('ff-'+f.n).style.width = pct + '%';
    document.getElementById('fv-'+f.n).textContent  = v.toFixed(3);
  });

  // Q-values
  const qv = c.q_values || [0, 0, 0];
  const mx = Math.max(...qv.map(Math.abs)) || 1;
  const best_q_idx = qv.indexOf(Math.max(...qv));
  Q_LABS.forEach((lab, i) => {
    const pct = Math.min(Math.abs(qv[i]) / mx * 100, 100);
    document.getElementById('qf-'+lab).style.width = pct + '%';
    document.getElementById('qv-'+lab).textContent  = qv[i].toFixed(3);
    const row = document.getElementById('qrow-'+lab);
    row.classList.toggle('qb-chosen', i === best_q_idx);
  });
}

// ---- poll loop ----
async function poll() {
  try {
    const r = await fetch('/data');
    if (r.ok) render(await r.json());
    else document.getElementById('footer').textContent = 'waiting for training…';
  } catch(_) {
    document.getElementById('footer').textContent = 'waiting for training…';
  }
  setTimeout(poll, 2000);
}

poll();
</script>
</body>
</html>"""
