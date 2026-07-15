import { useState } from "react";
import type { TournamentOutlook as Outlook, TournamentOutlookVoice } from "../lib/contract";
import { fetchWorldCupOutlook } from "../lib/api";
import { pct, utcDate } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton } from "./states";

const VOICE_COPY: Record<TournamentOutlookVoice["voice_id"], string> = {
  elo_ordlogit: "Ratings",
  dixon_coles: "Goals",
  "equal-chance-baseline": "Baseline",
};

function ProbabilityBar({ value }: { value: number }) {
  return (
    <span className="outlook-probability" aria-hidden>
      <span style={{ width: `${Math.max(1, value * 100)}%` }} />
    </span>
  );
}

export function TournamentOutlookBody({ outlook }: { outlook: Outlook }) {
  const [voiceId, setVoiceId] = useState<TournamentOutlookVoice["voice_id"]>("elo_ordlogit");
  if (outlook.status !== "available") {
    return (
      <div className="callout callout--info" role="status">
        <div>
          <div className="callout__title">Tournament outlook unavailable</div>
          <p>{outlook.reason}</p>
        </div>
      </div>
    );
  }
  const selected = outlook.voices.find((voice) => voice.voice_id === voiceId) ?? outlook.voices[0];
  return (
    <>
      {outlook.snapshot_status === "result_refresh_needed" && (
        <div className="callout callout--warning" role="status">
          <div>
            <div className="callout__title">Result refresh needed</div>
            <p>{outlook.snapshot_note}</p>
          </div>
        </div>
      )}
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
        <table className="grid outlook-table">
          <thead>
            <tr>
              <th scope="col">Team</th>
              <th scope="col">Reach final</th>
              <th scope="col">Champion</th>
              <th scope="col">Finish third</th>
            </tr>
          </thead>
          <tbody>
            {selected.teams.map((team) => (
              <tr key={team.team}>
                <th scope="row">{team.team}</th>
                <td className="num">{pct(team.reach_final)}</td>
                <td className="num outlook-table__champion">
                  <span>{pct(team.champion)}</span>
                  <ProbabilityBar value={team.champion} />
                </td>
                <td className="num">{pct(team.third)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="outlook-method">
        <summary>How this bracket is calculated</summary>
        <p>
          Exact enumeration — no random runs and no blended consensus. Each tab is a separate
          Golavo voice. A 90-minute draw follows the disclosed knockout rule; this outlook is never
          written to the forecast ledger.
        </p>
        <p className="small dim">
          Rule {outlook.outlook_rule} · {selected.draw_resolution} · model data through {outlook.data_through_utc ? utcDate(outlook.data_through_utc) : "unknown"}.
        </p>
      </details>
    </>
  );
}

export function TournamentOutlook() {
  const state = useAsync(fetchWorldCupOutlook, []);
  return (
    <section className="tournament-outlook stack" style={{ ["--gap" as string]: ".85rem" }} aria-labelledby="outlook-title">
      <header className="hgroup">
        <div>
          <span className="upper">World Cup 2026</span>
          <h2 id="outlook-title">Tournament outlook</h2>
          <p className="small dim">Separate model voices across the remaining four-team bracket.</p>
        </div>
        <span className="chip chip--neutral">Simulation · not a seal</span>
      </header>
      {state.status === "loading" ? <BlockSkeleton lines={5} /> : state.status === "error" ? (
        <div className="callout callout--info" role="status">
          <div><div className="callout__title">Tournament outlook unavailable</div><p>The local model fit could not be read.</p></div>
        </div>
      ) : (
        <TournamentOutlookBody outlook={state.data} />
      )}
    </section>
  );
}
