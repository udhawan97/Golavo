import { useEffect, useState } from "react";
import type {
  SeasonForcedResult,
  SeasonImportanceClub,
  SeasonImportanceSwings,
  SeasonOutlook as Outlook,
  SeasonOutlookTeam,
  SeasonOutlookVoice,
  SeasonRemainingFixture,
  SeasonStandingRow,
} from "../lib/contract";
import { fetchSeasonOutlook, fetchSeasonScenario } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton } from "./states";
import { ScrollableTable } from "./ScrollableTable";

const VOICE_COPY: Record<SeasonOutlookVoice["voice_id"], string> = {
  elo_ordlogit: "Ratings",
  dixon_coles: "Goals",
  "equal-chance-baseline": "Baseline",
};

const STAKE_COPY: Record<keyof SeasonImportanceSwings, string> = {
  title: "title",
  top_four: "top-four",
  relegation: "relegation",
};

/** How many upcoming fixtures the run-in shows per club. */
export const RUN_IN_LENGTH = 5;

export type OpponentBand = "tough" | "even" | "kind";

/**
 * Bands opponents by the same voice's projected finish, so the run-in never
 * joins a second rating source into a table built from one simulation.
 */
export function opponentBands(teams: SeasonOutlookTeam[]): Map<string, OpponentBand> {
  const ranked = teams
    .filter((team) => typeof team.expected_points === "number")
    .slice()
    .sort((left, right) => (right.expected_points ?? 0) - (left.expected_points ?? 0));
  const third = Math.ceil(ranked.length / 3);
  const bands = new Map<string, OpponentBand>();
  ranked.forEach((team, index) => {
    const band: OpponentBand =
      index < third ? "tough" : index < ranked.length - third ? "even" : "kind";
    bands.set(team.team, band);
  });
  return bands;
}

/** The reported swing for one club in one fixture, or null when it abstained. */
export function clubImportance(
  fixture: SeasonRemainingFixture,
  team: string,
): SeasonImportanceClub | null {
  if (fixture.importance?.status !== "ok") return null;
  return fixture.importance.clubs.find((club) => club.team === team) ?? null;
}

/** The stake a club has most riding on a fixture. */
export function topStake(club: SeasonImportanceClub): keyof SeasonImportanceSwings | null {
  const swings = club.swings;
  if (!swings) return null;
  let best: keyof SeasonImportanceSwings = "title";
  for (const stake of ["top_four", "relegation"] as const) {
    if (swings[stake] > swings[best]) best = stake;
  }
  return best;
}

export function scenarioRequest(
  fixture: SeasonRemainingFixture,
  homeScore: number,
  awayScore: number,
): SeasonForcedResult[] {
  if (![homeScore, awayScore].every((score) => Number.isInteger(score) && score >= 0 && score <= 20)) {
    throw new Error("Scenario scores must be whole numbers from 0 to 20.");
  }
  return [{ match_id: fixture.match_id, home_score: homeScore, away_score: awayScore }];
}

function Table({ rows }: { rows: SeasonStandingRow[] }) {
  return (
    <ScrollableTable label="Current season table" cue="More: points and recent form">
      <table className="grid season-table">
        <thead>
          <tr>
            <th scope="col">#</th><th scope="col">Team</th><th scope="col">P</th>
            <th scope="col">GD</th><th scope="col">Pts</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.team}>
              <td className="num">{row.position}</td><th scope="row">{row.team}</th>
              <td className="num">{row.played}</td>
              <td className="num">{row.goal_difference > 0 ? "+" : ""}{row.goal_difference}</td>
              <td className="num"><strong>{row.points}</strong></td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTable>
  );
}

