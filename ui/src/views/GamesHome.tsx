/**
 * GamesHome — the default landing surface.
 *
 * Games-first, not artifact-first: it opens on real matches from the local index
 * (recent results always exist, offline), a search entry, and league shortcuts —
 * so a fresh install with an empty ledger is still a full, useful page. The
 * upcoming rail is honestly empty when the snapshot holds no forward fixtures;
 * it never invents a schedule.
 */
import { useState } from "react";
import type { MatchRow, RecentMatchesResponse } from "../lib/contract";
import { fetchRecentMatches } from "../lib/api";
import { utcDate } from "../lib/format";
import { useAsync } from "../lib/hooks";
import type { AsyncState } from "../lib/hooks";
import { BlockSkeleton, ErrorState } from "../components/states";
import { ChevronRight, SealIcon, SearchIcon } from "../components/icons";
import { useWarmupStatus } from "../lib/warmup";
import { WarmupHero } from "../components/EngineWarmup";

const WELCOME_KEY = "golavo-welcome-dismissed";

/** A one-time, dismissible orientation card — the three verbs a first-time
 *  visitor needs (read → seal → track), then it stays out of the way forever. */
function WelcomeCard() {
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(WELCOME_KEY) === "1";
    } catch {
      return false;
    }
  });
  if (dismissed) return null;
  const dismiss = () => {
    setDismissed(true);
    try {
      localStorage.setItem(WELCOME_KEY, "1");
    } catch {
      /* private mode — it just won't persist */
    }
  };
  return (
    <aside className="welcome" aria-label="Getting started">
      <div className="welcome__icon" aria-hidden>
        <SealIcon size={22} />
      </div>
      <div className="welcome__body">
        <p className="welcome__title">New here? Three things Golavo does</p>
        <ul className="welcome__list">
          <li><b>Open any match</b> for the model council’s read — where the methods agree, and where they don’t.</li>
          <li><b>Seal an upcoming international</b> before kickoff to put a prediction on the record.</li>
          <li>Its score after full time lands in <b>Model Lab → Track record</b>.</li>
        </ul>
      </div>
      <button type="button" className="welcome__dismiss" onClick={dismiss}>
        Got it
      </button>
    </aside>
  );
}

const LEAGUES: { slug: string; name: string }[] = [
  { slug: "internationals", name: "Internationals" },
  { slug: "premier-league", name: "Premier League" },
  { slug: "la-liga", name: "La Liga" },
  { slug: "bundesliga", name: "Bundesliga" },
  { slug: "serie-a", name: "Serie A" },
  { slug: "ligue-1", name: "Ligue 1" },
];

export function GamesHome() {
  const warmup = useWarmupStatus();
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

      <WelcomeCard />

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

      {/* Hold the matches query until the index is warm — firing it early blocks
          ~25s inside pandas' import lock, showing bare skeletons. The store flips
          to ready the moment the index is up, and HomeRails then fetches instantly. */}
      {warmup.phase === "warming" ? <WarmupHero rows={warmup.rows} /> : <HomeRails />}

      <p className="small dim" style={{ margin: 0 }}>
        Tracking predictions before kickoff? Your sealed forecasts and their scores live in{" "}
        <a href="#/lab/track-record">Model Lab › Track record ›</a>
      </p>
    </div>
  );
}

/** Owns the recent-matches fetch — mounted only once the index is warm. */
function HomeRails() {
  const state = useAsync(() => fetchRecentMatches(24), []);
  return <Rails state={state} />;
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
  const state = match.is_complete
    ? `played, final score ${match.home_score}–${match.away_score}`
    : "upcoming";
  return (
    <a
      className="game-card"
      href={`#/match/${encodeURIComponent(match.match_id)}`}
      aria-label={`${match.home_team} versus ${match.away_team}, ${match.competition}, ${state}, ${utcDate(match.kickoff_utc)}`}
    >
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
