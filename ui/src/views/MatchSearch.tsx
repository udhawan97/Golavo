/**
 * MatchSearch — search the read-only match directory.
 *
 * Consumes Workstream D's `searchMatches` / `fetchCompetitions`. The query lives
 * in component state, never the URL hash (the hash router can't carry `?q=` and
 * per-keystroke hash writes would scroll-jump). A 503 from the still-warming
 * match index is surfaced as a distinct calm state, not a hard failure. Every
 * badge is a DISPLAY of engine-produced fields — a played result is classified
 * by `is_complete`, never by comparing kickoff to now (kickoff is a midnight-UTC
 * day proxy, so a past kickoff without a recorded score is "not in snapshot",
 * not "played").
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { MatchRow, SourceKind } from "../lib/contract";
import { ApiError, fetchCompetitions, searchMatches } from "../lib/api";
import { utcDate } from "../lib/format";
import { useAsync, useDebouncedValue } from "../lib/hooks";
import { InfoIcon, SearchIcon } from "../components/icons";
import { EmptyState, ErrorState, ListSkeleton, Loading } from "../components/states";
import { useDataGenerationRevision } from "../lib/data-refresh-context";

type StatusFilter = "all" | "played" | "upcoming";
const PAGE = 25;

type Phase = "idle" | "loading" | "ready" | "error" | "warming";

const GROUPS: Array<{ kind: SourceKind; title: string }> = [
  { kind: "international", title: "Internationals" },
  { kind: "club", title: "Club competitions" },
];

// Persist the search across navigation (open a match → Back) via sessionStorage,
// not the URL hash — the hash router can't carry `?q=` and per-keystroke hash
// writes scroll-jump.
const SS_Q = "golavo-search-q";
const SS_COMP = "golavo-search-comp";
const SS_STATUS = "golavo-search-status";

// A starting point so the directory is browseable without typing first.
const POPULAR = [
  "FIFA World Cup",
  "UEFA Champions League",
  "Copa América",
  "UEFA Euro",
  "Brazil",
  "England",
  "Argentina",
];

export function MatchSearch() {
  const [input, setInput] = useState(() => sessionStorage.getItem(SS_Q) ?? "");
  const debounced = useDebouncedValue(input, 250);
  const query = debounced.trim();
  const [competition, setCompetition] = useState(() => sessionStorage.getItem(SS_COMP) ?? "");
  const [status, setStatus] = useState<StatusFilter>(() => {
    const stored = sessionStorage.getItem(SS_STATUS);
    return stored === "played" || stored === "upcoming" ? stored : "all";
  });
  // Autofocus only on a truly fresh visit; a restored search must not yank focus
  // (and scroll) back to the input when you return from a match.
  const autoFocusFresh = useRef(!sessionStorage.getItem(SS_Q));

  const [rows, setRows] = useState<MatchRow[]>([]);
  const [total, setTotal] = useState(0);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<Error | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState(false);
  const [retryTick, setRetryTick] = useState(0);
  const generationRevision = useDataGenerationRevision();

  // Restore the query/filters after a round-trip into a match detail.
  useEffect(() => {
    sessionStorage.setItem(SS_Q, input);
    sessionStorage.setItem(SS_COMP, competition);
    sessionStorage.setItem(SS_STATUS, status);
  }, [input, competition, status]);

  const comps = useAsync(fetchCompetitions, [generationRevision]);

  // Stable options object so the fresh-search effect re-runs only on real
  // filter changes, not on every render.
  const opts = useMemo(
    () => ({ competition: competition || undefined, status: status === "all" ? undefined : status }),
    [competition, status],
  );
  const hasDirectoryFilter = competition !== "" || status !== "all";
  const canSearch = query.length >= 2 || (query.length === 0 && hasDirectoryFilter);

  // Identity of the current search — captured by Load-more so a page that
  // resolves after the filters changed is dropped instead of mis-appended.
  const searchKey = `${query}|${competition}|${status}`;
  const keyRef = useRef(searchKey);
  keyRef.current = searchKey;

  // Fresh search (offset 0, replaces rows) whenever the query or a filter moves.
  useEffect(() => {
    if (!canSearch) {
      setPhase("idle");
      setRows([]);
      setTotal(0);
      setError(null);
      return;
    }
    let alive = true;
    setPhase("loading");
    setLoadMoreError(false);
    searchMatches(query, { ...opts, offset: 0, limit: PAGE }).then(
      (res) => {
        if (!alive) return;
        setRows(res.matches);
        setTotal(res.total);
        setPhase("ready");
      },
      (err) => {
        if (!alive) return;
        if (err instanceof ApiError && err.status === 503) {
          setPhase("warming");
          return;
        }
        setError(err instanceof Error ? err : new Error(String(err)));
        setPhase("error");
      },
    );
    return () => {
      alive = false;
    };
  }, [query, opts, canSearch, retryTick, generationRevision]);

  // Re-run the current search (used by the "Try again" affordances).
  const retry = () => setRetryTick((t) => t + 1);

  const loadMore = () => {
    if (!canSearch || loadingMore) return;
    const key = keyRef.current;
    const offset = rows.length;
    setLoadingMore(true);
    setLoadMoreError(false);
    searchMatches(query, { ...opts, offset, limit: PAGE }).then(
      (res) => {
        setLoadingMore(false);
        if (keyRef.current !== key) return;
        setRows((prev) => [...prev, ...res.matches]);
        setTotal(res.total);
      },
      () => {
        setLoadingMore(false);
        setLoadMoreError(true);
      },
    );
  };

  const competitions = comps.status === "ready" ? comps.data.competitions : [];
  const intlComps = competitions.filter((c) => c.source_kind === "international");
  const clubComps = competitions.filter((c) => c.source_kind === "club");

  return (
    <div className="stack" style={{ ["--gap" as string]: "1.3rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Matches</h1>
        <p className="muted" style={{ maxWidth: "62ch" }}>
          Search the match directory. Every match carries a Commentator’s Notebook; a match is
          worth opening even before any forecast is sealed for it.
        </p>
      </header>


      <div className="ms-searchbox">
        <SearchIcon size={18} className="ms-searchbox__icon" aria-hidden />
        <input
          className="ms-search"
          type="search"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Search teams or competitions…"
          aria-label="Search matches"
          autoFocus={autoFocusFresh.current}
        />
      </div>

      <div className="mv-filters" role="group" aria-label="Filter matches">
        <div className="mv-filter-chips" role="group" aria-label="Filter by status">
          <FilterChip label="All" active={status === "all"} onClick={() => setStatus("all")} />
          <FilterChip label="Played" active={status === "played"} onClick={() => setStatus("played")} />
          <FilterChip label="Upcoming" active={status === "upcoming"} onClick={() => setStatus("upcoming")} />
        </div>
        <label className="field mv-filter-field">
          Competition
          <select className="select" value={competition} onChange={(e) => setCompetition(e.target.value)}>
            <option value="">All competitions</option>
            {intlComps.length > 0 && (
              <optgroup label="Internationals">
                {intlComps.map((c) => (
                  <option key={`i-${c.competition}`} value={c.competition}>
                    {c.competition} ({c.n_matches})
                  </option>
                ))}
              </optgroup>
            )}
            {clubComps.length > 0 && (
              <optgroup label="Club competitions">
                {clubComps.map((c) => (
                  <option key={`c-${c.competition}`} value={c.competition}>
                    {c.competition} ({c.n_matches})
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </label>
      </div>

      {phase === "idle" && query.length === 1 && (
        <EmptyState title="Type one more character">
          Match search starts at two characters. You can also clear the search and browse with a
          status or competition filter.
        </EmptyState>
      )}

      {phase === "idle" && query.length !== 1 && (
        <div className="stack" style={{ ["--gap" as string]: ".9rem" }}>
          <EmptyState title="Search the match directory">
            Search 100,000+ matches — internationals, the big-five leagues, and UEFA club
            competitions. Or jump in:
          </EmptyState>
          <div
            className="ms-popular"
            style={{ display: "flex", flexWrap: "wrap", gap: ".5rem", justifyContent: "center" }}
          >
            {POPULAR.map((q) => (
              <button
                key={q}
                type="button"
                className="btn btn--ghost"
                onClick={() => {
                  autoFocusFresh.current = false;
                  setInput(q);
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {phase === "warming" && (
        <div className="callout callout--info">
          <InfoIcon size={18} />
          <div>
            <div className="callout__title">Match engine warming up</div>
            The match index is still loading (it takes a moment on first use).{" "}
            <button type="button" className="btn btn--ghost" onClick={retry}>
              Try again
            </button>
          </div>
        </div>
      )}

      {phase === "loading" && (
        <>
          <Loading label="Searching matches" />
          <ListSkeleton rows={5} />
        </>
      )}

      {phase === "error" && error && <ErrorState error={error} onRetry={retry} />}

      {phase === "ready" && (
        rows.length === 0 ? (
          <div className="stack ms-filter-empty" style={{ ["--gap" as string]: ".8rem" }}>
            <EmptyState title={filterEmptyTitle(query, competition, status)}>
              {query
                ? "No match in the directory matches that query with the current filters. Try fewer filters or a different spelling."
                : `The current snapshot has no ${filterEmptySubject(competition, status)}. Change the filters to keep browsing.`}
            </EmptyState>
            {hasDirectoryFilter && (
              <div className="ms-empty-actions" aria-label="Change empty search filters">
                {status !== "all" && (
                  <button type="button" className="btn btn--ghost" onClick={() => setStatus("all")}>
                    Show all statuses
                  </button>
                )}
                {competition && (
                  <button type="button" className="btn btn--ghost" onClick={() => setCompetition("")}>
                    All competitions
                  </button>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="stack" style={{ ["--gap" as string]: "1.1rem" }}>
            <p className="ms-count small muted" role="status" aria-live="polite">
              Showing {rows.length} of {total} {resultLabel(status, total)}
            </p>
            {GROUPS.map(({ kind, title }) => {
              const group = rows.filter((r) => r.source_kind === kind);
              if (group.length === 0) return null;
              return (
                <section key={kind} className="ms-group" aria-label={title}>
                  <h2 className="ms-group__head">
                    {title} <span className="dim">· {group.length}</span>
                  </h2>
                  <ul className="ms-list">
                    {group.map((m) => (
                      <li key={m.match_id}>
                        <MatchResultRow match={m} />
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
            {rows.length < total && (
              <div className="ms-loadmore stack" style={{ ["--gap" as string]: ".5rem" }}>
                <button type="button" className="btn" onClick={loadMore} disabled={loadingMore}>
                  {loadingMore ? "Loading…" : `Load more (${total - rows.length} more)`}
                </button>
                {loadMoreError && (
                  <div className="small" role="alert" style={{ color: "var(--orange)" }}>
                    Couldn’t load more matches.{" "}
                    <button type="button" className="btn btn--ghost" onClick={loadMore}>
                      Retry
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      )}
    </div>
  );
}

function filterEmptySubject(competition: string, status: StatusFilter): string {
  const statusLabel = status === "all" ? "matches" : `${status} matches`;
  return competition ? `${statusLabel} in ${competition}` : statusLabel;
}

function filterEmptyTitle(query: string, competition: string, status: StatusFilter): string {
  if (query) return `No matches for “${query}”`;
  const subject = filterEmptySubject(competition, status);
  return `No ${subject}`;
}

function resultLabel(status: StatusFilter, total: number): string {
  const noun = total === 1 ? "match" : "matches";
  return status === "all" ? noun : `${status} ${noun}`;
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      className={`mv-filter-chip${active ? " is-active" : ""}`}
      aria-pressed={active}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

/** One result row. The badge classifies by `is_complete` first (never by
 *  kickoff-vs-now), so a past kickoff with no recorded score reads honestly as
 *  "Result not in snapshot" rather than a fabricated "Played" or "Upcoming". */
