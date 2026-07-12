/**
 * MatchDetail — one match from the directory (by match_id).
 *
 * This view NEVER renders engine numbers itself: when a seal exists it links to
 * ForecastDetail (the single renderer of sealed probabilities) rather than
 * embedding them. The honest no-forecast states are competition-gated — club
 * leagues are historical backtest data, so we never imply they are forecastable.
 * The Commentator's Notebook block always renders for a found match, which is
 * what makes a searched fixture worth opening even with no forecast attached.
 */
import type { MatchDetailResponse, MatchForecastLink, MatchNotebookResponse, MatchRow } from "../lib/contract";
import { fetchMatch, fetchMatchNotebook } from "../lib/api";
import { relative, utc, utcDate } from "../lib/format";
import type { AsyncState } from "../lib/hooks";
import { useAsync } from "../lib/hooks";
import { ChevronRight, ClockIcon, GlobeIcon, InfoIcon } from "../components/icons";
import { HorizonChip, StatusChip } from "../components/primitives";
import { NotebookFacts } from "../components/CommentatorsNotebook";
import { BlockSkeleton, EmptyState, ErrorState, Loading } from "../components/states";

export function MatchDetail({ id }: { id: string }) {
  const state = useAsync(() => fetchMatch(id), [id]);

  if (state.status === "loading")
    return (
      <>
        <Loading label="Loading match" />
        <Breadcrumb />
        <div style={{ marginTop: "1rem" }}>
          <BlockSkeleton />
        </div>
      </>
    );
  if (state.status === "error")
    return (
      <>
        <Breadcrumb />
        <ErrorState error={state.error} />
      </>
    );

  const detail = state.data;
  if (!detail) {
    return (
      <>
        <Breadcrumb />
        <EmptyState title="Match not found">
          No match in the directory has this id. <a href="#/matches">Search matches ›</a>
        </EmptyState>
      </>
    );
  }
  return <Detail id={id} detail={detail} />;
}

function Detail({ id, detail }: { id: string; detail: MatchDetailResponse }) {
  const { match, linked_by } = detail;
  const hasForecast = match.forecasts.length > 0;
  const future = new Date(match.kickoff_utc).getTime() > Date.now();
  const venue = match.city
    ? `${match.city}${match.country ? `, ${match.country}` : ""}`
    : match.country ?? "—";

  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <Breadcrumb label={`${match.home_team} v ${match.away_team}`} />

      <header className="stack" style={{ ["--gap" as string]: ".55rem" }}>
        <div className="badge-row">
          <StatusPill match={match} future={future} />
          {match.neutral && <span className="chip chip--neutral">Neutral venue</span>}
          {hasForecast && <span className="chip chip--sealed">Sealed forecast</span>}
        </div>
        <h1>
          {match.home_team} <span className="dim" style={{ fontWeight: 400 }}>v</span> {match.away_team}
        </h1>
        <div className="md-card__meta" style={{ marginTop: 0 }}>
          <span>{match.competition}</span>
          <span>
            <ClockIcon /> <span className="num">{utcDate(match.kickoff_utc)}</span>{" "}
            <span className="dim">({relative(match.kickoff_utc)})</span>
          </span>
          <span>
            <GlobeIcon /> {venue}
          </span>
          <span className="dim mono">{match.match_id}</span>
        </div>
      </header>

      {hasForecast ? (
        <ForecastLinks forecasts={match.forecasts} linkedBy={linked_by} />
      ) : match.is_complete ? (
        <PlayedNoForecast match={match} />
      ) : future ? (
        <FutureNoForecast match={match} />
      ) : (
        <PastNoForecast />
      )}

      <MatchNotebookBlock matchId={id} />
    </div>
  );
}

/** Quick top-of-page status, classified by is_complete first (never by kickoff
 *  vs now — kickoff is a day-proxy). */
function StatusPill({ match, future }: { match: MatchRow; future: boolean }) {
  if (match.is_complete)
    return (
      <span className="chip chip--scored">
        Played <span className="num">{match.home_score}–{match.away_score}</span>
      </span>
    );
  if (future) return <span className="chip chip--neutral">Upcoming</span>;
  return <span className="chip chip--muted">Result not in snapshot</span>;
}

/** (a) A seal exists — link out to ForecastDetail; never embed the numbers. */
function ForecastLinks({
  forecasts,
  linkedBy,
}: {
  forecasts: MatchForecastLink[];
  linkedBy: MatchDetailResponse["linked_by"];
}) {
  return (
    <section className="panel" aria-labelledby="md-fc">
      <div className="panel__head">
        <h2 id="md-fc">Sealed forecast{forecasts.length === 1 ? "" : "s"}</h2>
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>
          sealed before kickoff
        </span>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: ".8rem" }}>
        {linkedBy === "fixture" && (
          <p className="small dim" style={{ margin: 0 }}>
            Linked by fixture (date + teams) — the seal names the same fixture without sharing a
            match id.
          </p>
        )}
        <ul className="md-fc-list">
          {forecasts.map((f) => (
            <li key={f.artifact_id}>
              <a className="md-fc-card" href={`#/forecast/${encodeURIComponent(f.artifact_id)}`}>
                <div className="md-fc-card__chips">
                  <StatusChip status={f.status} />
                  <HorizonChip horizon={f.horizon} />
                </div>
                <span className="md-fc-card__when small muted">Sealed {utc(f.sealed_at_utc)}</span>
                <ChevronRight size={16} />
              </a>
            </li>
          ))}
        </ul>
        <p className="small dim" style={{ margin: 0 }}>
          The sealed probabilities live on the forecast page — this directory links to them, it
          never re-renders or restates a number.
        </p>
      </div>
    </section>
  );
}

