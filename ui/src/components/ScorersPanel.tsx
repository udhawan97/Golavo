/**
 * ScorersPanel — a competition's leak-safe Golden Boot and penalty-shootout ledger.
 *
 * Internationals-only: the goalscorers and shootouts side tables ship only with
 * the martj42 pack, so the backend returns a typed "unavailable" board for any
 * other competition and this panel renders nothing rather than an empty table.
 */
import type { CompetitionScorers, ScorerRow, ShootoutTeamRow } from "../lib/contract";
import { fetchCompetitionScorers } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton } from "./states";

const TOP_N = 12;

function GoldenBoot({ scorers }: { scorers: ScorerRow[] }) {
  return (
    <div className="table-wrap">
      <table className="grid scorers-table">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Scorer</th>
            <th scope="col">Team</th>
            <th scope="col">Goals</th>
            <th scope="col">Pens</th>
          </tr>
        </thead>
        <tbody>
          {scorers.slice(0, TOP_N).map((row) => (
            <tr key={`${row.scorer}|${row.team}`}>
              <td className="num">{row.rank}</td>
              <th scope="row">{row.scorer}</th>
              <td>{row.team}</td>
              <td className="num">
                <strong>{row.goals}</strong>
              </td>
              <td className="num dim">{row.penalties || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ShootoutLedger({ teams }: { teams: ShootoutTeamRow[] }) {
  const ranked = [...teams].sort((a, b) => b.won + b.lost - (a.won + a.lost)).slice(0, TOP_N);
  return (
    <div className="table-wrap">
      <table className="grid scorers-table">
        <thead>
          <tr>
            <th scope="col">Team</th>
            <th scope="col">Won</th>
            <th scope="col">Lost</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((row) => (
            <tr key={row.team}>
              <th scope="row">{row.team}</th>
              <td className="num">{row.won}</td>
              <td className="num">{row.lost}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScorersBody({ board }: { board: CompetitionScorers }) {
  if (board.scope === "unavailable" || board.matches_counted === 0) {
    return (
      <div className="callout callout--info" role="status">
        <div>
          <div className="callout__title">No scorer data for this competition</div>
          <p>Scorer and shootout records are available for men’s internationals only.</p>
        </div>
      </div>
    );
  }
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.1rem" }}>
      <div>
        <h3 className="upper small dim" style={{ margin: "0 0 .4rem" }}>
          Leading scorers
        </h3>
        <GoldenBoot scorers={board.scorers} />
        <p className="small dim" style={{ margin: ".4rem 0 0" }}>
          All-time in this competition, from {board.matches_counted.toLocaleString()} matches with
          goals. Own goals are never credited to a scorer.
        </p>
      </div>
      {board.teams.length > 0 && (
        <div>
          <h3 className="upper small dim" style={{ margin: "0 0 .4rem" }}>
            Penalty shootouts
          </h3>
          <ShootoutLedger teams={board.teams} />
          <p className="small dim" style={{ margin: ".4rem 0 0" }}>
            {board.shootouts_counted.toLocaleString()} shootouts on record.
          </p>
        </div>
      )}
    </div>
  );
}

export function ScorersPanel({ competitionId }: { competitionId: string }) {
  const state = useAsync(() => fetchCompetitionScorers(competitionId), [competitionId]);
  return (
    <section
      className="scorers-panel stack"
      style={{ ["--gap" as string]: ".85rem" }}
      aria-labelledby="scorers-title"
    >
      <header className="hgroup">
        <div>
          <span className="upper">Records</span>
          <h2 id="scorers-title">Golden Boot &amp; shootouts</h2>
          <p className="small dim">Leak-safe: only matches played to date are counted.</p>
        </div>
        <span className="chip chip--neutral">Internationals · CC0</span>
      </header>
      {state.status === "loading" ? (
        <BlockSkeleton lines={5} />
      ) : state.status === "error" ? (
        <div className="callout callout--info" role="status">
          <div>
            <div className="callout__title">Scorer records unavailable</div>
            <p>The local scorer data could not be read.</p>
          </div>
        </div>
      ) : (
        <ScorersBody board={state.data} />
      )}
    </section>
  );
}
