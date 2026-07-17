/**
 * Golavo Ratings — the in-house national-team Elo table.
 *
 * Computed from the same CC0 results the models train on, and leak-safe by
 * construction. It is explicitly not the FIFA ranking; the header says so and
 * every row carries its sample size, so the reader can weigh a rating built on
 * 90 matches against one built on 900.
 */
import type { InternationalRatings, RatingRow } from "../lib/contract";
import { fetchInternationalRatings } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton, EmptyState, ErrorState } from "../components/states";
import { ChevronRight } from "../components/icons";

/** A minimal inline sparkline of a team's rating across the monthly checkpoints. */
function Trend({ row }: { row: RatingRow }) {
  const points = row.history.map((point) => point.rating);
  if (points.length < 2) return <span className="dim small">—</span>;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const width = 88;
  const height = 22;
  const step = width / (points.length - 1);
  const d = points
    .map((value, index) => {
      const x = index * step;
      const y = height - ((value - min) / span) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const rising = points[points.length - 1] >= points[0];
  return (
    <svg
      className="rating-trend"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Rating trend, ${rising ? "rising" : "falling"}`}
    >
      <path d={d} fill="none" stroke={rising ? "var(--positive, #0b6e4f)" : "var(--text-dim)"} strokeWidth="1.5" />
    </svg>
  );
}

function RatingsTable({ table }: { table: InternationalRatings }) {
  return (
    <div className="table-wrap">
      <table className="grid ratings-table">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Team</th>
            <th scope="col">Rating</th>
            <th scope="col">Matches</th>
            <th scope="col">12-month trend</th>
          </tr>
        </thead>
        <tbody>
          {table.teams.map((row) => (
            <tr key={row.team}>
              <td className="num">{row.rank}</td>
              <th scope="row">{row.team}</th>
              <td className="num">
                <strong>{Math.round(row.rating)}</strong>
              </td>
              <td className="num dim">{row.matches.toLocaleString()}</td>
              <td>
                <Trend row={row} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Ratings() {
  const state = useAsync(() => fetchInternationalRatings({ topN: 40 }), []);
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/lab">Model Lab</a>
        <ChevronRight size={14} />
        <span aria-current="page">Golavo Ratings</span>
      </nav>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Golavo Ratings</h1>
        <p className="measure dim" style={{ margin: 0 }}>
          A national-team Elo table Golavo computes from the same public results it trains on —
          goal-difference weighted, home advantage on non-neutral ground.{" "}
          <strong>Not the FIFA ranking</strong> and not an official rating. Confederation coverage
          varies with how densely a region's matches are recorded, so read a rating alongside its
          match count.
        </p>
      </header>
      {state.status === "loading" ? (
        <BlockSkeleton lines={8} />
      ) : state.status === "error" ? (
        <ErrorState error={state.error} />
      ) : state.data.teams.length === 0 ? (
        <EmptyState title="Ratings unavailable">
          Connect the Golavo engine to compute the national-team table.
        </EmptyState>
      ) : (
        <>
          <RatingsTable table={state.data} />
          <p className="small dim" style={{ margin: 0 }}>
            {state.data.matches_counted.toLocaleString()} completed internationals counted.
            Leak-safe: a rating as of a date depends only on matches played by then.
          </p>
        </>
      )}
    </div>
  );
}
