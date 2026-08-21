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
export const MAX_SCENARIO_RESULTS = 12;

export type OpponentBand = "tough" | "even" | "kind";

export interface SeasonScenarioDraft {
  id: number;
  fixtureId: string;
  homeScore: number;
  awayScore: number;
}

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
  fixtures: SeasonRemainingFixture[],
  drafts: SeasonScenarioDraft[],
): SeasonForcedResult[] {
  if (drafts.length === 0 || drafts.length > MAX_SCENARIO_RESULTS) {
    throw new Error(`A scenario needs 1 to ${MAX_SCENARIO_RESULTS} results.`);
  }
  const fixtureIds = new Set(fixtures.map((fixture) => fixture.match_id));
  const selected = new Set<string>();
  return drafts.map((draft) => {
    if (!fixtureIds.has(draft.fixtureId)) {
      throw new Error("Every scenario result must use an available future fixture.");
    }
    if (selected.has(draft.fixtureId)) {
      throw new Error("Each fixture can appear only once in a scenario.");
    }
    selected.add(draft.fixtureId);
    if (![draft.homeScore, draft.awayScore].every(
      (score) => Number.isInteger(score) && score >= 0 && score <= 20,
    )) {
      throw new Error("Scenario scores must be whole numbers from 0 to 20.");
    }
    return {
      match_id: draft.fixtureId,
      home_score: draft.homeScore,
      away_score: draft.awayScore,
    };
  });
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

/** A club whose row rests on the model's prior rather than on evidence about it.
 *  "unknown" counts too: the field exists to withhold confidence, so anything
 *  that is not an affirmative "ok" is treated as a caveat rather than ignored. */
function belowModelFloor(team: SeasonOutlookTeam): boolean {
  const status = team.history_coverage?.status;
  return status !== undefined && status !== "ok";
}

/** "A", "A and B", "A, B and C" — a season can promote more than two clubs. */
function nameList(names: string[]): string {
  if (names.length <= 1) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

function ThinHistoryChip({ team }: { team: SeasonOutlookTeam }) {
  const coverage = team.history_coverage;
  if (!coverage || coverage.status === "ok") return null;
  return (
    <span
      className="season-probability-table__thin"
      title={`${coverage.matches} of the ${coverage.model_floor} recent matches this competition's models need. This row is the model's prior, not evidence about ${team.team}.`}
    >
      no model history
    </span>
  );
}

function ThinHistoryNote({ teams }: { teams: SeasonOutlookTeam[] }) {
  const thin = teams.filter(belowModelFloor);
  if (thin.length === 0) return null;
  return (
    <p className="season-probability-table__note" role="note">
      {nameList(thin.map((team) => team.team))}
      {thin.length > 1 ? " have" : " has"} no recent history in this competition, so the
      per-match council abstains on {thin.length > 1 ? "their" : "its"} fixtures. The
      {thin.length > 1 ? " rows above are" : " row above is"} the model&rsquo;s prior filling
      a gap it cannot measure, and the voices disagree most exactly there.
    </p>
  );
}

function ProbabilityTable({ voice }: { voice: SeasonOutlookVoice }) {
  // A club below the model floor still has to be simulated — the other clubs'
  // projections depend on it — but its row rests on the model's prior, not on
  // evidence about that club. Say so beside the number instead of leaving the
  // reader to assume the whole table is equally grounded.
  return (
    <>
      <ScrollableTable
        label={`${VOICE_COPY[voice.voice_id]} season probabilities`}
        cue="More: model probabilities"
      >
        <table className="grid season-probability-table">
          <thead><tr><th scope="col">Team</th><th scope="col">Title</th><th scope="col">Top 4</th><th scope="col">Relegation</th></tr></thead>
          <tbody>
            {voice.teams.map((team) => {
              return (
                <tr key={team.team}>
                  <th scope="row">{team.team}<ThinHistoryChip team={team} /></th>
                  <td className="num">{team.display_percent.title.toFixed(1)}%</td>
                  <td className="num">{team.display_percent.top_four.toFixed(1)}%</td>
                  <td className="num">{team.display_percent.relegation.toFixed(1)}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </ScrollableTable>
      <ThinHistoryNote teams={voice.teams} />
    </>
  );
}

function ProbabilityComparison({
  canonical,
  conditional,
  voiceId,
}: {
  canonical: Outlook;
  conditional: Outlook;
  voiceId: SeasonOutlookVoice["voice_id"];
}) {
  const verified = canonical.voices.find((voice) => voice.voice_id === voiceId);
  const scenario = conditional.voices.find((voice) => voice.voice_id === voiceId);
  if (!verified || !scenario) {
    return (
      <div className="callout callout--info" role="status">
        <div>
          <div className="callout__title">Conditional comparison unavailable</div>
          <p>The local response did not include the same model voice on both sides.</p>
        </div>
      </div>
    );
  }
  const verifiedTeamNames = new Set(verified.teams.map((team) => team.team));
  const scenarioByTeam = new Map(scenario.teams.map((team) => [team.team, team]));
  if (
    verifiedTeamNames.size !== verified.teams.length
    || scenarioByTeam.size !== scenario.teams.length
    || verifiedTeamNames.size !== scenarioByTeam.size
    || [...verifiedTeamNames].some((team) => !scenarioByTeam.has(team))
  ) {
    return (
      <div className="callout callout--info" role="status">
        <div>
          <div className="callout__title">Conditional comparison unavailable</div>
          <p>The local response did not include the same unique team set on both sides.</p>
        </div>
      </div>
    );
  }
  return (
    <>
    <ScrollableTable
      label={`${VOICE_COPY[voiceId]} verified and conditional season probabilities`}
      cue="More: verified and conditional probabilities"
    >
      <table className="grid season-comparison-table">
        <thead>
          <tr>
            <th scope="col" rowSpan={2}>Team</th>
            <th scope="colgroup" colSpan={2}>Title</th>
            <th scope="colgroup" colSpan={2}>Top 4</th>
            <th scope="colgroup" colSpan={2}>Relegation</th>
          </tr>
          <tr>
            <th scope="col">Verified</th><th scope="col" className="season-comparison__conditional">Conditional</th>
            <th scope="col">Verified</th><th scope="col" className="season-comparison__conditional">Conditional</th>
            <th scope="col">Verified</th><th scope="col" className="season-comparison__conditional">Conditional</th>
          </tr>
        </thead>
        <tbody>
          {verified.teams.map((team) => {
            const compared = scenarioByTeam.get(team.team);
            return (
              <tr key={team.team}>
                <th scope="row">{team.team}<ThinHistoryChip team={team} /></th>
                <td className="num">{team.display_percent.title.toFixed(1)}%</td>
                <td className="num season-comparison__conditional">{compared ? `${compared.display_percent.title.toFixed(1)}%` : "—"}</td>
                <td className="num">{team.display_percent.top_four.toFixed(1)}%</td>
                <td className="num season-comparison__conditional">{compared ? `${compared.display_percent.top_four.toFixed(1)}%` : "—"}</td>
                <td className="num">{team.display_percent.relegation.toFixed(1)}%</td>
                <td className="num season-comparison__conditional">{compared ? `${compared.display_percent.relegation.toFixed(1)}%` : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </ScrollableTable>
    <ThinHistoryNote teams={verified.teams} />
    </>
  );
}

export function RunIn({ outlook }: { outlook: Outlook }) {
  const voiceId = outlook.remaining_fixtures.find((fixture) => fixture.importance)?.importance
    ?.voice_id;
  const voice = outlook.voices.find((item) => item.voice_id === voiceId);
  if (!voice || outlook.remaining_fixtures.length === 0) return null;
  const bands = opponentBands(voice.teams);
  const projected = new Map(voice.teams.map((team) => [team.team, team.expected_points]));
  // The same below-floor clubs appear here with a projected-points number.
  const thinTeams = new Map(voice.teams.map((team) => [team.team, team]));
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
                <th scope="row">
                  {row.team}
                  {(() => {
                    const team = thinTeams.get(row.team);
                    return team ? <ThinHistoryChip team={team} /> : null;
                  })()}
                </th>
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

export function SeasonOutlookBody({
  outlook,
  canonical,
}: {
  outlook: Outlook;
  canonical?: Outlook;
}) {
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
  const voiceSource = canonical ?? outlook;
  const selected = voiceSource.voices.find((voice) => voice.voice_id === voiceId)
    ?? voiceSource.voices[0];
  return (
    <>
      <div className="outlook-voices" role="group" aria-label="Model voice">
        {voiceSource.voices.map((voice) => (
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
      {canonical && outlook.scenario
        ? <ProbabilityComparison canonical={canonical} conditional={outlook} voiceId={selected.voice_id} />
        : <ProbabilityTable voice={selected} />}
      <RunIn outlook={canonical ?? outlook} />
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

export function ScenarioBuilder({
  outlook,
  activeScenario,
  onResult,
  onReset,
}: {
  outlook: Outlook;
  activeScenario: Outlook | null;
  onResult: (result: Outlook) => void;
  onReset: () => void;
}) {
  const [drafts, setDrafts] = useState<SeasonScenarioDraft[]>(() => [{
    id: 1,
    fixtureId: outlook.remaining_fixtures[0]?.match_id ?? "",
    homeScore: 1,
    awayScore: 0,
  }]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resultLimit = Math.min(MAX_SCENARIO_RESULTS, outlook.remaining_fixtures.length);
  let requestValid = true;
  try {
    scenarioRequest(outlook.remaining_fixtures, drafts);
  } catch {
    requestValid = false;
  }

  function updateDraft(id: number, patch: Partial<SeasonScenarioDraft>) {
    if (busy) return;
    setDrafts((current) => current.map((draft) => (
      draft.id === id ? { ...draft, ...patch, id } : draft
    )));
  }

  function addDraft() {
    if (busy) return;
    setDrafts((current) => {
      if (current.length >= resultLimit) return current;
      const selected = new Set(current.map((draft) => draft.fixtureId));
      const fixture = outlook.remaining_fixtures.find((item) => !selected.has(item.match_id));
      if (!fixture) return current;
      const nextId = current.reduce((largest, draft) => Math.max(largest, draft.id), 0) + 1;
      return [...current, {
        id: nextId,
        fixtureId: fixture.match_id,
        homeScore: 1,
        awayScore: 0,
      }];
    });
  }

  async function run() {
    if (!requestValid) return;
    const forcedResults = scenarioRequest(outlook.remaining_fixtures, drafts);
    setBusy(true);
    setError(null);
    try {
      const result = await fetchSeasonScenario(
        outlook.competition_id,
        forcedResults,
        {
          asOfUtc: outlook.as_of_utc,
          season: outlook.season,
          fixtures: outlook.remaining_fixtures,
          indexSha256: outlook.provenance.index_sha256,
        },
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
      <summary>Compose a conditional run</summary>
      <div className="stack" style={{ ["--gap" as string]: ".7rem" }}>
        <p className="small dim">
          Choose 1 to {resultLimit} future results and apply them together. Hypothetical only:
          nothing is saved, sealed, or used as model input.
        </p>
        <ol className="season-scenario__results">
          {drafts.map((draft, index) => {
            const fixture = outlook.remaining_fixtures.find(
              (item) => item.match_id === draft.fixtureId,
            );
            const selectedElsewhere = new Set(
              drafts
                .filter((item) => item.id !== draft.id)
                .map((item) => item.fixtureId),
            );
            return (
              <li key={draft.id}>
                <fieldset className="season-scenario__result" disabled={busy}>
                  <legend>Result {index + 1}</legend>
                  <label className="field season-scenario__fixture">
                    Fixture
                    <select
                      className="select"
                      aria-label={`Fixture ${index + 1}`}
                      value={draft.fixtureId}
                      onChange={(event) => updateDraft(draft.id, { fixtureId: event.target.value })}
                    >
                      {outlook.remaining_fixtures
                        .filter((item) => !selectedElsewhere.has(item.match_id))
                        .map((item) => (
                          <option key={item.match_id} value={item.match_id}>
                            {item.home_team} vs {item.away_team}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label className="field">
                    {fixture?.home_team ?? "Home"} score
                    <input
                      type="number"
                      min="0"
                      max="20"
                      step="1"
                      value={draft.homeScore}
                      onChange={(event) => updateDraft(draft.id, {
                        homeScore: Number(event.target.value),
                      })}
                    />
                  </label>
                  <label className="field">
                    {fixture?.away_team ?? "Away"} score
                    <input
                      type="number"
                      min="0"
                      max="20"
                      step="1"
                      value={draft.awayScore}
                      onChange={(event) => updateDraft(draft.id, {
                        awayScore: Number(event.target.value),
                      })}
                    />
                  </label>
                  {drafts.length > 1 && (
                    <button
                      type="button"
                      className="btn season-scenario__remove"
                      aria-label={`Remove result ${index + 1}`}
                      onClick={() => setDrafts((current) => (
                        current.filter((item) => item.id !== draft.id)
                      ))}
                    >
                      Remove
                    </button>
                  )}
                </fieldset>
              </li>
            );
          })}
        </ol>
        <div className="cluster season-scenario__add">
          <button
            type="button"
            className="btn"
            disabled={busy || drafts.length >= resultLimit}
            onClick={addDraft}
          >
            Add another result
          </button>
          <span className="small dim" aria-live="polite">
            {drafts.length} of {resultLimit} results
          </span>
        </div>
        <div className="cluster">
          <button type="button" className="btn btn--primary" disabled={busy || !requestValid} onClick={() => void run()}>
            {busy ? "Running…" : `Run ${drafts.length}-result scenario`}
          </button>
          {activeScenario && (
            <button type="button" className="btn" disabled={busy} onClick={onReset}>
              Reset to verified outlook
            </button>
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
                <div className="callout__title">
                  {displayed.scenario.forced_results.length} conditional{" "}
                  {displayed.scenario.forced_results.length === 1 ? "result" : "results"} applied
                </div>
                <p>
                  Verified and conditional engine values are shown together below. This comparison
                  exists only in this view; it is not a forecast or a saved result.
                </p>
                <ul className="season-scenario__applied" aria-label="Applied conditional results">
                  {displayed.scenario.forced_results.map((result) => (
                    <li key={result.match_id} className="chip chip--neutral">
                      {result.home_team} {result.home_score}–{result.away_score} {result.away_team}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          <SeasonOutlookBody
            outlook={displayed ?? state.data}
            canonical={scenario ? state.data : undefined}
          />
          {state.data.status === "available" && (
            <ScenarioBuilder
              outlook={state.data}
              activeScenario={scenario}
              onResult={setScenario}
              onReset={() => setScenario(null)}
            />
          )}
        </>
      )}
    </section>
  );
}
