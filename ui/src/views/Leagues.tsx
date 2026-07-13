/**
 * Leagues — a browse hub over the five bundled club leagues + internationals.
 *
 * MVP scope: honest browsing (recent results + any upcoming) per competition,
 * from the local index. Standings and a season Outlook are deliberately NOT here
 * yet — they require a fixtures feed and a simulator (later phases), and the app
 * must never imply a projection it can't compute.
 */
import { fetchRecentMatches } from "../lib/api";
import { LEAGUES } from "../lib/leagues";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton, EmptyState, ErrorState } from "../components/states";
import { ChevronRight } from "../components/icons";
import { Rail } from "./Matchday";

export { LEAGUES } from "../lib/leagues";

export function LeaguesHub() {
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Leagues</h1>
        <p className="measure dim" style={{ margin: 0 }}>
          Browse each competition’s recent matches and open any one for the model council. Standings
          and season projections aren’t here yet — Golavo won’t show a table it can’t honestly
          compute.
        </p>
      </header>
      <div className="league-grid">
        {LEAGUES.map((l) => (
          <a key={l.slug} className="league-card" href={`#/league/${l.slug}`}>
            <div className="league-card__name">{l.name}</div>
            <div className="league-card__note small muted">{l.note}</div>
            <ChevronRight size={16} />
          </a>
        ))}
      </div>
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

  if (!league)
    return (
      <EmptyState title="League not found">
        No league matches this address. <a href="#/leagues">All leagues ›</a>
      </EmptyState>
    );

  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/leagues">Leagues</a>
        <ChevronRight size={14} />
        <span aria-current="page">{league.name}</span>
      </nav>
      <header className="stack" style={{ ["--gap" as string]: ".3rem" }}>
        <h1>{league.name}</h1>
        <p className="small dim" style={{ margin: 0 }}>{league.note}</p>
      </header>
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
