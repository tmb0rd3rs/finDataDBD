import { useState, useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";

// ─── constants ────────────────────────────────────────────────────────────────
const ALL_TICKERS = ["SCCO","IBM","TRI","XOM","AZN","JNJ"];
const PALETTE     = ["#3b82f6","#ef4444","#22c55e","#a855f7","#f97316","#06b6d4"];
const CMAP        = Object.fromEntries(ALL_TICKERS.map((t,i)=>[t,PALETTE[i]]));
CMAP["Portfolio"] = "#111827";
const RF_ANNUAL   = 0.05;
const WINDOW      = 60;
const N_DAYS      = 1200;
const DS          = 4;       // downsample every Nth day for chart rendering

// ─── seeded RNG (mulberry32) ──────────────────────────────────────────────────
function mkRng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function rNorm(rng) {
  let u, v, s;
  do { u = rng() * 2 - 1; v = rng() * 2 - 1; s = u*u + v*v; } while (s >= 1 || s === 0);
  return u * Math.sqrt(-2 * Math.log(s) / s);
}

// ─── synthetic data (generated once at module load) ───────────────────────────
const PARAMS = {
  SCCO: { drift: 0.00035, vol: 0.022, beta: 1.20 },
  IBM:  { drift: 0.00010, vol: 0.016, beta: 0.80 },
  TRI:  { drift: 0.00045, vol: 0.014, beta: 0.65 },
  XOM:  { drift: 0.00020, vol: 0.020, beta: 1.10 },
  AZN:  { drift: 0.00055, vol: 0.018, beta: 0.60 },
  JNJ:  { drift: 0.00010, vol: 0.012, beta: 0.50 },
};
const MKT_DRIFT = 0.0003, MKT_VOL = 0.012;

function buildStaticData() {
  const rfDaily = Math.log(1 + RF_ANNUAL) / 252;
  const mrng    = mkRng(42);
  const mkt     = Array.from({ length: N_DAYS }, () => MKT_DRIFT + MKT_VOL * rNorm(mrng));

  const rets = {};
  ALL_TICKERS.forEach((t, i) => {
    const { drift, vol, beta } = PARAMS[t];
    const rng     = mkRng(i * 211 + 77);
    const idioVol = Math.sqrt(Math.max(vol**2 - (beta * MKT_VOL)**2, 1e-8));
    rets[t] = mkt.map(m => beta*m + idioVol*rNorm(rng) + (drift - beta*MKT_DRIFT));
  });

  const dates = [];
  const d = new Date("2020-02-07");
  while (dates.length < N_DAYS) {
    if (d.getDay() !== 0 && d.getDay() !== 6) dates.push(d.toISOString().slice(0, 10));
    d.setDate(d.getDate() + 1);
  }
  return { dates, mkt, rets, rfDaily };
}
const STATIC = buildStaticData();

// ─── math helpers ─────────────────────────────────────────────────────────────
const sum  = a => a.reduce((s, x) => s + x, 0);
const avg  = a => sum(a) / a.length;
function sdev(a) {
  const m = avg(a);
  return Math.sqrt(a.reduce((s, x) => s + (x - m)**2, 0) / (a.length - 1));
}
function covar(a, b) {
  const ma = avg(a), mb = avg(b);
  return a.reduce((s, x, i) => s + (x - ma)*(b[i] - mb), 0) / (a.length - 1);
}
const fmt2 = v => v != null ? v.toFixed(2) : "—";
const fmt3 = v => v != null ? v.toFixed(3) : "—";

// ─── metrics ──────────────────────────────────────────────────────────────────
function computeAll(selected, weights) {
  const { dates, mkt, rets, rfDaily } = STATIC;

  // portfolio log-returns (exact: simple → weighted sum → log)
  const port = new Array(N_DAYS).fill(0);
  selected.forEach(t => rets[t].forEach((r, i) => { port[i] += Math.expm1(r) * weights[t]; }));
  const portLog = port.map(r => Math.log1p(r));

  const allNames = [...selected, "Portfolio"];
  const allRets  = { ...Object.fromEntries(selected.map(t => [t, rets[t]])), Portfolio: portLog };
  const mktEx    = mkt.map(r => r - rfDaily);
  const mktVar   = covar(mktEx, mktEx);

  // cumulative prices (start = 1)
  const cumRets = {};
  allNames.forEach(name => {
    let v = 1;
    cumRets[name] = [1, ...allRets[name].map(r => (v *= Math.exp(r), v))];
  });

  // rolling window metrics + downsampling
  const chartData = [];
  for (let i = 0; i < N_DAYS; i += DS) {
    const pt = { date: dates[i] };
    allNames.forEach(n => { pt[`cum_${n}`] = +cumRets[n][i + 1].toFixed(3); });

    if (i >= WINDOW) {
      allNames.forEach(name => {
        const sl     = allRets[name].slice(i - WINDOW, i).map(r => r - rfDaily);
        const m      = avg(sl);
        const s      = sdev(sl);
        const neg    = sl.filter(r => r < 0);
        const ds     = neg.length > 3
          ? Math.sqrt(neg.reduce((a, r) => a + r*r, 0) / neg.length)
          : (s || 1e-10);
        const mktSl  = mktEx.slice(i - WINDOW, i);
        const mktV   = covar(mktSl, mktSl) || 1e-10;
        const beta   = covar(sl, mktSl) / mktV;

        pt[`sh_${name}`] = s   > 1e-10 ? +(m / s   * Math.sqrt(252)).toFixed(3) : null;
        pt[`so_${name}`] = ds  > 1e-10 ? +(m / ds  * Math.sqrt(252)).toFixed(3) : null;
        pt[`tr_${name}`] = Math.abs(beta) > 0.05 ? +(m / beta * 252).toFixed(4) : null;
      });
    }
    chartData.push(pt);
  }

  // full-period stats
  const stats = {};
  allNames.forEach(name => {
    const excess = allRets[name].map(r => r - rfDaily);
    const m      = avg(excess);
    const s      = sdev(excess);
    const neg    = excess.filter(r => r < 0);
    const ds     = neg.length > 3
      ? Math.sqrt(neg.reduce((a, r) => a + r*r, 0) / neg.length)
      : s;
    const beta   = covar(excess, mktEx) / (mktVar || 1e-10);

    stats[name] = {
      sharpe:  +(m / s  * Math.sqrt(252)).toFixed(3),
      sortino: +(m / ds * Math.sqrt(252)).toFixed(3),
      treynor: +(m / beta * 252).toFixed(4),
      beta:    +beta.toFixed(3),
      ret:     +((Math.exp(avg(allRets[name]) * 252) - 1) * 100).toFixed(2),
      vol:     +(s * Math.sqrt(252) * 100).toFixed(2),
    };
  });

  return { chartData, stats };
}

// ─── chart configs ────────────────────────────────────────────────────────────
const CHARTS = [
  { key:"cum", prefix:"cum", label:"Cumulative Returns",           statKey:null,      yFmt:fmt2, zero:false },
  { key:"sh",  prefix:"sh",  label:`Rolling Sharpe (${WINDOW}d)`, statKey:"sharpe",  yFmt:fmt2, zero:true  },
  { key:"so",  prefix:"so",  label:`Rolling Sortino (${WINDOW}d)`,statKey:"sortino", yFmt:fmt2, zero:true  },
  { key:"tr",  prefix:"tr",  label:`Rolling Treynor (${WINDOW}d)`,statKey:"treynor", yFmt:fmt2, zero:true  },
];

// ─── chart component ──────────────────────────────────────────────────────────
function MetricChart({ cfg, data, selected, stats }) {
  const { prefix, label, yFmt, zero, statKey } = cfg;

  const footerNames = statKey ? [...selected, "Portfolio"] : [];

  return (
    <div style={{
      background: "white", borderRadius: 10, padding: "14px 16px 10px",
      boxShadow: "0 1px 4px rgba(0,0,0,.07)", display: "flex", flexDirection: "column",
    }}>
      <span style={{ fontSize: 12, fontWeight: 700, color: "#374151", marginBottom: 8, letterSpacing: ".01em" }}>
        {label}
      </span>

      <ResponsiveContainer width="100%" height={185}>
        <LineChart data={data} margin={{ top: 4, right: 4, left: -8, bottom: 2 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#9ca3af" }}
            tickFormatter={v => v.slice(0, 4)}
            interval={Math.floor((N_DAYS / DS) / 5)} />
          <YAxis tick={{ fontSize: 9, fill: "#9ca3af" }} width={38} tickFormatter={yFmt} />
          {zero && <ReferenceLine y={0} stroke="#d1d5db" strokeDasharray="4 2" />}
          <Tooltip contentStyle={{ fontSize: 10, padding: "3px 8px", borderRadius: 6 }}
            formatter={(v, n) => [v != null ? (+v).toFixed(3) : "—", n]}
            labelStyle={{ fontSize: 10, color: "#6b7280" }} />
          <Legend wrapperStyle={{ fontSize: 9 }} iconSize={7} />

          {selected.map(t => (
            <Line key={t} type="monotone" dataKey={`${prefix}_${t}`}
              stroke={CMAP[t]} dot={false} strokeWidth={1.5}
              name={t} connectNulls isAnimationActive={false} />
          ))}
          <Line type="monotone" dataKey={`${prefix}_Portfolio`}
            stroke={CMAP["Portfolio"]} dot={false} strokeWidth={2.8}
            name="Portfolio" connectNulls strokeDasharray="7 3" isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>

      {/* final-value footer */}
      {footerNames.length > 0 && (
        <div style={{
          display: "flex", flexWrap: "wrap", gap: "3px 10px",
          marginTop: 8, paddingTop: 7, borderTop: "1px solid #f3f4f6",
        }}>
          {footerNames.map(name => (
            <span key={name} style={{
              fontSize: 10, fontWeight: name === "Portfolio" ? 800 : 600,
              color: name === "Portfolio" ? CMAP["Portfolio"] : CMAP[name],
            }}>
              {name}: {stats[name]?.[statKey] ?? "—"}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── main dashboard ───────────────────────────────────────────────────────────
export default function Dashboard() {
  const [selected, setSelected] = useState(new Set(ALL_TICKERS));
  const [sliders,  setSliders]  = useState(
    Object.fromEntries(ALL_TICKERS.map(t => [t, 50]))
  );

  const selArr  = ALL_TICKERS.filter(t => selected.has(t));
  const rawSum  = selArr.reduce((s, t) => s + sliders[t], 0) || 1;
  const weights = Object.fromEntries(selArr.map(t => [t, sliders[t] / rawSum]));

  const { chartData, stats } = useMemo(() => {
    if (!selArr.length) return { chartData: [], stats: {} };
    return computeAll(selArr, weights);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selArr.join(","), selArr.map(t => sliders[t]).join(",")]);

  const toggle = t => setSelected(prev => {
    if (prev.has(t) && prev.size === 1) return prev;
    const next = new Set(prev);
    next.has(t) ? next.delete(t) : next.add(t);
    return next;
  });

  const portStats = stats["Portfolio"] ?? null;

  return (
    <div style={{
      display: "flex", minHeight: "100vh",
      fontFamily: '"Inter",system-ui,sans-serif', background: "#f1f5f9",
    }}>

      {/* ─── sidebar ─── */}
      <div style={{
        width: 240, flexShrink: 0, background: "white",
        borderRight: "1px solid #e5e7eb", padding: "20px 14px",
        overflowY: "auto", display: "flex", flexDirection: "column", gap: 18,
      }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 800, color: "#111827" }}>Portfolio Builder</div>
          <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 3 }}>
            Synthetic · 2020 – 2025 · RF {(RF_ANNUAL*100).toFixed(0)}%
          </div>
        </div>

        {/* stock toggles */}
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#6b7280", textTransform: "uppercase",
            letterSpacing: ".07em", marginBottom: 9 }}>
            Stocks
          </div>
          {ALL_TICKERS.map((t, i) => {
            const on = selected.has(t);
            return (
              <button key={t} onClick={() => toggle(t)} style={{
                display: "flex", alignItems: "center", width: "100%",
                background: on ? `${PALETTE[i]}14` : "transparent",
                border: `1.5px solid ${on ? PALETTE[i] : "#e5e7eb"}`,
                borderRadius: 7, padding: "6px 10px", marginBottom: 5,
                cursor: "pointer", textAlign: "left",
              }}>
                <span style={{
                  width: 9, height: 9, borderRadius: "50%",
                  background: on ? PALETTE[i] : "#d1d5db",
                  flexShrink: 0, marginRight: 8,
                }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: on ? "#111827" : "#9ca3af", flex: 1 }}>
                  {t}
                </span>
                {on && (
                  <span style={{ fontSize: 10, color: PALETTE[i], fontWeight: 700 }}>
                    {(weights[t] * 100).toFixed(0)}%
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* weight sliders */}
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#6b7280", textTransform: "uppercase",
            letterSpacing: ".07em", marginBottom: 9 }}>
            Weights
          </div>
          {selArr.map(t => (
            <div key={t} style={{ marginBottom: 13 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 12, color: "#374151", fontWeight: 500 }}>{t}</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: CMAP[t] }}>
                  {(weights[t] * 100).toFixed(1)}%
                </span>
              </div>
              <input type="range" min={1} max={100} value={sliders[t]}
                onChange={e => setSliders(p => ({ ...p, [t]: +e.target.value }))}
                style={{ width: "100%", accentColor: CMAP[t], cursor: "pointer", height: 4 }} />
            </div>
          ))}
        </div>

        {/* portfolio summary card */}
        {portStats && (
          <div style={{
            background: "#111827", borderRadius: 10, padding: 14,
            marginTop: "auto", color: "white",
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#9ca3af",
              textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 12 }}>
              Portfolio Summary
            </div>
            {[
              ["Ann. Return", portStats.ret + "%"],
              ["Volatility",  portStats.vol + "%"],
              ["Beta",        portStats.beta],
              null,
              ["Sharpe",      portStats.sharpe],
              ["Sortino",     portStats.sortino],
              ["Treynor",     portStats.treynor],
            ].map((row, ri) => row === null
              ? <div key={ri} style={{ height: 1, background: "#374151", margin: "8px 0" }} />
              : (
                <div key={row[0]} style={{ display: "flex", justifyContent: "space-between", marginBottom: 7 }}>
                  <span style={{ fontSize: 12, color: "#9ca3af" }}>{row[0]}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#f9fafb" }}>{row[1]}</span>
                </div>
              )
            )}
          </div>
        )}
      </div>

      {/* ─── charts area ─── */}
      <div style={{ flex: 1, padding: "20px 20px 24px", overflowY: "auto" }}>
        <div style={{ marginBottom: 16 }}>
          <h1 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#111827" }}>
            Risk-Adjusted Return Dashboard
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 11, color: "#6b7280" }}>
            Window = {WINDOW} trading days · Portfolio = dashed black line · Final values shown below each chart
          </p>
        </div>

        {/* 2 × 2 chart grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 16 }}>
          {CHARTS.map(cfg => (
            <MetricChart key={cfg.key} cfg={cfg} data={chartData}
              selected={selArr} stats={stats} />
          ))}
        </div>

        {/* full-period stats table */}
        {selArr.length > 0 && Object.keys(stats).length > 0 && (
          <div style={{
            background: "white", borderRadius: 10, padding: "14px 16px",
            boxShadow: "0 1px 4px rgba(0,0,0,.07)",
          }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#374151", marginBottom: 12 }}>
              Full-Period Statistics
            </div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #e5e7eb" }}>
                    {["Ticker","Ann. Return","Volatility","Beta","Sharpe","Sortino","Treynor"].map(h => (
                      <th key={h} style={{
                        padding: "5px 10px", textAlign: h === "Ticker" ? "left" : "right",
                        color: "#6b7280", fontWeight: 700, fontSize: 11,
                        textTransform: "uppercase", letterSpacing: ".04em",
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...selArr, "Portfolio"].map(name => {
                    const s = stats[name];
                    if (!s) return null;
                    const isPort = name === "Portfolio";
                    return (
                      <tr key={name} style={{
                        borderBottom: "1px solid #f3f4f6",
                        background: isPort ? "#f8fafc" : "white",
                        fontWeight: isPort ? 700 : 400,
                      }}>
                        <td style={{ padding: "8px 10px" }}>
                          <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
                            <span style={{
                              width: 8, height: 8, borderRadius: "50%",
                              background: CMAP[name], flexShrink: 0,
                              ...(isPort ? { borderRadius: 2 } : {}),
                            }} />
                            <span style={{ color: CMAP[name] }}>{name}</span>
                          </span>
                        </td>
                        {[s.ret+"%", s.vol+"%", s.beta, s.sharpe, s.sortino, s.treynor].map((v, j) => (
                          <td key={j} style={{
                            padding: "8px 10px", textAlign: "right",
                            color: isPort ? "#111827" : "#374151",
                          }}>{v}</td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
