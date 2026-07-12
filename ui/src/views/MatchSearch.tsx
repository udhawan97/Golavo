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

type StatusFilter = "all" | "played" | "upcoming";
const PAGE = 25;

type Phase = "idle" | "loading" | "ready" | "error" | "warming";

const GROUPS: Array<{ kind: SourceKind; title: string }> = [
  { kind: "international", title: "Internationals" },
  { kind: "club", title: "Club leagues" },
];

export function MatchSearch() {
  const [input, setInput] = useState("");
  const debounced = useDebouncedValue(input, 250);
  const query = debounced.trim();
  const [competition, setCompetition] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");

  const [rows, setRows] = useState<MatchRow[]>([]);
  const [total, setTotal] = useState(0);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<Error | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const comps = useAsync(fetchCompetitions, []);

  // Stable options object so the fresh-search effect re-runs only on real
  // filter changes, not on every render.
  const opts = useMemo(
    () => ({ competition: competition || undefined, status: status === "all" ? undefined : status }),
    [competition, status],
  );

  // Identity of the current search — captured by Load-more so a page that
  // resolves after the filters changed is dropped instead of mis-appended.
  const searchKey = `${query}|${competition}|${status}`;
  const keyRef = useRef(searchKey);
  keyRef.current = searchKey;

  // Fresh search (offset 0, replaces rows) whenever the query or a filter moves.
  useEffect(() => {
    if (query.length < 2) {
      setPhase("idle");
      setRows([]);
      setTotal(0);
      setError(null);
      return;
    }
    let alive = true;
    setPhase("loading");
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
  }, [query, opts]);

  const loadMore = () => {
    if (query.length < 2 || loadingMore) return;
    const key = keyRef.current;
    const offset = rows.length;
    setLoadingMore(true);
    searchMatches(query, { ...opts, offset, limit: PAGE }).then(
      (res) => {
        setLoadingMore(false);
        if (keyRef.current !== key) return;
        setRows((prev) => [...prev, ...res.matches]);
        setTotal(res.total);
      },
      () => setLoadingMore(false),
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
          autoFocus
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
              <optgroup label="Club leagues">
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

      {phase === "idle" && (
        <EmptyState title="Search the match directory">
          Search 50,000+ matches — internationals and the big-five club leagues.
        </EmptyState>
      )}

      {phase === "warming" && (
        <div className="callout callout--info">
          <InfoIcon size={18} />
          <div>
            <div className="callout__title">Match engine warming up</div>
            The match engine is still warming up — try again in a moment.
          </div>
        </div>
      )}

      {phase === "loading" && (
        <>
          <Loading label="Searching matches" />
          <ListSkeleton rows={5} />
        </>
      )}

      {phase === "error" && error && <ErrorState error={error} />}

      {phase === "ready" && (
        rows.length === 0 ? (
          <EmptyState title={`No matches for “${query}”`}>
            No match in the directory matches that query with the current filters. Try fewer
            filters or a different spelling.
          </EmptyState>
        ) : (
          <div className="stack" style={{ ["--gap" as string]: "1.1rem" }}>
            <p className="ms-count small muted" role="status" aria-live="polite">
              Showing {rows.length} of {total} match{total === 1 ? "" : "es"}
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
              <div className="ms-loadmore">
                <button type="button" className="btn" onClick={loadMore} disabled={loadingMore}>
                  {loadingMore ? "Loading…" : `Load more (${total - rows.length} more)`}
                </button>
              </div>
            )}
          </div>
        )
      )}
    </div>
  );
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
    <a className="ms-row" href={`#/match/${encodeURIComponent(match.match_id)}`}>
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
