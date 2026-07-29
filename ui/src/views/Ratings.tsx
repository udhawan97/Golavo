/**
 * Golavo Ratings — the in-house Elo tables.
 *
 * Computed from the same CC0 results the models train on, and leak-safe by
 * construction. It is explicitly not the FIFA ranking (nor a licensed club
 * rating); the header says so and every row carries its sample size, so the
 * reader can weigh a rating built on 90 matches against one built on 900.
 *
 * One scope at a time, deliberately. National teams are one pool because they
 * meet across confederations; club sides are ranked inside a single competition,
 * because the leagues in the index meet only through the thin 2020+ UEFA
 * fixtures. Putting both in one table would invite a comparison the data cannot
 * support.
 */
import { useState } from "react";
import type { RatingsTable as RatingsTableData, RatingRow } from "../lib/contract";
import { fetchClubRatings, fetchInternationalRatings } from "../lib/api";
import { LEAGUES, leagueHubCategory } from "../lib/leagues";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton, EmptyState, ErrorState } from "../components/states";
import { ChevronRight } from "../components/icons";

/** Internationals plus every club competition the catalog gives a stable id. */
export const RATING_SCOPES: { id: string; name: string; club: boolean }[] = [
  { id: "internationals", name: "Internationals", club: false },
  ...LEAGUES.filter(
    (league) => league.competitionId && leagueHubCategory(league) !== "international",
  ).map((league) => ({
    id: league.competitionId as string,
    name: league.name,
    club: true,
  })),
];

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

function RatingsTable({ table }: { table: RatingsTableData }) {
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
  const [scopeId, setScopeId] = useState(RATING_SCOPES[0].id);
  const scope = RATING_SCOPES.find((entry) => entry.id === scopeId) ?? RATING_SCOPES[0];
  const state = useAsync(
    () => (scope.club ? fetchClubRatings(scope.id, { topN: 40 }) : fetchInternationalRatings({ topN: 40 })),
    [scope.club, scope.id],
  );
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
          An Elo table Golavo computes from the same public results it trains on — goal-difference
          weighted, home advantage on non-neutral ground. <strong>Not the FIFA ranking</strong> and
          not an official rating. Coverage varies with how densely a competition's matches are
          recorded, so read a rating alongside its match count.
        </p>
      </header>
      <label className="stack" style={{ ["--gap" as string]: ".3rem" }}>
        <span className="small dim">Scope</span>
        <select value={scopeId} onChange={(event) => setScopeId(event.target.value)}>
          {RATING_SCOPES.map((entry) => (
            <option key={entry.id} value={entry.id}>
              {entry.name}
            </option>
          ))}
        </select>
      </label>
      <p className="small dim measure" style={{ margin: 0 }}>
        {scope.club
          ? "Club ratings are computed inside one competition. The leagues meet only through the 2020-21 onward UEFA fixtures, so a rating here is not comparable with one from another league."
          : "National teams are rated as a single pool, which their cross-confederation fixtures support."}
      </p>
      {state.status === "loading" ? (
        <BlockSkeleton lines={8} />
      ) : state.status === "error" ? (
        <ErrorState error={state.error} />
      ) : state.data.teams.length === 0 ? (
        <EmptyState title="Ratings unavailable">
          Connect the Golavo engine to compute the {scope.name} table.
        </EmptyState>
      ) : (
        <>
          <RatingsTable table={state.data} />
          <p className="small dim" style={{ margin: 0 }}>
            {state.data.matches_counted.toLocaleString()} completed {scope.name} matches counted.
            Leak-safe: a rating as of a date depends only on matches played by then.
          </p>
        </>
      )}
    </div>
  );
}
