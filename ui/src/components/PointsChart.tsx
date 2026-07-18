import { memo, useMemo, useState } from "react";
import type { ScoredRivalFamily, PicksSummary } from "../lib/contract";
import { RIVALS } from "../lib/picks";

type SeriesId = "user" | ScoredRivalFamily;
const FAMILIES = Object.keys(RIVALS) as ScoredRivalFamily[];
const CLASS: Record<SeriesId, string> = {
  user: "points-line--user",
  dixon_coles: "points-line--dc",
  poisson_independent: "points-line--pi",
  bivariate_poisson: "points-line--bp",
  elo_ordlogit: "points-line--elo",
  climatological: "points-line--clim",
};

function niceCeil(value: number): number {
  if (value <= 5) return 5;
  const power = 10 ** Math.floor(Math.log10(value));
  return Math.ceil(value / power) * power;
}

function PointsChartImpl({ series }: { series: PicksSummary["series"] }) {
  const [hidden, setHidden] = useState<Set<SeriesId>>(new Set());
  const [active, setActive] = useState<number | null>(null);
  const chart = useMemo(() => {
    const max = Math.max(
      0,
      ...series.map((point) => point.user_total),
      ...series.flatMap((point) => Object.values(point.per_family_totals)),
    );
    return { max: niceCeil(max) };
  }, [series]);
  if (series.length === 0) return null;

  const W = 720;
  const H = 340;
  const pad = { l: 46, r: 110, t: 20, b: 48 };
  const plotW = W - pad.l - pad.r;
  const plotH = H - pad.t - pad.b;
  const x = (index: number) => pad.l + (series.length === 1 ? plotW / 2 : (index / (series.length - 1)) * plotW);
  const y = (value: number) => pad.t + (1 - value / chart.max) * plotH;
  const values = (id: SeriesId) =>
    series.map((point) => (id === "user" ? point.user_total : point.per_family_totals[id] ?? 0));
  const ids: SeriesId[] = ["user", ...FAMILIES];
  const tickEvery = Math.max(1, Math.ceil(series.length / 8));
  const summary = `Cumulative points across ${series.length} scored picks. You have ${series.at(-1)?.user_total ?? 0} points.`;

  const toggle = (id: SeriesId) => {
    if (id === "user") return;
    setHidden((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <figure className="points-chart">
      <div className="points-chart__legend" aria-label="Chart series">
        {ids.map((id) => (
          <button key={id} type="button" className={CLASS[id]} aria-pressed={!hidden.has(id)} disabled={id === "user"} onClick={() => toggle(id)}>
            <span aria-hidden /> {id === "user" ? "You" : RIVALS[id].name}
          </button>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary}>
        {[0, .25, .5, .75, 1].map((tick) => (
          <g key={tick}>
            <line className="points-grid" x1={pad.l} y1={y(chart.max * tick)} x2={pad.l + plotW} y2={y(chart.max * tick)} />
            <text className="points-tick" x={pad.l - 8} y={y(chart.max * tick) + 4} textAnchor="end">{Math.round(chart.max * tick)}</text>
          </g>
        ))}
        {ids.map((id) => {
          if (hidden.has(id)) return null;
          const data = values(id);
          const points = data.map((value, index) => `${x(index)},${y(value)}`).join(" ");
          return (
            <g key={id} className={`points-line ${CLASS[id]}`}>
              {series.length > 1 && <polyline points={points} />}
              {data.map((value, index) => <circle key={index} cx={x(index)} cy={y(value)} r={id === "user" ? 3.5 : 2.5} />)}
              <text x={pad.l + plotW + 7} y={y(data.at(-1) ?? 0) + 4}>{id === "user" ? "You" : RIVALS[id].name}</text>
            </g>
          );
        })}
        {series.map((point, index) => (
          <g key={point.match_id}>
            {(index % tickEvery === 0 || index === series.length - 1) && (
              <text className="points-tick" x={x(index)} y={pad.t + plotH + 20} textAnchor="middle">
                {new Date(point.kickoff_utc).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" })}
              </text>
            )}
            <rect
              className="points-hit"
              x={x(index) - Math.max(8, plotW / Math.max(2, series.length) / 2)}
              y={pad.t}
              width={Math.max(16, plotW / Math.max(2, series.length))}
              height={plotH}
              tabIndex={0}
              aria-label={`Pick ${index + 1}: you ${point.user_total} cumulative points`}
              onMouseEnter={() => setActive(index)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(index)}
              onBlur={() => setActive(null)}
            />
          </g>
        ))}
        {active !== null && (
          <g className="points-tip" pointerEvents="none">
            <line x1={x(active)} y1={pad.t} x2={x(active)} y2={pad.t + plotH} />
            <rect x={Math.min(x(active) + 8, W - 170)} y={pad.t + 8} width="150" height="42" rx="6" />
            <text x={Math.min(x(active) + 16, W - 162)} y={pad.t + 25}>Pick {active + 1}</text>
            <text x={Math.min(x(active) + 16, W - 162)} y={pad.t + 41}>You · {series[active].user_total} pts</text>
          </g>
        )}
      </svg>
      <figcaption className="small muted">
        {series.length === 1 ? "The chart starts drawing after your second scored pick. " : ""}
        Each column matches one row in the history table below.
      </figcaption>
    </figure>
  );
}

export const PointsChart = memo(PointsChartImpl);
