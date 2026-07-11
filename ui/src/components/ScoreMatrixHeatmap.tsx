import type { ScoreMatrix } from "../lib/contract";
import { pct } from "../lib/format";

/**
 * Accessible exact-score heatmap. Real table semantics (row/col headers,
 * scope), tabular numerals, a per-cell screen-reader label, and the most-likely
 * scoreline highlighted. The heat tint is mixed over the surface so cell text
 * stays legible in both themes, and all motion is CSS-only (so the global
 * reduced-motion rule covers it). Nothing here is derived in the UI — every
 * number comes straight from the sealed score_matrix.
 */
export function ScoreMatrixHeatmap({
  matrix, home, away,
}: { matrix: ScoreMatrix; home: string; away: string }) {
  const n = matrix.max_goals;
  const grid = matrix.grid;
  const ml = matrix.most_likely;
  const range = Array.from({ length: n + 1 }, (_, i) => i);
  const maxCell = Math.max(...grid.flat(), 1e-9);
  const caption =
    `Exact-score probability grid. Rows are ${home} goals, columns are ${away} goals. ` +
    `Most likely: ${home} ${ml.home}–${ml.away} ${away} at ${pct(ml.probability)}. ` +
    `${pct(matrix.tail.probability)} of the distribution lies beyond ${n} goals for a side.`;

  return (
    <div className="table-wrap">
      <table className="grid heatmap">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" className="heatmap__corner">
              <span aria-hidden>{home} ↓ · {away} →</span>
              <span className="visually-hidden">{home} goals by {away} goals</span>
            </th>
            {range.map((a) => (
              <th key={a} scope="col" className="num">{a}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {range.map((h) => (
            <tr key={h}>
              <th scope="row" className="num">{h}</th>
              {range.map((a) => {
                const p = grid[h][a];
                const isML = h === ml.home && a === ml.away;
                const intensity = Math.round((p / maxCell) * 55);
                const bg = `color-mix(in srgb, var(--home) ${intensity}%, var(--surface-1))`;
                return (
                  <td
                    key={a}
                    className={`num heat${isML ? " heat--ml" : ""}`}
                    style={{ background: bg }}
                    aria-label={`${home} ${h}, ${away} ${a}: ${pct(p)}${isML ? ", most likely scoreline" : ""}`}
                  >
                    {p >= 0.001 ? pct(p) : "—"}
                    {isML && <span aria-hidden className="heat__star">★</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
