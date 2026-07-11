import type { ReliabilityBin } from "../lib/contract";
import { pct } from "../lib/format";

/** Hand-rolled reliability (calibration) diagram. No chart library: mean model
 *  confidence on x, observed accuracy on y, point area ∝ sample count, the Wilson
 *  95% interval as a vertical whisker, and a dashed diagonal marking perfect
 *  calibration. Points on the line = confidence matched accuracy. */
export function ReliabilityDiagram({
  bins,
  caption,
}: {
  bins: ReliabilityBin[];
  caption?: string;
}) {
  const pts = bins
    .filter((b) => b.count > 0 && b.mean_confidence != null && b.accuracy != null)
    .map((b) => ({
      conf: b.mean_confidence as number,
      acc: b.accuracy as number,
      n: b.count,
      lo: b.wilson_low,
      hi: b.wilson_high,
    }))
    .sort((a, b) => a.conf - b.conf);

  const W = 360;
  const H = 340;
  const padL = 46;
  const padR = 16;
  const padT = 16;
  const padB = 44;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const x = (p: number) => padL + p * plotW;
  const y = (r: number) => padT + (1 - r) * plotH;

  const maxN = Math.max(...pts.map((p) => p.n), 1);
  const rMin = 3.5;
  const rMax = 12;
  const radius = (n: number) => Math.sqrt(rMin * rMin + (n / maxN) * (rMax * rMax - rMin * rMin));
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const poly = pts.map((p) => `${x(p.conf).toFixed(1)},${y(p.acc).toFixed(1)}`).join(" ");

  const summary =
    `Reliability diagram: ${pts.length} populated bins. ` +
    pts.map((p) => `confidence ${pct(p.conf, 0)}, accuracy ${pct(p.acc, 0)} over ${p.n}`).join("; ") +
    ".";

  return (
    <figure style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary}>
        {ticks.map((t) => (
          <g key={`g${t}`}>
            <line className="rd-grid" x1={x(t)} y1={padT} x2={x(t)} y2={padT + plotH} />
            <line className="rd-grid" x1={padL} y1={y(t)} x2={padL + plotW} y2={y(t)} />
          </g>
        ))}
        <line className="rd-diag" x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} />
        <line className="rd-axis" x1={padL} y1={padT} x2={padL} y2={padT + plotH} />
        <line className="rd-axis" x1={padL} y1={padT + plotH} x2={padL + plotW} y2={padT + plotH} />
        {ticks.map((t) => (
          <g key={`t${t}`}>
            <text className="rd-tick" x={x(t)} y={padT + plotH + 16} textAnchor="middle">
              {t.toFixed(2)}
            </text>
            <text className="rd-tick" x={padL - 8} y={y(t) + 3} textAnchor="end">
              {t.toFixed(2)}
            </text>
          </g>
        ))}
        {pts.map((p, i) =>
          p.lo != null && p.hi != null ? (
            <line
              key={`w${i}`}
              className="rd-grid"
              x1={x(p.conf)}
              y1={y(p.lo)}
              x2={x(p.conf)}
              y2={y(p.hi)}
              style={{ strokeWidth: 1.5 }}
            />
          ) : null,
        )}
        <polyline className="rd-pt-line" points={poly} />
        {pts.map((p, i) => (
          <circle key={i} className="rd-pt" cx={x(p.conf)} cy={y(p.acc)} r={radius(p.n)}>
            <title>{`Confidence ${pct(p.conf, 0)} · accuracy ${pct(p.acc, 1)} · n=${p.n}`}</title>
          </circle>
        ))}
        <text className="rd-label" x={padL + plotW / 2} y={H - 6} textAnchor="middle">
          Mean confidence
        </text>
        <text
          className="rd-label"
          transform={`rotate(-90 12 ${padT + plotH / 2})`}
          x={12}
          y={padT + plotH / 2}
          textAnchor="middle"
        >
          Observed accuracy
        </text>
      </svg>
      <figcaption
        className="small muted"
        style={{ marginTop: ".5rem", display: "flex", gap: ".9rem", flexWrap: "wrap" }}
      >
        <span><span className="mono">— —</span> perfect calibration</span>
        <span>● point size ∝ sample count · whisker = Wilson 95%</span>
        {caption && <span className="dim">{caption}</span>}
      </figcaption>
    </figure>
  );
}