/** (b) Played, no seal — show the engine-recorded score and refuse to retro-forecast. */
function PlayedNoForecast({ match }: { match: MatchRow }) {
  return (
    <section className="panel" aria-labelledby="md-final">
      <div className="panel__head">
        <h2 id="md-final">Final score</h2>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: ".85rem" }}>
        <div className="md-final">
          <span>{match.home_team}</span>
          <span className="md-final__score num">
            {match.home_score}–{match.away_score}
          </span>
          <span>{match.away_team}</span>
        </div>
        <div className="callout callout--info">
          <InfoIcon size={18} />
          <div>
            Golavo never retro-forecasts a played match — a forecast is only honest if it was
            sealed before kickoff. <a href="#/eval">See how the models perform ›</a>
          </div>
        </div>
      </div>
    </section>
  );
}

/** (c) Upcoming, no seal — honest about where sealing happens today, and gated
 *  by competition so club leagues are never implied to be forecastable. */
function FutureNoForecast({ match }: { match: MatchRow }) {
  return (
    <div className="callout callout--info">
      <InfoIcon size={18} />
      <div>
        <div className="callout__title">No forecast sealed for this fixture yet</div>
        Sealing from inside the app lands in a future release; today, seals are written by the
        engine CLI.
        {match.source_kind === "club" && (
          <>
            {" "}
            Forward sealing currently covers internationals; club leagues are used for historical
            backtesting.
          </>
        )}
      </div>
    </div>
  );
}

/** (c′) Past kickoff, no recorded score, no seal — not "upcoming". */
function PastNoForecast() {
  return (
    <div className="callout callout--void">
      <InfoIcon size={18} />
      <div>
        <div className="callout__title">No result on record</div>
        Result not recorded in the pinned data snapshot.
      </div>
    </div>
  );
}

/** The Commentator's Notebook — always shown for a found match. Fed by the
 *  per-match notebook endpoint and rendered through the shared NotebookFacts
 *  renderer. Subordinate to any seal: it is descriptive history, never a forecast. */
function MatchNotebookBlock({ matchId }: { matchId: string }) {
  const state = useAsync(() => fetchMatchNotebook(matchId), [matchId]);
  return (
    <section className="panel md-nb" aria-labelledby="md-nb-h">
      <div className="panel__head">
        <h2 id="md-nb-h">Commentator’s Notebook</h2>
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>
          deterministic · source-backed
        </span>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: "1rem" }}>
        <p className="small muted" style={{ margin: 0 }}>
          The hidden facts, streaks, and coincidences behind this fixture — computed from the
          vendored packs. Never a forecast, and no AI wrote any of them.
        </p>
        <NotebookBlockBody state={state} />
      </div>
    </section>
  );
}

function NotebookBlockBody({ state }: { state: AsyncState<MatchNotebookResponse> }) {
  if (state.status === "loading") return <BlockSkeleton lines={4} />;
  if (state.status === "error") {
    const warming = /HTTP 503/.test(state.error.message);
    return (
      <p className="small dim" style={{ margin: 0 }}>
        {warming
          ? "Notebook engine warming up — the facts aren’t ready yet. Try again in a moment."
          : "Couldn’t load the notebook for this fixture right now. The rest of the page is unaffected."}
      </p>
    );
  }

  const resp = state.data;
  const facts = resp.notebook?.facts ?? [];
  const caption =
    resp.computed === "precomputed"
      ? "From the sealed forecast’s notebook."
      : resp.computed === "on_demand"
        ? `Computed at the pre-kickoff information horizon (${resp.as_of_horizon ?? "unknown"}); descriptive history, not a forecast.`
        : null;

  return (
    <>
      {caption && (
        <p className="small dim" style={{ margin: 0 }}>
          {caption}
        </p>
      )}
      {facts.length > 0 && <FactLegend />}
      <NotebookFacts notebook={resp.available ? resp.notebook : null} />
    </>
  );
}

/** A one-line key for the fact labels — NotebookFacts groups by label but does
 *  not restate what each label means. */
function FactLegend() {
  return (
    <div className="md-nb-legend small muted" aria-hidden>
      <span className="chip chip--fact-predictive">
        <span className="chip__dot" />
        Predictive
      </span>
      <span className="md-nb-legend__note">labelled base rate, reported only</span>
      <span className="chip chip--fact-context">
        <span className="chip__dot" />
        Context
      </span>
      <span className="md-nb-legend__note">background from results</span>
      <span className="chip chip--fact-coincidence">
        <span className="chip__dot" />
        Coincidence
      </span>
      <span className="md-nb-legend__note">for the pub, not the forecast</span>
    </div>
  );
}

function Breadcrumb({ label }: { label?: string }) {
  return (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      <a href="#/matches">Matches</a>
      {label && (
        <>
          <ChevronRight size={14} />
          <span aria-current="page">{label}</span>
        </>
      )}
    </nav>
  );
}
