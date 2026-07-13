/**
 * Matchday — the default landing surface.
 *
 * Analytics-first, results-first: it opens on real matches from the local index
 * (finished results in the last week by default), grouped by competition with the
 * big-five leagues and major internationals surfaced first. Every card links to
 * its Match Cockpit — the analytics showcase. Sealing is a small side feature now,
 * explained in its own guide, not the front door.
 *
 * The default "last week" is anchored to the freshest result in the snapshot, so a
 * stale bundle degrades to "the most recent week of results" rather than an empty
 * page; the range and any staleness are labelled honestly.
 */
import { useState } from "react";
import type { MatchRow, MatchWindow, MatchesWindowResponse } from "../lib/contract";
import { fetchMatchesWindow } from "../lib/api";
import { groupMatchesByCompetition, leagueSlugFor, LEAGUES } from "../lib/leagues";
import { utcDate } from "../lib/format";
import { useAsync } from "../lib/hooks";
import type { AsyncState } from "../lib/hooks";
import { BlockSkeleton, EmptyState, ErrorState } from "../components/states";
import { ChevronRight, SearchIcon } from "../components/icons";
import { useWarmupStatus } from "../lib/warmup";
import { WarmupHero } from "../components/EngineWarmup";

const WELCOME_KEY = "golavo-welcome-dismissed";

/** A one-time, dismissible orientation card — what Golavo is for, in three lines.
 *  Sealing is mentioned as an option (with a link to its guide), not the headline. */
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
        <SearchIcon size={22} />
      </div>
      <div className="welcome__body">
        <p className="welcome__title">New here? What Golavo does</p>
        <ul className="welcome__list">
          <li><b>Open any match</b> — past or upcoming — for a deep analytics read: a five-model council, team style, and source-backed facts.</li>
          <li><b>See where the methods agree</b>, and where they don’t — no averaging into false certainty.</li>
          <li>Want to put a prediction on the record? <a href="#/guide/sealing">Sealing, explained ›</a></li>
        </ul>
      </div>
      <button type="button" className="welcome__dismiss" onClick={dismiss}>
        Got it
      </button>
    </aside>
  );
}

const WINDOWS: { value: MatchWindow; label: string }[] = [
  { value: "week", label: "Last week" },
  { value: "month", label: "Last month" },
  { value: "upcoming", label: "Upcoming" },
];

export function MatchdayHome() {
  const warmup = useWarmupStatus();
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.5rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Matchday</h1>
        <p className="measure dim" style={{ margin: 0 }}>
          Every game gets the full treatment — a five-model council, how each side attacks and
          defends, and the facts worth knowing. Open any match for its deep analytics read. No
          account, no network, no invented certainty.
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

      {/* Hold the window query until the index is warm — firing it early blocks
          ~25s inside pandas' import lock. The store flips to ready the moment the
          index is up, and MatchdayFeed then fetches instantly. */}
      {warmup.phase === "warming" ? <WarmupHero rows={warmup.rows} /> : <MatchdayFeed />}

      <p className="small dim" style={{ margin: 0 }}>
        Tracking predictions before kickoff? Your sealed forecasts and their scores live in{" "}
        <a href="#/lab/track-record">Model Lab › Track record ›</a> —{" "}
        <a href="#/guide/sealing">how sealing works ›</a>
      </p>
    </div>
  );
}

/** Owns the window state + fetch — mounted only once the index is warm. */
function MatchdayFeed() {
  const [window, setWindow] = useState<MatchWindow>("week");
  const state = useAsync(() => fetchMatchesWindow(window), [window]);
  return (
    <section className="stack" style={{ ["--gap" as string]: ".9rem" }} aria-label="Matchday feed">
      <div className="mv-filter-chips" role="group" aria-label="Time window">
        {WINDOWS.map((w) => (
          <button
            key={w.value}
            type="button"
            className={`mv-filter-chip${window === w.value ? " is-active" : ""}`}
            aria-pressed={window === w.value}
            onClick={() => setWindow(w.value)}
          >
            {w.label}
          </button>
        ))}
      </div>
      <WindowBody window={window} state={state} />
    </section>
  );
}

