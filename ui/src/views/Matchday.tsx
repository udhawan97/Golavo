/**
 * Matchday — the default landing surface.
 *
 * Analytics-first, results-first: it opens on real matches from the local index
 * (finished results in the last week by default), grouped by competition with the
 * bundled club competitions and major internationals surfaced first. Every card links to
 * its Match Cockpit — the analytics showcase. Sealing is a small side feature now,
 * explained in its own guide, not the front door.
 *
 * The default "last week" is anchored to the freshest result in the snapshot, so a
 * stale bundle degrades to "the most recent week of results" rather than an empty
 * page; the range and any staleness are labelled honestly.
 */
import { useState } from "react";
import type { MatchRow, MatchWindow, MatchesWindowResponse, PickView } from "../lib/contract";
import { fetchMatchesWindow } from "../lib/api";
import { groupMatchesByCompetition, leagueSlugFor, LEAGUES } from "../lib/leagues";
import { utcDate } from "../lib/format";
import { useAsync } from "../lib/hooks";
import type { AsyncState } from "../lib/hooks";
import { BlockSkeleton, EmptyState, ErrorState } from "../components/states";
import { ChevronRight, PinIcon, SearchIcon } from "../components/icons";
import { useWarmupStatus } from "../lib/warmup";
import { WarmupHero } from "../components/EngineWarmup";
import { usePicks } from "../lib/picks";
import { PickChip, pickChipLabel } from "../components/PickChip";
import { nationalFlag, teamMonogram, teamNameDensity } from "../lib/teamIdentity";
import { TournamentOutlook } from "../components/TournamentOutlook";

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
          <li><b>Make your own call</b> before kickoff, then race five transparent model rivals. <a href="#/guide/picks">How picks work ›</a></li>
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
        <span>Search 77,000+ matches — internationals, big-five leagues, and UEFA clubs</span>
        <ChevronRight size={16} />
      </a>

      <nav className="league-chips" aria-label="Browse competitions">
        {LEAGUES.map((l) => (
          <a key={l.slug} className="league-chip" href={`#/league/${l.slug}`}>
            {l.name}
          </a>
        ))}
      </nav>

      <TournamentOutlook />

      {/* Hold the window query until the index is warm — firing it early blocks
          ~25s inside pandas' import lock. The store flips to ready the moment the
          index is up, and MatchdayFeed then fetches instantly. */}
      {warmup.phase === "warming" ? <WarmupHero rows={warmup.rows} /> : <MatchdayFeed />}

      <p className="small dim" style={{ margin: 0 }}>
        Your score calls live in <a href="#/season">My Season ›</a>. Expert model forecasts and
        their audit record live in <a href="#/lab/track-record">Model Lab › Track record ›</a>
      </p>
    </div>
  );
}

/** Owns the window state + fetch — mounted only once the index is warm. */
function MatchdayFeed() {
  const [window, setWindow] = useState<MatchWindow>("week");
  const state = useAsync(() => fetchMatchesWindow(window), [window]);
  const picks = usePicks();
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
      <WindowBody window={window} state={state} picks={picks.byMatch} />
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
  picks,
}: {
  window: MatchWindow;
  state: AsyncState<MatchesWindowResponse>;
  picks: ReadonlyMap<string, PickView>;
}) {
  if (state.status === "loading") return <BlockSkeleton lines={6} />;
  if (state.status === "error") return <ErrorState error={state.error} />;
  const data = state.data;

  if (data.matches.length === 0) {
    if (window === "upcoming") {
      return (
        <EmptyState title="No forward fixtures in this snapshot">
          The bundled snapshot holds no scheduled matches yet. Internationals refresh on demand —
          turn on <a href="#/settings">Keep matches up to date</a> in Settings — and club fixtures appear
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
      {groups.map((g, i) => (
        <CompetitionSection
          key={`${g.competition}|${g.sourceKind}`}
          competition={g.competition}
          sourceKind={g.sourceKind}
          matches={g.matches}
          anchorFirst={i === 0}
          picks={picks}
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
  anchorFirst = false,
  picks,
}: {
  competition: string;
  sourceKind: MatchRow["source_kind"];
  matches: MatchRow[];
  anchorFirst?: boolean;
  picks: ReadonlyMap<string, PickView>;
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
        {shown.map((m, idx) => (
          <GameCard key={m.match_id} match={m} anchor={anchorFirst && idx === 0} pick={picks.get(m.match_id)} />
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

function TeamMark({ team, international }: { team: string; international: boolean }) {
  const flag = international ? nationalFlag(team) : null;
  return (
    <span className={`game-card__mark${flag ? " game-card__mark--flag" : ""}`} aria-hidden="true">
      {flag ?? teamMonogram(team)}
    </span>
  );
}

function MatchLocation({ match }: { match: MatchRow }) {
  const parts = [match.city, match.country].filter(
    (part, index, all): part is string => Boolean(part) && all.indexOf(part) === index,
  );
  if (parts.length === 0) return <span>Location unavailable</span>;
  return <span>{parts.join(" · ")}</span>;
}

export function GameCard({ match, anchor = false, pick }: { match: MatchRow; anchor?: boolean; pick?: PickView }) {
  const state = match.is_complete
    ? `played, final score ${match.home_score}–${match.away_score}`
    : "upcoming";
  const isInternational = match.source_kind === "international";
  const homeDensity = teamNameDensity(match.home_team);
  const awayDensity = teamNameDensity(match.away_team);
  return (
    <a
      className="game-card"
      href={`#/match/${encodeURIComponent(match.match_id)}`}
      data-tour={anchor ? "match-card" : undefined}
      aria-label={`${match.home_team} versus ${match.away_team}, ${match.competition}, ${state}, ${utcDate(match.kickoff_utc)}.${pickChipLabel(match, pick) ? ` ${pickChipLabel(match, pick)}.` : ""} Open analytics.`}
    >
      <div className="game-card__meta">
        <span className="game-card__state">{match.is_complete ? "Final" : "Upcoming"}</span>
        <span className="game-card__date">{utcDate(match.kickoff_utc)}</span>
      </div>
      <div className="game-card__teams">
        <span className="game-card__side game-card__side--home">
          <TeamMark team={match.home_team} international={isInternational} />
          <span className={`game-card__team game-card__team--${homeDensity}`} title={match.home_team}>
            {match.home_team}
          </span>
        </span>
        <span className="game-card__mid">
          {match.is_complete ? (
            <span className="num game-card__score">
              {match.home_score}–{match.away_score}
            </span>
          ) : (
            <span className="small muted">v</span>
          )}
        </span>
        <span className="game-card__side game-card__side--away">
          <TeamMark team={match.away_team} international={isInternational} />
          <span className={`game-card__team game-card__team--away game-card__team--${awayDensity}`} title={match.away_team}>
            {match.away_team}
          </span>
        </span>
      </div>
      <div className="game-card__foot">
        <span className="game-card__location">
          <PinIcon size={13} />
          <MatchLocation match={match} />
        </span>
        <span className="game-card__analyze" aria-hidden>
          Open analysis <ChevronRight size={13} />
        </span>
      </div>
      <PickChip match={match} pick={pick} />
    </a>
  );
}
