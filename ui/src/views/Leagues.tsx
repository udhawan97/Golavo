/**
 * Leagues — a browse hub over the five bundled club leagues + internationals.
 *
 * MVP scope: honest browsing (recent results + any upcoming) per competition,
 * from the local index. Standings and a season Outlook are deliberately NOT here
 * yet — they require a fixtures feed and a simulator (later phases), and the app
 * must never imply a projection it can't compute.
 */
import type { SourceKind } from "../lib/contract";
import { fetchRecentMatches } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton, EmptyState, ErrorState } from "../components/states";
import { ChevronRight } from "../components/icons";
import { Rail } from "./GamesHome";

interface League {
  slug: string;
  name: string;
  competition?: string;
  sourceKind?: SourceKind;
  note: string;
}

export const LEAGUES: League[] = [
  { slug: "internationals", name: "Internationals", sourceKind: "international",
    note: "Men’s senior internationals — the one surface that refreshes on demand." },
  { slug: "premier-league", name: "Premier League", competition: "English Premier League",
    note: "England · bundled 2010–11 onward (historical)." },
  { slug: "la-liga", name: "La Liga", competition: "La Liga",
    note: "Spain · bundled 2012–13 onward (historical)." },
  { slug: "bundesliga", name: "Bundesliga", competition: "Bundesliga",
    note: "Germany · bundled 2010–11 onward (historical)." },
  { slug: "serie-a", name: "Serie A", competition: "Serie A",
    note: "Italy · bundled 2013–14 onward (historical)." },
  { slug: "ligue-1", name: "Ligue 1", competition: "Ligue 1",
    note: "France · bundled 2014–15 onward (historical)." },
];

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
