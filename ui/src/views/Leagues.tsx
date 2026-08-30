/**
 * Leagues — a browse hub over bundled domestic and UEFA club competitions + internationals.
 *
 * Domestic leagues also expose their verified standings/simulation gate. A
 * complete fixture certificate is necessary but not sufficient: the outlook
 * remains blocked whenever the approved source has past-result gaps.
 */
import { useState } from "react";
import type {
  CompetitionAnalytics,
  CurrentSeasonPulse,
  ScheduleDifficulty,
  StrengthPoint,
} from "../lib/contract";
import { fetchCompetitionAnalytics, fetchRecentMatches } from "../lib/api";
import { num, pct, utcDate } from "../lib/format";
import { LEAGUES, leagueHubCategory } from "../lib/leagues";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton, EmptyState, ErrorState } from "../components/states";
import { ChevronRight } from "../components/icons";
import { Rail } from "./Matchday";
import { TournamentOutlook } from "../components/TournamentOutlook";
import { SeasonOutlook } from "../components/SeasonOutlook";
import { ScorersPanel } from "../components/ScorersPanel";
import { ResearchTeamAnalytics } from "../components/ResearchTeamAnalytics";

export { LEAGUES } from "../lib/leagues";

export function LeaguesHub() {
  const groups = [
    {
      id: "domestic-leagues",
      title: "Live domestic seasons · 2026–27",
      leagues: LEAGUES.filter((league) => leagueHubCategory(league) === "domestic"),
    },
    {
      id: "uefa-club-competitions",
      title: "UEFA club competitions",
      leagues: LEAGUES.filter((league) => leagueHubCategory(league) === "uefa-club"),
    },
    {
      id: "international-competitions",
      title: "Internationals & archives",
      leagues: LEAGUES.filter((league) => leagueHubCategory(league) === "international"),
    },
  ];
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <span className="upper">Current season first</span>
        <h1>Leagues &amp; 2026–27</h1>
        <p className="measure dim" style={{ margin: 0 }}>
          Start with live domestic fixtures, tables, form and model projections. Historical seasons
          stay available as training context, while completed tournaments sit in the archive.
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

  const category = leagueHubCategory(league);
  const isLiveDomestic = category === "domestic";
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/leagues">Leagues &amp; Europe</a>
        <ChevronRight size={14} />
        <span aria-current="page">{league.name}</span>
      </nav>
      <header className={`league-hero${isLiveDomestic ? " league-hero--live" : ""}`}>
        <div className="stack" style={{ ["--gap" as string]: ".35rem" }}>
          <span className="upper">
            {isLiveDomestic ? "2026–27 live season desk" : league.archived ? "Completed tournament archive" : "Competition desk"}
          </span>
          <h1>{league.name}</h1>
          <p className="measure dim" style={{ margin: 0 }}>{league.note}</p>
          {isLiveDomestic && (
            <div className="league-hero__actions">
              <a className="btn" href="#current-fixtures">Predict the next match</a>
              <a className="btn btn--ghost" href="#current-form">Current form</a>
            </div>
          )}
        </div>
        {isLiveDomestic && (
          <aside className="league-hero__source" aria-label="Current-season data coverage">
            <strong>Current data lane</strong>
            <span>CC0 fixtures + results</span>
            <span>Cutoff-safe table and form</span>
            <span>Optional BYOK match player lens</span>
            <a href="#/settings">Sources &amp; player data ›</a>
          </aside>
        )}
      </header>
      {league.slug === "world-cup-2026" && <TournamentOutlook />}
      {league.competitionId && isLiveDomestic && (
        <div id="current-form">
          {analyticsState.status === "loading" ? (
            <BlockSkeleton lines={3} />
          ) : analyticsState.status === "error" ? (
            <ErrorState error={analyticsState.error} />
          ) : analyticsState.data ? (
            <CurrentSeasonPulsePanel pulse={analyticsState.data.current_season} />
          ) : null}
        </div>
      )}
      <div id="current-fixtures">
        {state.status === "loading" ? (
          <BlockSkeleton lines={6} />
        ) : state.status === "error" ? (
          <ErrorState error={state.error} />
        ) : (
          <div className="stack" style={{ ["--gap" as string]: "1.5rem" }}>
            <Rail
              key={`${league.slug}-upcoming`}
              title="Upcoming · predict & compare"
              matches={state.data.upcoming}
              emptyNote="No forward fixtures for this competition in the current snapshot."
              pageSize={6}
            />
            <Rail
              key={`${league.slug}-recent`}
              title="Latest results"
              matches={state.data.recent}
              emptyNote="No matches for this competition in the snapshot."
              pageSize={6}
            />
          </div>
        )}
      </div>
      {league.seasonOutlook && league.competitionId && (
        <SeasonOutlook competitionId={league.competitionId} />
      )}
      {league.competitionId &&
        (analyticsState.status === "loading" ? (
          isLiveDomestic ? null : <BlockSkeleton lines={5} />
        ) : analyticsState.status === "error" ? (
          isLiveDomestic ? null : <ErrorState error={analyticsState.error} />
        ) : analyticsState.data ? (
          isLiveDomestic ? (
            <details className="history-archive">
              <summary>
                <span><strong>Historical model inputs</strong><small>Strength, workload and run-in context derived from older results</small></span>
                <span aria-hidden>+</span>
              </summary>
              <div className="history-archive__body">
                <CompetitionAnalyticsPanel data={analyticsState.data} />
              </div>
            </details>
          ) : (
            <CompetitionAnalyticsPanel data={analyticsState.data} />
          )
        ) : null)}
      {league.scorers && league.competitionId && (
        <ScorersPanel competitionId={league.competitionId} />
      )}
      {league.researchAnalytics && league.competitionId && (
        <details className="history-archive">
          <summary>
            <span><strong>Historical research archive</strong><small>Older event data · model context, not the live-season headline</small></span>
            <span aria-hidden>+</span>
          </summary>
          <div className="history-archive__body">
            <ResearchTeamAnalytics competitionId={league.competitionId} />
          </div>
        </details>
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
          <span className="upper">Historical model input</span>
          <h2 style={{ marginBottom: ".25rem" }}>Strength, workload &amp; run-in</h2>
          <p className="small dim" style={{ margin: 0 }}>
            Old results estimate competition-local strength. This context sits below the current record and never replaces it.
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

      <ScheduleDifficultySection difficulty={data.schedule_difficulty} />
    </section>
  );
}

function CurrentSeasonPulsePanel({ pulse }: { pulse: CurrentSeasonPulse }) {
  if (pulse.status !== "available") {
    return (
      <div className="callout callout--info" role="status">
        <div>
          <div className="callout__title">Current-season pulse unavailable</div>
          <p>{pulse.reason}</p>
        </div>
      </div>
    );
  }
  return (
    <section className="season-pulse stack" style={{ ["--gap" as string]: ".8rem" }} aria-labelledby="season-pulse-title">
      <div className="hgroup">
        <div>
          <span className="upper">Live record</span>
          <h3 id="season-pulse-title">{pulse.season.replace("-", "–")} season pulse</h3>
        </div>
        <span className={`chip ${pulse.fixture_list_complete ? "chip--ok" : "chip--neutral"}`}>
          {pulse.fixture_list_complete ? "Fixture list certified" : "Partial fixture list"}
        </span>
      </div>
      <div className="season-pulse__metrics" aria-label="Current season league statistics">
        <PulseMetric label="Played" value={`${pulse.matches_played ?? 0} / ${pulse.expected_matches ?? "—"}`} />
        <PulseMetric label="Future" value={String(pulse.matches_remaining ?? 0)} />
        <PulseMetric label="Result gaps" value={String(pulse.past_result_gaps ?? 0)} />
        <PulseMetric label="Goals / match" value={num(pulse.goals_per_match ?? 0, 2)} />
        <PulseMetric label="Home wins" value={pct(pulse.home_win_rate ?? 0)} />
        <PulseMetric label="Draws" value={pct(pulse.draw_rate ?? 0)} />
        <PulseMetric label="Both scored" value={pct(pulse.both_teams_scored_rate ?? 0)} />
        <PulseMetric label="Over 2.5" value={pct(pulse.over_2_5_rate ?? 0)} />
      </div>
      {pulse.teams.length > 0 && (
        <details className="season-pulse__details">
          <summary>
            <span><strong>Open the {pulse.teams.length}-team form board</strong><small>Last five, points rate, scoring, clean sheets and BTTS</small></span>
            <span aria-hidden>+</span>
          </summary>
          <div className="table-wrap">
            <table className="grid season-pulse__table">
              <thead><tr>
                <th scope="col">Team</th><th scope="col">Form</th><th scope="col">PPG</th>
                <th scope="col">GF / match</th><th scope="col">GA / match</th>
                <th scope="col">Clean sheets</th><th scope="col">BTTS</th>
              </tr></thead>
              <tbody>
                {pulse.teams.map((team) => (
                  <tr key={team.team}>
                    <th scope="row">{team.team}</th>
                    <td><span className="form-strip" role="img" aria-label={`${team.team} last ${team.recent_form.length}: ${team.recent_form.join(", ")}`}>
                      {team.recent_form.length > 0 ? team.recent_form.map((result, index) => (
                        <span className={`form-dot form-dot--${result.toLowerCase()}`} key={`${result}-${index}`} aria-hidden>{result}</span>
                      )) : <span className="dim">—</span>}
                    </span></td>
                    <td className="num">{num(team.points_per_game, 2)}</td>
                    <td className="num">{num(team.goals_for_per_match, 2)}</td>
                    <td className="num">{num(team.goals_against_per_match, 2)}</td>
                    <td className="num">{team.clean_sheets}</td>
                    <td className="num">{team.both_teams_scored}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      <p className="small dim" style={{ margin: 0 }}>
        Completed matches only, cut off at {pulse.data_through_utc ? utcDate(pulse.data_through_utc) : "the current snapshot"}.
        {pulse.past_result_gaps ? ` ${pulse.past_result_gaps} past result gap${pulse.past_result_gaps === 1 ? " is" : "s are"} held back, not counted as future fixtures.` : ""}
        {" "}Counts are descriptive and never alter a sealed forecast.
        {pulse.source_ids?.length ? ` Sources: ${pulse.source_ids.join(", ")}.` : ""}
      </p>
    </section>
  );
}

function PulseMetric({ label, value }: { label: string; value: string }) {
  return <div className="season-pulse__metric"><span>{label}</span><strong className="num">{value}</strong></div>;
}

/** The remaining run-in, hardest first — or the honest reason there isn't one. */
function ScheduleDifficultySection({ difficulty }: { difficulty: ScheduleDifficulty }) {
  if (difficulty.status !== "available" || difficulty.teams.length === 0) {
    return (
      <div className="callout callout--info" role="note">
        <div>
          <div className="callout__title">Schedule difficulty not calculated</div>
          <p>{difficulty.reason}</p>
        </div>
      </div>
    );
  }
  return (
    <>
      <h3>Remaining schedule {difficulty.season ? `· ${difficulty.season.replace("-", "–")}` : ""}</h3>
      <div className="table-wrap">
        <table className="grid analytics-table">
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Team</th>
              <th scope="col">Left</th>
              <th scope="col">Home</th>
              <th scope="col">Mean opponent rating</th>
            </tr>
          </thead>
          <tbody>
            {difficulty.teams.map((team) => (
              <tr key={team.team}>
                <td className="num">{team.rank}</td>
                <th scope="row">{team.team}</th>
                <td className="num">{team.matches_remaining}</td>
                <td className="num dim">{team.home_remaining}</td>
                <td className="num">{num(team.mean_opponent_rating, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small dim measure" style={{ margin: 0 }}>
        Hardest run-in first, scored with this competition's own Golavo Ratings. Before a season
        starts every side plays every other, so the only difference is that a team never faces
        itself — the spread widens as fixtures are played off.
      </p>
    </>
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
