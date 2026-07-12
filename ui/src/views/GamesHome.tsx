/**
 * GamesHome — the default landing surface.
 *
 * Games-first, not artifact-first: it opens on real matches from the local index
 * (recent results always exist, offline), a search entry, and league shortcuts —
 * so a fresh install with an empty ledger is still a full, useful page. The
 * upcoming rail is honestly empty when the snapshot holds no forward fixtures;
 * it never invents a schedule.
 */
import type { MatchRow, RecentMatchesResponse } from "../lib/contract";
import { fetchRecentMatches } from "../lib/api";
import { utcDate } from "../lib/format";
import { useAsync } from "../lib/hooks";
import type { AsyncState } from "../lib/hooks";
import { BlockSkeleton, ErrorState } from "../components/states";
import { ChevronRight, SearchIcon } from "../components/icons";

const LEAGUES: { slug: string; name: string }[] = [
  { slug: "internationals", name: "Internationals" },
  { slug: "premier-league", name: "Premier League" },
  { slug: "la-liga", name: "La Liga" },
  { slug: "bundesliga", name: "Bundesliga" },
  { slug: "serie-a", name: "Serie A" },
  { slug: "ligue-1", name: "Ligue 1" },
];

export function GamesHome() {
  const state = useAsync(() => fetchRecentMatches(24), []);
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.5rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Games</h1>
        <p className="measure dim" style={{ margin: 0 }}>
          Open any match — past or upcoming — for a local, multi-model read: what each method
          predicts, where they agree or disagree, and the facts worth knowing. No account, no
          network, no invented certainty.
        </p>
      </header>

      <a className="search-cta" href="#/matches">
        <SearchIcon />
        <span>Search 75,000+ matches — internationals and the big-five leagues</span>
        <ChevronRight size={16} />
      </a>

      <nav className="league-chips" aria-label="Browse leagues">
        {LEAGUES.map((l) => (
          <a key={l.slug} className="league-chip" href={`#/league/${l.slug}`}>
            {l.name}
          </a>
        ))}
      </nav>

      <Rails state={state} />

      <p className="small dim" style={{ margin: 0 }}>
        Tracking predictions before kickoff? Your sealed forecasts and their scores live in{" "}
        <a href="#/lab/track-record">Model Lab › Track record ›</a>
      </p>
    </div>
  );
}

function Rails({ state }: { state: AsyncState<RecentMatchesResponse> }) {
  if (state.status === "loading") return <BlockSkeleton lines={6} />;
  if (state.status === "error") return <ErrorState error={state.error} />;
  const { upcoming, recent } = state.data;
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.5rem" }}>
      <Rail title="Upcoming" matches={upcoming} emptyNote="No forward fixtures in this snapshot yet — internationals refresh on demand, and club fixtures appear once the open feed publishes them. Recent results are below." />
      <Rail title="Recent results" matches={recent} emptyNote="No matches in this snapshot." />
    </div>
  );
}

export function Rail({
  title,
  matches,
  emptyNote,
}: {
  title: string;
  matches: MatchRow[];
  emptyNote: string;
}) {
  return (
    <section className="stack" style={{ ["--gap" as string]: ".6rem" }} aria-label={title}>
      <h2 className="rail__title">{title}</h2>
      {matches.length === 0 ? (
        <p className="small dim measure" style={{ margin: 0 }}>
          {emptyNote}
        </p>
      ) : (
        <div className="game-grid">
          {matches.map((m) => (
            <GameCard key={m.match_id} match={m} />
          ))}
        </div>
      )}
    </section>
  );
}

export function GameCard({ match }: { match: MatchRow }) {
  return (
    <a className="game-card" href={`#/match/${encodeURIComponent(match.match_id)}`}>
      <div className="game-card__comp small muted">{match.competition}</div>
      <div className="game-card__teams">
        <span className="game-card__team">{match.home_team}</span>
        <span className="game-card__mid">
          {match.is_complete ? (
            <span className="num game-card__score">
              {match.home_score}–{match.away_score}
            </span>
          ) : (
            <span className="small muted">v</span>
          )}
        </span>
        <span className="game-card__team game-card__team--away">{match.away_team}</span>
      </div>
      <div className="game-card__foot small muted">
        {match.is_complete ? "Played" : "Upcoming"} · {utcDate(match.kickoff_utc)}
      </div>
    </a>
  );
}
