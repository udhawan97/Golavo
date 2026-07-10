import type { ReliabilityBin } from "../lib/contract";
import { pct } from "../lib/format";

/** Hand-rolled reliability (calibration) diagram. No chart library: forecast
 *  probability on x, observed frequency on y, point area ∝ sample count, with a
 *  dashed diagonal marking perfect calibration. Points on the line = honest. */
export function ReliabilityDiagram({
  bins, caption,
}: { bins: ReliabilityBin[]; caption?: string }) {
  const W = 360, H = 340;
  const padL = 46, padR = 16, padT = 16, padB = 44;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const x = (p: number) => padL + p * plotW;
  const y = (r: number) => padT + (1 - r) * plotH;

  const maxN = Math.max(...bins.map((b) => b.n), 1);
  // Area-proportional with a visibility floor: area = π·r² is affine in n, so
  // r = √(rMin² + (n/maxN)·(rMax² − rMin²)). A tiny bin stays visible without
  // overstating its weight.
  const rMin = 3.5, rMax = 12;
  const radius = (n: number) => Math.sqrt(rMin * rMin + (n / maxN) * (rMax * rMax - rMin * rMin));
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const sorted = [...bins].sort((a, b) => a.p_mid - b.p_mid);
  const poly = sorted.map((b) => `${x(b.p_mid).toFixed(1)},${y(b.observed_rate).toFixed(1)}`).join(" ");

  const summary =
    `Calibration diagram: ${bins.length} bins. ` +
    sorted.map((b) => `at forecast ${pct(b.p_mid, 0)}, observed ${pct(b.observed_rate, 0)} over ${b.n}`).join("; ") + ".";

  return (
    <figure style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary}>
        {/* grid */}
        {ticks.map((t) => (
          <g key={`g${t}`}>
            <line className="rd-grid" x1={x(t)} y1={padT} x2={x(t)} y2={padT + plotH} />
            <line className="rd-grid" x1={padL} y1={y(t)} x2={padL + plotW} y2={y(t)} />
          </g>
        ))}
        {/* perfect-calibration diagonal */}
        <line className="rd-diag" x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} />
        {/* axes */}
        <line className="rd-axis" x1={padL} y1={padT} x2={padL} y2={padT + plotH} />
        <line className="rd-axis" x1={padL} y1={padT + plotH} x2={padL + plotW} y2={padT + plotH} />
        {/* ticks */}
        {ticks.map((t) => (
          <g key={`t${t}`}>
            <text className="rd-tick" x={x(t)} y={padT + plotH + 16} textAnchor="middle">{t.toFixed(2)}</text>
            <text className="rd-tick" x={padL - 8} y={y(t) + 3} textAnchor="end">{t.toFixed(2)}</text>
          </g>
        ))}
        {/* trend through the bins */}
        <polyline className="rd-pt-line" points={poly} />
        {/* points */}
        {sorted.map((b, i) => (
          <circle key={i} className="rd-pt" cx={x(b.p_mid)} cy={y(b.observed_rate)} r={radius(b.n)}>
            <title>{`Forecast ${pct(b.p_mid, 0)} · observed ${pct(b.observed_rate, 1)} · n=${b.n}`}</title>
          </circle>
        ))}
        {/* axis labels */}
        <text className="rd-label" x={padL + plotW / 2} y={H - 6} textAnchor="middle">Forecast probability</text>
        <text className="rd-label" transform={`rotate(-90 12 ${padT + plotH / 2})`} x={12} y={padT + plotH / 2} textAnchor="middle">Observed frequency</text>
      </svg>
      <figcaption className="small muted" style={{ marginTop: ".5rem", display: "flex", gap: ".9rem", flexWrap: "wrap" }}>
        <span><span className="mono">— —</span> perfect calibration</span>
        <span>● point size scales with sample count</span>
        {caption && <span className="dim">{caption}</span>}
      </figcaption>
    </figure>
  );
}