/** The honest range + staleness line above the results. */
function WindowMeta({ data }: { data: MatchesWindowResponse }) {
  if (data.window === "upcoming") {
    return (
      <p className="small dim" role="status" style={{ margin: 0 }}>
        Scheduled fixtures, soonest first.
      </p>
    );
  }
  if (!data.window_start_utc || !data.window_end_utc) return null;
  const start = utcDate(data.window_start_utc);
  const end = utcDate(data.window_end_utc);
  // Stale if the freshest result is older than yesterday (snapshot behind real time).
  const yesterday = Date.now() - 2 * 86_400_000;
  const stale = data.latest_result_utc && new Date(data.latest_result_utc).getTime() < yesterday;
  return (
    <p className="small dim" role="status" style={{ margin: 0 }}>
      Results {start} – {end}.
      {stale && data.latest_result_utc && (
        <> Freshest result in this snapshot: {utcDate(data.latest_result_utc)}.</>
      )}
    </p>
  );
}

function WindowBody({
  window,
  state,
}: {
  window: MatchWindow;
  state: AsyncState<MatchesWindowResponse>;
}) {
  if (state.status === "loading") return <BlockSkeleton lines={6} />;
  if (state.status === "error") return <ErrorState error={state.error} />;
  const data = state.data;

  if (data.matches.length === 0) {
    if (window === "upcoming") {
      return (
        <EmptyState title="No forward fixtures in this snapshot">
          The bundled snapshot holds no scheduled matches yet. Internationals refresh on demand —
          turn on <a href="#/settings">Keep fixtures fresh</a> in Settings — and club fixtures appear
          once the open feed publishes them. Switch to <b>Last week</b> for recent results.
        </EmptyState>
      );
    }
    return (
      <EmptyState title="No results in this snapshot">
        There are no completed matches in this window. <a href="#/matches">Search all matches ›</a>
      </EmptyState>
    );
  }

  const groups = groupMatchesByCompetition(data.matches);
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.5rem" }}>
      <WindowMeta data={data} />
      {groups.map((g) => (
        <CompetitionSection
          key={`${g.competition}|${g.sourceKind}`}
          competition={g.competition}
          sourceKind={g.sourceKind}
          matches={g.matches}
        />
      ))}
    </div>
  );
}

const SECTION_CAP = 12;

function CompetitionSection({
  competition,
  sourceKind,
  matches,
}: {
  competition: string;
  sourceKind: MatchRow["source_kind"];
  matches: MatchRow[];
}) {
  const [expanded, setExpanded] = useState(false);
  const slug = leagueSlugFor(competition, sourceKind);
  const shown = expanded ? matches : matches.slice(0, SECTION_CAP);
  const overflow = matches.length - shown.length;
  return (
    <section className="stack" style={{ ["--gap" as string]: ".6rem" }} aria-label={competition}>
      <div className="comp-section__head">
        <h2 className="rail__title">{competition}</h2>
        <span className="comp-section__count small muted">{matches.length}</span>
      </div>
      <div className="game-grid">
        {shown.map((m) => (
          <GameCard key={m.match_id} match={m} />
        ))}
      </div>
      {overflow > 0 &&
        (slug ? (
          <a className="comp-section__more small" href={`#/league/${slug}`}>
            All {competition} matches › ({matches.length})
          </a>
        ) : (
          <button
            type="button"
            className="comp-section__more small"
            onClick={() => setExpanded(true)}
          >
            Show all {matches.length} ›
          </button>
        ))}
    </section>
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
      aria-label={`${match.home_team} versus ${match.away_team}, ${match.competition}, ${state}, ${utcDate(match.kickoff_utc)}. Open analytics.`}
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
        <span>{match.is_complete ? "Played" : "Upcoming"} · {utcDate(match.kickoff_utc)}</span>
        <span className="game-card__analyze" aria-hidden>
          Analyze <ChevronRight size={13} />
        </span>
      </div>
    </a>
  );
}
