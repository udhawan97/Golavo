import { useEffect, useState } from "react";
import type {
  SeasonForcedResult,
  SeasonOutlook as Outlook,
  SeasonOutlookVoice,
  SeasonRemainingFixture,
  SeasonStandingRow,
} from "../lib/contract";
import { fetchSeasonOutlook, fetchSeasonScenario } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton } from "./states";

const VOICE_COPY: Record<SeasonOutlookVoice["voice_id"], string> = {
  elo_ordlogit: "Ratings",
  dixon_coles: "Goals",
  "equal-chance-baseline": "Baseline",
};

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
    <div className="table-wrap">
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
    </div>
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
      <div className="table-wrap">
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
      </div>
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
