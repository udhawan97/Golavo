/**
 * Leagues — a browse hub over bundled domestic and UEFA club competitions + internationals.
 *
 * Domestic leagues also expose their verified standings/simulation gate. The
 * outlook remains blocked until the local source proves a complete fixture list.
 */
import { useState } from "react";
import type { CompetitionAnalytics, StrengthPoint } from "../lib/contract";
import { fetchCompetitionAnalytics, fetchRecentMatches } from "../lib/api";
import { num, utcDate } from "../lib/format";
import { LEAGUES, leagueHubCategory } from "../lib/leagues";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton, EmptyState, ErrorState } from "../components/states";
import { ChevronRight } from "../components/icons";
import { Rail } from "./Matchday";
import { TournamentOutlook } from "../components/TournamentOutlook";
import { SeasonOutlook } from "../components/SeasonOutlook";

export { LEAGUES } from "../lib/leagues";

export function LeaguesHub() {
  const groups = [
    {
      id: "international-competitions",
      title: "International tournaments",
      leagues: LEAGUES.filter((league) => leagueHubCategory(league) === "international"),
    },
    {
      id: "domestic-leagues",
      title: "Domestic leagues",
      leagues: LEAGUES.filter((league) => leagueHubCategory(league) === "domestic"),
    },
    {
      id: "uefa-club-competitions",
      title: "UEFA club competitions",
      leagues: LEAGUES.filter((league) => leagueHubCategory(league) === "uefa-club"),
    },
  ];
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Leagues &amp; Europe</h1>
        <p className="measure dim" style={{ margin: 0 }}>
          Browse recent matches and open any one for the model council. Domestic standings rules are
          verified; season projections stay visibly blocked until every fixture is certified.
        </p>
      </header>
      {groups.map((group) => (
        <section
          key={group.id}
          className="stack"
          style={{ ["--gap" as string]: ".65rem" }}
          aria-labelledby={group.id}
        >
          <h2 id={group.id} className="upper muted" style={{ margin: 0 }}>{group.title}</h2>
          <div className="league-grid">
            {group.leagues.map((league) => (
              <a
                key={league.slug}
                className="league-card"
                href={`#/league/${league.slug}`}
              >
                <div className="league-card__name">{league.name}</div>
                <div className="league-card__note small muted">{league.note}</div>
                <ChevronRight size={16} />
              </a>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export function LeagueView({ slug }: { slug: string }) {
  const league = LEAGUES.find((l) => l.slug === slug);
  const state = useAsync(
    () =>
      league
        ? fetchRecentMatches(48, {
            competition: league.competition,
            sourceKind: league.sourceKind,
          })
        : Promise.reject(new Error("unknown league")),
    [slug],
  );
  const analyticsState = useAsync<CompetitionAnalytics | null>(
    () =>
      league?.competitionId
        ? fetchCompetitionAnalytics(league.competitionId)
        : Promise.resolve(null),
    [slug],
  );

  if (!league)
    return (
      <EmptyState title="Competition not found">
        No competition matches this address. <a href="#/leagues">All competitions ›</a>
      </EmptyState>
    );

  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/leagues">Leagues &amp; Europe</a>
        <ChevronRight size={14} />
        <span aria-current="page">{league.name}</span>
      </nav>
      <header className="stack" style={{ ["--gap" as string]: ".3rem" }}>
        <h1>{league.name}</h1>
        <p className="small dim" style={{ margin: 0 }}>{league.note}</p>
      </header>
      {league.slug === "world-cup-2026" && <TournamentOutlook />}
      {league.seasonOutlook && league.competitionId && (
        <SeasonOutlook competitionId={league.competitionId} />
      )}
      {league.competitionId &&
        (analyticsState.status === "loading" ? (
          <BlockSkeleton lines={5} />
        ) : analyticsState.status === "error" ? (
          <ErrorState error={analyticsState.error} />
        ) : analyticsState.data ? (
          <CompetitionAnalyticsPanel data={analyticsState.data} />
        ) : null)}
      {state.status === "loading" ? (
        <BlockSkeleton lines={6} />
      ) : state.status === "error" ? (
        <ErrorState error={state.error} />
      ) : (
        <div className="stack" style={{ ["--gap" as string]: "1.5rem" }}>
          <Rail
            title="Upcoming"
            matches={state.data.upcoming}
            emptyNote="No forward fixtures for this competition in the current snapshot."
          />
          <Rail
            title="Recent results"
            matches={state.data.recent}
            emptyNote="No matches for this competition in the snapshot."
          />
        </div>
      )}
    </div>
  );
}

function CompetitionAnalyticsPanel({ data }: { data: CompetitionAnalytics }) {
  const teams = data.strength_trends.teams;
  const [selectedTeam, setSelectedTeam] = useState(teams[0]?.team ?? "");
  const selected = teams.find((team) => team.team === selectedTeam) ?? teams[0];
  const workload = new Map(data.rest_congestion.teams.map((team) => [team.team, team]));

  return (
    <section className="stack league-analytics" style={{ ["--gap" as string]: "1rem" }}>
      <div className="hgroup">
        <div>
          <h2 className="upper muted" style={{ marginBottom: ".25rem" }}>Team analytics</h2>
          <p className="small dim" style={{ margin: 0 }}>
            Model-estimated strength inside this competition only. Context is descriptive and does
            not enter a forecast.
          </p>
        </div>
        {data.strength_trends.data_through_utc && (
          <span className="small dim">Results through {utcDate(data.strength_trends.data_through_utc)}</span>
        )}
      </div>

      {data.strength_trends.status !== "available" || !selected ? (
        <div className="callout callout--info" role="status">
          <div>
            <div className="callout__title">Strength trends unavailable</div>
            <p>{data.strength_trends.reason ?? "No eligible teams at this cutoff."}</p>
          </div>
        </div>
      ) : (
        <>
          <div className="analytics-focus card card--pad">
            <div className="analytics-focus__head">
              <label className="field">
                Team
                <select
                  className="select"
                  value={selected.team}
                  onChange={(event) => setSelectedTeam(event.target.value)}
                >
                  {teams.map((team) => <option key={team.team}>{team.team}</option>)}
                </select>
              </label>
              <div className="analytics-kpis" aria-label={`${selected.team} current strength`}>
                <Metric label="Overall" value={selected.current.overall_index} />
                <Metric label="Attack" value={selected.current.attack_index} />
                <Metric label="Defence" value={selected.current.defence_index} />
              </div>
            </div>
            <StrengthTrendChart team={selected.team} points={selected.trend} />
            <p className="small dim" style={{ margin: 0 }}>
              100 is the competition baseline; above 100 is stronger. Minimum {data.strength_trends.minimum_matches} matches.
            </p>
          </div>

          <div className="table-wrap">
            <table className="grid analytics-table">
              <thead>
                <tr>
                  <th scope="col">Team</th>
                  <th scope="col">Overall</th>
                  <th scope="col">Attack</th>
                  <th scope="col">Defence</th>
                  <th scope="col">Rest</th>
                  <th scope="col">Matches / 14d</th>
                  <th scope="col">Load</th>
                </tr>
              </thead>
              <tbody>
                {teams.map((team) => {
                  const load = workload.get(team.team);
                  return (
                    <tr key={team.team}>
                      <th scope="row">{team.team}</th>
                      <td className="num">{num(team.current.overall_index, 1)}</td>
                      <td className="num">{num(team.current.attack_index, 1)}</td>
                      <td className="num">{num(team.current.defence_index, 1)}</td>
                      <td>{load ? `${load.rest_days}d` : "—"}</td>
                      <td className="num">{load?.matches_last_14_days ?? "—"}</td>
                      <td><span className={`load-chip load-chip--${load?.congestion ?? "unknown"}`}>{load?.congestion ?? "unknown"}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="small dim" style={{ margin: 0 }}>{data.rest_congestion.coverage_note}</p>
        </>
      )}

      <div className="callout callout--info" role="note">
        <div>
          <div className="callout__title">Schedule difficulty not calculated</div>
          <p>{data.schedule_difficulty.reason}</p>
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="analytics-kpi">
      <span className="small muted">{label}</span>
      <strong className="num">{num(value, 1)}</strong>
    </div>
  );
}

function StrengthTrendChart({ team, points }: { team: string; points: StrengthPoint[] }) {
  if (points.length < 2) return <p className="muted small">Not enough checkpoints for a trend.</p>;
  const width = 680;
  const height = 180;
  const pad = 22;
  const values = points.map((point) => point.overall_index);
  const low = Math.min(90, ...values) - 5;
  const high = Math.max(110, ...values) + 5;
  const coordinates = points.map((point, index) => {
    const x = pad + (index / (points.length - 1)) * (width - pad * 2);
    const y = pad + ((high - point.overall_index) / (high - low)) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const baselineY = pad + ((high - 100) / (high - low)) * (height - pad * 2);
  return (
    <figure className="strength-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${team} overall strength trend`}>
        <line className="strength-chart__baseline" x1={pad} x2={width - pad} y1={baselineY} y2={baselineY} />
        <polyline className="strength-chart__line" points={coordinates.join(" ")} />
        {coordinates.map((coordinate, index) => {
          const [cx, cy] = coordinate.split(",");
          return <circle key={points[index].cutoff_utc} className="strength-chart__point" cx={cx} cy={cy} r="3" />;
        })}
      </svg>
      <figcaption className="small dim">
        {utcDate(points[0].cutoff_utc)}–{utcDate(points[points.length - 1].cutoff_utc)} · month-end cutoffs
      </figcaption>
    </figure>
  );
}
