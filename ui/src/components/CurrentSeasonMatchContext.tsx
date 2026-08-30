import { fetchSeasonOutlook } from "../lib/api";
import type { MatchRow, SeasonOutlook, SeasonOutlookTeam } from "../lib/contract";
import { pctWhole, utc } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { LEAGUES } from "../lib/leagues";
import { clubImportance, projectionCoverageCaveat, topStake } from "./SeasonOutlook";
import { BlockSkeleton } from "./states";

export function seasonOutlookCompetitionId(match: MatchRow): string | null {
  if (match.source_kind !== "club") return null;
  return LEAGUES.find(
    (league) => league.competition === match.competition
      && league.seasonOutlook
      && league.competitionId,
  )?.competitionId ?? null;
}

export function CurrentSeasonMatchContext({ match }: { match: MatchRow }) {
  const competitionId = seasonOutlookCompetitionId(match);
  if (!competitionId) return null;
  return <SeasonContext match={match} competitionId={competitionId} />;
}

function SeasonContext({ match, competitionId }: { match: MatchRow; competitionId: string }) {
  const state = useAsync(() => fetchSeasonOutlook(competitionId), [competitionId]);
  if (state.status === "loading") return <section className="panel" aria-label="Current season context"><div className="panel__head"><h2>Current season context</h2></div><div className="panel__body"><BlockSkeleton lines={2} /></div></section>;
  if (state.status === "error") return <section className="panel" aria-label="Current season context"><div className="panel__head"><h2>Current season context</h2></div><div className="panel__body"><p className="small dim">The certified local season outlook could not be loaded. Match facts above are unaffected.</p></div></section>;
  const outlook = state.data;
  if (outlook.status !== "available") return <section className="panel" aria-label="Current season context"><div className="panel__head"><h2>Current season context</h2></div><div className="panel__body"><p className="small dim">{outlook.reason ?? "Golavo cannot certify this season outlook from the current local index."}</p></div></section>;
  return <AvailableContext match={match} outlook={outlook} />;
}

function AvailableContext({ match, outlook }: { match: MatchRow; outlook: SeasonOutlook }) {
  const voice = outlook.voices.find((item) => item.role === "voice");
  const fixture = outlook.remaining_fixtures.find((item) => item.match_id === match.match_id);
  const teams = [match.home_team, match.away_team].map((team) => ({
    team,
    standing: outlook.current_table.find((row) => row.team === team),
    projection: voice?.teams.find((row) => row.team === team),
    importance: fixture ? clubImportance(fixture, team) : null,
  }));
  return <section className="panel" aria-labelledby="current-season-context-heading">
    <div className="panel__head"><div><p className="eyebrow">{outlook.season}</p><h2 id="current-season-context-heading">Current season context</h2></div></div>
    <div className="panel__body stack">
      <div className="season-context-grid">{teams.map(({ team, standing, projection, importance }) => <article key={team} className="card card--pad">
        <h3>{team}</h3>
        {standing ? <p><strong>{standing.position}</strong> in table · <strong>{standing.points}</strong> points from {standing.played}</p> : <p className="small dim">Exact team identity is absent from the current local table.</p>}
        {projection && <ProjectionSummary projection={projection} />}
        {importance?.score != null && <p className="small"><strong>{Math.round(importance.score * 100)}pp</strong> maximum season-stakes swing · {topStake(importance)?.replace("_", " ") ?? "outcome"}</p>}
        {fixture && importance === null && <p className="small dim">Season-stakes swing held back because no qualifying conditional-run comparison is available for this club.</p>}
      </article>)}</div>
      {!fixture && !match.is_complete && <p className="small dim">This exact match is not in the certified remaining-fixture list, so fixture-importance context is held back.</p>}
      <p className="small dim">Descriptive simulation{voice ? ` from ${voice.label}` : ""}, never a sealed match forecast, proof of future performance, or advice. As of {utc(outlook.as_of_utc)} · {outlook.iterations.toLocaleString()} runs{outlook.seed === null ? "" : ` · seed ${outlook.seed}`}.</p>
      <p className="small dim">Sources: {outlook.provenance.source_ids.map((source) => <code key={source}>{source} </code>)}· index <code>{outlook.provenance.index_sha256.slice(0, 12)}…</code></p>
    </div>
  </section>;
}

function ProjectionSummary({ projection }: { projection: SeasonOutlookTeam }) {
  const caveat = projectionCoverageCaveat(projection);
  return <><p className="small">Projected {typeof projection.expected_points === "number" ? projection.expected_points.toFixed(1) : "—"} points · title {pctWhole(projection.title)} · top four {pctWhole(projection.top_four)} · relegation {pctWhole(projection.relegation)}</p>{caveat && <p className="small dim">{caveat}</p>}</>;
}