export function RunIn({ outlook }: { outlook: Outlook }) {
  const voiceId = outlook.remaining_fixtures.find((fixture) => fixture.importance)?.importance
    ?.voice_id;
  const voice = outlook.voices.find((item) => item.voice_id === voiceId);
  if (!voice || outlook.remaining_fixtures.length === 0) return null;
  const bands = opponentBands(voice.teams);
  const projected = new Map(voice.teams.map((team) => [team.team, team.expected_points]));
  const rows = outlook.current_table.map((row) => ({
    team: row.team,
    expected: projected.get(row.team),
    fixtures: outlook.remaining_fixtures
      .filter((fixture) => fixture.home_team === row.team || fixture.away_team === row.team)
      .slice(0, RUN_IN_LENGTH),
  }));
  return (
    <section className="stack" style={{ ["--gap" as string]: ".5rem" }}>
      <h3 className="run-in-title">The run-in</h3>
      <p className="small dim">
        Projected points and the next {RUN_IN_LENGTH} opponents, from the{" "}
        {VOICE_COPY[voice.voice_id]} voice&apos;s runs. A badge shows how far winning instead of
        losing moves that club&apos;s biggest season stake, in percentage points. Fixtures whose
        conditional branches were too thin to read carry no badge.
      </p>
      <ScrollableTable label="Run-in" cue="More: upcoming opponents">
        <table className="grid run-in-table">
          <thead>
            <tr>
              <th scope="col">Team</th>
              <th scope="col">Projected pts</th>
              <th scope="col">Next {RUN_IN_LENGTH}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.team}>
                <th scope="row">{row.team}</th>
                <td className="num">
                  {typeof row.expected === "number" ? row.expected.toFixed(1) : "—"}
                </td>
                <td>
                  <ul className="run-in-chips">
                    {row.fixtures.map((fixture) => {
                      const atHome = fixture.home_team === row.team;
                      const opponent = atHome ? fixture.away_team : fixture.home_team;
                      const club = clubImportance(fixture, row.team);
                      const stake = club ? topStake(club) : null;
                      return (
                        <li key={fixture.match_id}>
                          <span
                            className={`chip run-in-chip run-in-chip--${bands.get(opponent) ?? "even"}`}
                          >
                            <span className="run-in-chip__side">{atHome ? "H" : "A"}</span>
                            {opponent}
                            {club?.score != null && stake && (
                              <span
                                className="run-in-chip__swing"
                                title={`Winning instead of losing moves ${row.team}'s ${STAKE_COPY[stake]} chance by ${Math.round(club.score * 100)} percentage points.`}
                              >
                                {Math.round(club.score * 100)}pp
                              </span>
                            )}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollableTable>
    </section>
  );
}

export function SeasonOutlookBody({ outlook }: { outlook: Outlook }) {
  const [voiceId, setVoiceId] = useState<SeasonOutlookVoice["voice_id"]>("elo_ordlogit");
  if (outlook.status !== "available") {
    const title = outlook.status === "complete"
      ? "Season complete"
      : outlook.reason_code === "fixtures_not_published"
        ? "Waiting for the complete fixture list"
        : "Season outlook blocked";
    return (
      <>
        <div className="callout callout--info" role="status">
          <div><div className="callout__title">{title}</div><p>{outlook.reason}</p></div>
        </div>
        {outlook.current_table.length > 0 && <Table rows={outlook.current_table} />}
      </>
    );
  }
  const selected = outlook.voices.find((voice) => voice.voice_id === voiceId) ?? outlook.voices[0];
  return (
    <>
      <div className="outlook-voices" role="group" aria-label="Model voice">
        {outlook.voices.map((voice) => (
          <button
            key={voice.voice_id}
            type="button"
            className={voice.voice_id === selected.voice_id ? "is-active" : ""}
            aria-pressed={voice.voice_id === selected.voice_id}
            onClick={() => setVoiceId(voice.voice_id)}
          >
            {VOICE_COPY[voice.voice_id]}
          </button>
        ))}
      </div>
      <ScrollableTable
        label={`${VOICE_COPY[selected.voice_id]} season probabilities`}
        cue="More: model probabilities"
      >
        <table className="grid season-probability-table">
          <thead><tr><th scope="col">Team</th><th scope="col">Title</th><th scope="col">Top 4</th><th scope="col">Relegation</th></tr></thead>
          <tbody>
            {selected.teams.map((team) => (
              <tr key={team.team}>
                <th scope="row">{team.team}</th>
                <td className="num">{team.display_percent.title.toFixed(1)}%</td>
                <td className="num">{team.display_percent.top_four.toFixed(1)}%</td>
                <td className="num">{team.display_percent.relegation.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollableTable>
      <RunIn outlook={outlook} />
      <details className="outlook-method">
        <summary>How this season is simulated</summary>
        <p>
          {outlook.iterations.toLocaleString()} seeded runs over a certified complete fixture list.
          Each tab stays separate, and no result is written to the forecast ledger.
        </p>
        <p className="small dim">Rule {outlook.simulation_rule} · {selected.scoreline_method} · seed {outlook.seed}.</p>
      </details>
    </>
  );
}

function ScenarioBuilder({
  outlook,
  onResult,
  onReset,
}: {
  outlook: Outlook;
  onResult: (result: Outlook) => void;
  onReset: () => void;
}) {
  const [fixtureId, setFixtureId] = useState(outlook.remaining_fixtures[0]?.match_id ?? "");
  const [homeScore, setHomeScore] = useState(1);
  const [awayScore, setAwayScore] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fixture = outlook.remaining_fixtures.find((item) => item.match_id === fixtureId);
  const scoresValid = [homeScore, awayScore].every(
    (score) => Number.isInteger(score) && score >= 0 && score <= 20,
  );

  async function run() {
    if (!fixture || !scoresValid) return;
    setBusy(true);
    setError(null);
    try {
      const result = await fetchSeasonScenario(
        outlook.competition_id,
        scenarioRequest(fixture, homeScore, awayScore),
        { asOfUtc: outlook.as_of_utc, season: outlook.season },
      );
      onResult(result);
    } catch {
      setError("The local engine could not run this conditional scenario.");
    } finally {
      setBusy(false);
    }
  }

  if (outlook.remaining_fixtures.length === 0) return null;
  return (
    <details className="outlook-method season-scenario">
      <summary>Try one conditional result</summary>
      <div className="stack" style={{ ["--gap" as string]: ".7rem" }}>
        <p className="small dim">
          Hypothetical only. The result is never saved, sealed, or used as model input.
        </p>
        <label className="field">
          Fixture
          <select className="select" value={fixtureId} onChange={(event) => setFixtureId(event.target.value)}>
            {outlook.remaining_fixtures.map((item) => (
              <option key={item.match_id} value={item.match_id}>
                {item.home_team} vs {item.away_team}
              </option>
            ))}
          </select>
        </label>
        <div className="correction-two-col">
          <label className="field">
            Home score
            <input
              type="number"
              min="0"
              max="20"
              step="1"
              value={homeScore}
              onChange={(event) => setHomeScore(Number(event.target.value))}
            />
          </label>
          <label className="field">
            Away score
            <input
              type="number"
              min="0"
              max="20"
              step="1"
              value={awayScore}
              onChange={(event) => setAwayScore(Number(event.target.value))}
            />
          </label>
        </div>
        <div className="cluster">
          <button type="button" className="btn btn--primary" disabled={busy || !fixture || !scoresValid} onClick={() => void run()}>
            {busy ? "Running…" : "Run conditional scenario"}
          </button>
          {outlook.scenario && (
            <button type="button" className="btn" onClick={onReset}>Reset to verified outlook</button>
          )}
        </div>
        {error && <p className="small" role="alert">{error}</p>}
      </div>
    </details>
  );
}

export function SeasonOutlook({ competitionId }: { competitionId: string }) {
  const state = useAsync(() => fetchSeasonOutlook(competitionId), [competitionId]);
  const [scenario, setScenario] = useState<Outlook | null>(null);
  useEffect(() => setScenario(null), [competitionId]);
  const displayed = state.status === "ready" && scenario?.competition_id === competitionId
    ? scenario
    : state.status === "ready" ? state.data : null;
  return (
    <section className="season-outlook stack" style={{ ["--gap" as string]: ".85rem" }} aria-labelledby="season-outlook-title">
      <header className="hgroup">
        <div>
          <span className="upper">Domestic league</span>
          <h2 id="season-outlook-title">Season outlook</h2>
          <p className="small dim">Verified standings rules; projections require every fixture.</p>
        </div>
        <span className="chip chip--neutral">
          {displayed?.scenario ? "Conditional · never saved" : "Simulation · not a seal"}
        </span>
      </header>
      {state.status === "loading" ? <BlockSkeleton lines={4} /> : state.status === "error" ? (
        <div className="callout callout--info" role="status">
          <div><div className="callout__title">Season outlook unavailable</div><p>The local season state could not be read.</p></div>
        </div>
      ) : (
        <>
          {displayed?.scenario && (
            <div className="callout callout--info" role="status">
              <div>
                <div className="callout__title">Conditional result applied</div>
                <p>This table exists only in this view. It is not a forecast or a saved result.</p>
              </div>
            </div>
          )}
          <SeasonOutlookBody outlook={displayed ?? state.data} />
          {state.data.status === "available" && (
            <ScenarioBuilder
              outlook={displayed ?? state.data}
              onResult={setScenario}
              onReset={() => setScenario(null)}
            />
          )}
        </>
      )}
    </section>
  );
}