function MatchResultRow({ match }: { match: MatchRow }) {
  const hasForecast = match.forecasts.length > 0;
  return (
    <a
      className="ms-row"
      href={`#/match/${encodeURIComponent(match.match_id)}`}
      aria-label={`${match.home_team} versus ${match.away_team}, ${match.competition}, ${utcDate(match.kickoff_utc)}${hasForecast ? ", has a sealed forecast" : ""}`}
    >
      <div className="ms-row__main">
        <span className="ms-row__teams">
          {match.home_team} <span className="dim" style={{ fontWeight: 400 }}>v</span> {match.away_team}
        </span>
        <span className="ms-row__meta">
          <span className="num">{utcDate(match.kickoff_utc)}</span>
          <span className="dim">·</span>
          <span>{match.competition}</span>
        </span>
      </div>
      <div className="ms-row__badges">
        <ResultBadge match={match} />
        {hasForecast && <span className="chip chip--sealed">Sealed forecast</span>}
      </div>
    </a>
  );
}

function ResultBadge({ match }: { match: MatchRow }) {
  if (match.is_complete) {
    return (
      <span className="chip chip--scored">
        Played <span className="num">{match.home_score}–{match.away_score}</span>
      </span>
    );
  }
  const future = new Date(match.kickoff_utc).getTime() > Date.now();
  if (future) return <span className="chip chip--neutral">Upcoming</span>;
  return <span className="chip chip--muted">Result not in snapshot</span>;
}
