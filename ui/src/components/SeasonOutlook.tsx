import { useState } from "react";
import type {
  SeasonOutlook as Outlook,
  SeasonOutlookVoice,
  SeasonStandingRow,
} from "../lib/contract";
import { fetchSeasonOutlook } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton } from "./states";

const VOICE_COPY: Record<SeasonOutlookVoice["voice_id"], string> = {
  elo_ordlogit: "Ratings",
  dixon_coles: "Goals",
  "equal-chance-baseline": "Baseline",
};

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

export function SeasonOutlook({ competitionId }: { competitionId: string }) {
  const state = useAsync(() => fetchSeasonOutlook(competitionId), [competitionId]);
  return (
    <section className="season-outlook stack" style={{ ["--gap" as string]: ".85rem" }} aria-labelledby="season-outlook-title">
      <header className="hgroup">
        <div>
          <span className="upper">Domestic league</span>
          <h2 id="season-outlook-title">Season outlook</h2>
          <p className="small dim">Verified standings rules; projections require every fixture.</p>
        </div>
        <span className="chip chip--neutral">Simulation · not a seal</span>
      </header>
      {state.status === "loading" ? <BlockSkeleton lines={4} /> : state.status === "error" ? (
        <div className="callout callout--info" role="status">
          <div><div className="callout__title">Season outlook unavailable</div><p>The local season state could not be read.</p></div>
        </div>
      ) : <SeasonOutlookBody outlook={state.data} />}
    </section>
  );
}
