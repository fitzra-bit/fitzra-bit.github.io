"""Real-time training dashboard served at http://localhost:8765

Starts automatically when DQN training begins.  A background daemon thread
runs a plain-stdlib HTTP server — no new dependencies.  The page auto-refreshes
every 2 seconds by polling /data which returns the full episode history as JSON.

The view is organised around the numbers that actually drive the run:
  * GREEDY EVAL (eval_avg / eval_best) — every control decision keys off this,
    not the ε-contaminated training score.
  * EVAL DEATH CAUSES — what is actually killing the policy (cactus vs which
    bird height), the single most diagnostic panel.
  * ACTION MIX — jump / duck / run-under usage (the bird-strategy tell).
  * curriculum phase, ε decay, loss, throughput.
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
                "history": list(self._history[-600:]),   # keep last 600 eps
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

#hdr{background:#161b22;border-bottom:1px solid #30363d;padding:10px 18px;
     display:flex;align-items:center;gap:18px;flex-wrap:wrap}
#hdr h1{font-size:15px;color:#58a6ff;letter-spacing:1px;white-space:nowrap}
.kpi{text-align:center;min-width:70px}
.kpi .v{font-size:20px;font-weight:bold;color:#f0f6fc}
.kpi .l{font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px}
.g .v{color:#3fb950} .c .v{color:#39d2fc} .y .v{color:#e3b341}
.r .v{color:#f85149} .p .v{color:#bc8cff}
#modes{display:flex;gap:6px;flex-wrap:wrap}
.mode{font-size:10px;padding:2px 7px;border-radius:10px;background:#21262d;color:#6e7681;
      border:1px solid #30363d;text-transform:uppercase;letter-spacing:.5px}
.mode.on{background:#15301d;color:#3fb950;border-color:#238636}
#hdr-time{margin-left:auto;font-size:10px;color:#484f58}

#main{display:grid;grid-template-columns:2fr 1fr;gap:10px;padding:10px}
.panel{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:12px}
.panel h2{font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px}
.panel .sub{font-size:10px;color:#6e7681;margin-bottom:8px}
.chart-wrap{position:relative}

#act-pct{display:flex;gap:0;margin-bottom:10px}
.act-chip{flex:1;text-align:center;padding:6px 0}
.act-chip .pv{font-size:24px;font-weight:bold}
.act-chip .pl{font-size:10px;color:#8b949e;text-transform:uppercase}
.an .pv{color:#8b949e} .aj .pv{color:#39d2fc} .ad .pv{color:#bc8cff}

/* death-cause bars */
.dc{display:flex;align-items:center;gap:8px;margin-bottom:7px;height:18px}
.dc-name{width:96px;color:#c9d1d9;font-size:11px;flex-shrink:0}
.dc-track{flex:1;background:#21262d;border-radius:3px;height:14px;overflow:hidden}
.dc-fill{height:100%;border-radius:3px;transition:width .4s}
.dc-val{width:30px;text-align:right;font-size:11px;color:#c9d1d9;flex-shrink:0}
.dc-hint{font-size:9px;color:#6e7681;margin-left:4px}

.qb{display:flex;align-items:center;gap:6px;margin-bottom:8px}
.qb-name{width:36px;color:#8b949e;font-size:12px;flex-shrink:0}
.qb-track{flex:1;background:#21262d;border-radius:3px;height:20px;overflow:hidden}
.qb-fill{height:100%;border-radius:3px;transition:width .4s}
.qb-val{width:56px;text-align:right;font-size:12px;flex-shrink:0;font-weight:bold}
.qb-chosen .qb-track{outline:2px solid #f0f6fc;border-radius:3px}

#bottom{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr;gap:10px}
#footer{padding:4px 12px;font-size:10px;color:#484f58;text-align:right}
</style>
</head>
<body>

<div id="hdr">
  <h1>&#11035; DINO RL</h1>
  <div id="modes">
    <span class="mode" id="M-jitter">jitter</span>
    <span class="mode" id="M-randstart">randstart</span>
    <span class="mode" id="M-evaljit">eval-jitter</span>
  </div>
  <div class="kpi c"><div class="v" id="H-phase">—</div><div class="l">Phase</div></div>
  <div class="kpi y"><div class="v" id="H-eval">—</div><div class="l">Eval Median</div></div>
  <div class="kpi g"><div class="v" id="H-gate">—</div><div class="l">Deploy GATE %</div></div>
  <div class="kpi g"><div class="v" id="H-ebest">—</div><div class="l">Eval Best</div></div>
  <div class="kpi c"><div class="v" id="H-ep">—</div><div class="l">Episode</div></div>
  <div class="kpi p"><div class="v" id="H-eps">—</div><div class="l">Epsilon</div></div>
  <div class="kpi"  ><div class="v" id="H-steps">—</div><div class="l">Total Steps</div></div>
  <div class="kpi"  ><div class="v" id="H-sps">—</div><div class="l">Steps/s</div></div>
  <div class="kpi r"><div class="v" id="H-loss">—</div><div class="l">Loss</div></div>
  <div id="hdr-time"></div>
</div>

<div id="main">

  <!-- hero: eval progression -->
  <div class="panel">
    <h2>Greedy Eval Progression — the metric every decision keys off</h2>
    <div class="sub">Gating uses the MEDIAN over the eval seeds (ε=0, fixed seeds, under jitter when enabled). Mean shown faint: when it sits far above the median, one lucky cruise is carrying the score. Training score is ε-contaminated.</div>
    <div class="chart-wrap" style="height:210px"><canvas id="cEval"></canvas></div>
  </div>

  <!-- eval death causes -->
  <div class="panel">
    <h2>Latest Eval — Death Causes</h2>
    <div class="sub" id="dc-meta">waiting for first eval…</div>
    <div id="dc-bars"></div>
  </div>

  <!-- loss + epsilon -->
  <div class="panel">
    <h2>Loss &amp; Epsilon Decay</h2>
    <div class="chart-wrap" style="height:160px"><canvas id="cLoss"></canvas></div>
  </div>

  <!-- action distribution -->
  <div class="panel">
    <h2>Action Mix — latest training episode (incl. exploration)</h2>
    <div id="act-pct">
      <div class="act-chip an"><div class="pv" id="A-noop">—</div><div class="pl">Noop / run-under</div></div>
      <div class="act-chip aj"><div class="pv" id="A-jump">—</div><div class="pl">Jump</div></div>
      <div class="act-chip ad"><div class="pv" id="A-duck">—</div><div class="pl">Duck</div></div>
    </div>
    <div class="chart-wrap" style="height:90px"><canvas id="cAction"></canvas></div>
  </div>

  <div id="bottom">
    <div class="panel">
      <h2>Q-Values — last network decision</h2>
      <div id="q-bars"></div>
    </div>
    <div class="panel">
      <h2>Curriculum &amp; Throughput</h2>
      <div class="dc"><span class="dc-name">Phase</span><span class="dc-val" id="C-phase" style="width:auto;flex:1;text-align:left;color:#39d2fc">—</span></div>
      <div class="dc"><span class="dc-name">Eval survived</span><span class="dc-val" id="C-surv" style="width:auto;flex:1;text-align:left;color:#3fb950">—</span></div>
      <div class="dc"><span class="dc-name">Eval clears</span><span class="dc-val" id="C-clears" style="width:auto;flex:1;text-align:left">—</span></div>
      <div class="dc"><span class="dc-name">Eval cadence</span><span class="dc-val" id="C-cad" style="width:auto;flex:1;text-align:left">—</span></div>
      <div class="dc"><span class="dc-name">Buffer</span><span class="dc-val" id="C-buf" style="width:auto;flex:1;text-align:left">—</span></div>
      <div class="dc"><span class="dc-name">Best train</span><span class="dc-val" id="C-bscore" style="width:auto;flex:1;text-align:left">—</span></div>
    </div>
  </div>

</div>
<div id="footer">auto-refresh every 2 s</div>

<script>
const Q_COLS = ['#8b949e','#39d2fc','#bc8cff'];
const Q_LABS = ['noop','jump','duck'];

// death-cause rows: cacti (blue) vs birds by required action
const DCAUSES = [
  {k:'cactus_small', c:'#39d2fc', hint:'jump'},
  {k:'cactus_large', c:'#1f9ed1', hint:'jump'},
  {k:'bird_low',     c:'#3fb950', hint:'jump'},
  {k:'bird_mid',     c:'#e3b341', hint:'DUCK'},
  {k:'bird_high',    c:'#f85149', hint:'run under (no jump!)'},
];

(function initQBars(){
  const el=document.getElementById('q-bars');
  Q_LABS.forEach((lab,i)=>el.insertAdjacentHTML('beforeend',`
    <div class="qb" id="qrow-${lab}">
      <span class="qb-name">${lab}</span>
      <div class="qb-track"><div class="qb-fill" id="qf-${lab}" style="width:0%;background:${Q_COLS[i]}"></div></div>
      <span class="qb-val" id="qv-${lab}">—</span>
    </div>`));
})();
(function initDC(){
  const el=document.getElementById('dc-bars');
  DCAUSES.forEach(d=>el.insertAdjacentHTML('beforeend',`
    <div class="dc">
      <span class="dc-name">${d.k.replace('_',' ')}</span>
      <div class="dc-track"><div class="dc-fill" id="dcf-${d.k}" style="width:0%;background:${d.c}"></div></div>
      <span class="dc-val" id="dcv-${d.k}">0</span>
      <span class="dc-hint">${d.hint}</span>
    </div>`));
})();

const darkGrid='#21262d', darkTick='#484f58', labelColor='#8b949e';
const baseOpts=(extra={})=>({
  responsive:true,maintainAspectRatio:false,animation:false,
  plugins:{legend:{labels:{color:labelColor,font:{size:10},boxWidth:10}}},
  scales:{
    x:{ticks:{color:darkTick,maxTicksLimit:8,font:{size:10}},grid:{color:darkGrid}},
    y:{ticks:{color:labelColor,font:{size:10}},grid:{color:darkGrid},...extra.y},
    ...(extra.y2?{y2:{type:'linear',position:'right',ticks:{color:'#e3b341',font:{size:10}},
                 grid:{drawOnChartArea:false},min:0,max:1,...extra.y2}}:{}),
  },...extra.top,
});
const mkChart=(id,type,ds,extra={})=>new Chart(document.getElementById(id),
  {type,data:{labels:[],datasets:ds},options:baseOpts(extra)});

const cEval = mkChart('cEval','line',[
  {label:'Eval median (gate)', data:[], borderColor:'#e3b341', backgroundColor:'#e3b34118',
   borderWidth:2, pointRadius:0, fill:true, tension:.2},
  {label:'Eval best',data:[], borderColor:'#3fb950', backgroundColor:'transparent',
   borderWidth:2, pointRadius:0, fill:false, tension:0},
  {label:'Eval mean', data:[], borderColor:'#f0a05088', backgroundColor:'transparent',
   borderWidth:1, pointRadius:0, fill:false, tension:.2, borderDash:[4,3]},
  {label:'Train score (ε)', data:[], borderColor:'#39d2fc55', backgroundColor:'transparent',
   borderWidth:1, pointRadius:0, fill:false, tension:.3},
]);
const cLoss = mkChart('cLoss','line',[
  {label:'Loss',    data:[], borderColor:'#f85149', backgroundColor:'transparent',
   borderWidth:1.5, pointRadius:0, tension:.3, yAxisID:'y'},
  {label:'Epsilon', data:[], borderColor:'#e3b341', backgroundColor:'transparent',
   borderWidth:1.5, pointRadius:0, tension:.1, yAxisID:'y2'},
],{ y2:{} });
const cAction = mkChart('cAction','bar',[
  {label:'Noop', data:[], backgroundColor:'#8b949e80'},
  {label:'Jump', data:[], backgroundColor:'#39d2fc80'},
  {label:'Duck', data:[], backgroundColor:'#bc8cff80'},
],{ y:{stacked:true,min:0,max:100},
    top:{plugins:{legend:{labels:{color:labelColor,font:{size:9},boxWidth:8}}}} });
cAction.options.scales.x.stacked=true; cAction.options.scales.y.stacked=true;

const fmtK = v => Math.abs(v)>=1000 ? (v/1000).toFixed(1)+'k' : String(Math.round(v));

function render(data){
  const h=data.history, c=data.current||{};
  if(!h.length) return;

  // mode chips
  document.getElementById('M-jitter').classList.toggle('on', !!c.jitter);
  document.getElementById('M-randstart').classList.toggle('on', !!c.randstart);
  document.getElementById('M-evaljit').classList.toggle('on', !!c.eval_jitter);

  // header
  document.getElementById('H-phase').textContent = c.phase || '—';
  document.getElementById('H-phase').style.color = (c.phase_status==='stalled')?'#f85149':'';
  document.getElementById('H-eval').textContent  = (c.eval_avg!=null)? fmtK(c.eval_avg):'—';
  document.getElementById('H-gate').textContent  = (c.deploy_gate!=null)? Math.round(c.deploy_gate*100)+'%':'—';
  document.getElementById('H-ebest').textContent = fmtK(c.eval_best||0);
  document.getElementById('H-ep').textContent    = data.total_episodes;
  document.getElementById('H-eps').textContent   = (c.epsilon!=null?c.epsilon:1).toFixed(3);
  document.getElementById('H-steps').textContent = fmtK(c.total_steps||0);
  document.getElementById('H-sps').textContent   = fmtK(c.sps||0);
  document.getElementById('H-loss').textContent  = (c.loss||0).toFixed(3);
  document.getElementById('hdr-time').textContent= new Date().toLocaleTimeString();

  // eval progression (carry-forward eval values; training score faint)
  const eps=h.map(e=>e.episode);
  cEval.data.labels=eps;
  cEval.data.datasets[0].data=h.map(e=>e.eval_avg!=null?e.eval_avg:null);   // median (gate)
  cEval.data.datasets[1].data=h.map(e=>e.eval_best||0);
  cEval.data.datasets[2].data=h.map(e=>e.eval_mean!=null?e.eval_mean:null);
  cEval.data.datasets[3].data=h.map(e=>e.score||0);
  cEval.update('none');

  // loss + epsilon (last 150)
  const l=h.slice(-150);
  cLoss.data.labels=l.map(e=>e.episode);
  cLoss.data.datasets[0].data=l.map(e=>e.loss||0);
  cLoss.data.datasets[1].data=l.map(e=>e.epsilon!=null?e.epsilon:1);
  cLoss.update('none');

  // action mix
  const ap=c.action_pct||{};
  document.getElementById('A-noop').textContent=(ap.noop||0).toFixed(0)+'%';
  document.getElementById('A-jump').textContent=(ap.jump||0).toFixed(0)+'%';
  document.getElementById('A-duck').textContent=(ap.duck||0).toFixed(0)+'%';
  const a60=h.slice(-60);
  cAction.data.labels=a60.map(e=>e.episode);
  cAction.data.datasets[0].data=a60.map(e=>(e.action_pct||{}).noop||0);
  cAction.data.datasets[1].data=a60.map(e=>(e.action_pct||{}).jump||0);
  cAction.data.datasets[2].data=a60.map(e=>(e.action_pct||{}).duck||0);
  cAction.update('none');

  // latest eval death causes (scan back for the most recent eval round)
  let dc=null, dcEp=null;
  for(let i=h.length-1;i>=0;i--){ if(h[i].eval_death_causes){ dc=h[i].eval_death_causes; dcEp=h[i].episode; break; } }
  const total=dc?Object.values(dc).reduce((a,b)=>a+b,0):0;
  document.getElementById('dc-meta').textContent = dc
    ? `episode ${dcEp} · ${total} deaths across ${ (c.eval_episodes||'?') } eval episodes`
    : 'waiting for first eval…';
  const mx=dc?Math.max(1,...Object.values(dc)):1;
  DCAUSES.forEach(d=>{
    const n=dc?(dc[d.k]||0):0;
    document.getElementById('dcf-'+d.k).style.width=(n/mx*100)+'%';
    document.getElementById('dcv-'+d.k).textContent=n;
  });

  // curriculum / throughput
  document.getElementById('C-phase').textContent  = (c.phase||'—')+(c.phase_status==='stalled'?'  ⚠ STALLED':'');
  let evRow=null; for(let i=h.length-1;i>=0;i--){ if(h[i].eval_survived!=null){evRow=h[i];break;} }
  document.getElementById('C-surv').textContent = evRow? `${evRow.eval_survived}/${evRow.eval_n} cruised to timeout`:'—';
  let evClears=null; for(let i=h.length-1;i>=0;i--){ if(h[i].eval_clears!=null){evClears=h[i].eval_clears;break;} }
  document.getElementById('C-clears').textContent = evClears!=null? evClears+' obstacles/ep':'—';
  document.getElementById('C-cad').textContent    = c.eval_jitter? 'jittered '+'(2–6 frames)':'fixed';
  document.getElementById('C-buf').textContent    = fmtK(c.buffer||0)+' transitions';
  document.getElementById('C-bscore').textContent = fmtK(c.best||0);

  // q-values
  const qv=c.q_values||[0,0,0];
  const mxq=Math.max(...qv.map(Math.abs))||1;
  const bi=qv.indexOf(Math.max(...qv));
  Q_LABS.forEach((lab,i)=>{
    document.getElementById('qf-'+lab).style.width=Math.min(Math.abs(qv[i])/mxq*100,100)+'%';
    document.getElementById('qv-'+lab).textContent=qv[i].toFixed(3);
    document.getElementById('qrow-'+lab).classList.toggle('qb-chosen', i===bi);
  });
}

async function poll(){
  try{ const r=await fetch('/data'); if(r.ok) render(await r.json());
       else document.getElementById('footer').textContent='waiting for training…'; }
  catch(_){ document.getElementById('footer').textContent='waiting for training…'; }
  setTimeout(poll,2000);
}
poll();
</script>
</body>
</html>"""
