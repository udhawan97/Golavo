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
import { useRef, useState } from "react";
import type {
  MatchDetailResponse,
  MatchForecastLink,
  MatchNotebookResponse,
  MatchRow,
  ModelFamily,
  SealEligibility,
} from "../lib/contract";
import { FAMILY_LABELS } from "../lib/contract";
import { fetchMatch, fetchMatchAnalysis, fetchMatchNotebook, sealMatch, SealApiError } from "../lib/api";
import { utc } from "../lib/format";
import type { AsyncState } from "../lib/hooks";
import { useAsync, useForecastMode } from "../lib/hooks";
import { ChevronRight, InfoIcon, SealIcon, ShieldCheckIcon } from "../components/icons";
import { HorizonChip, StatusChip, TrustStrip } from "../components/primitives";
import { AiDeepRead } from "../components/ai/AiDeepRead";
import { MatchHeader } from "../components/MatchHeader";
import { ModelCouncil } from "../components/ModelCouncil";
import { FormStripsRow } from "../components/FormStrip";
import { TeamStyleProfile } from "../components/TeamStyleProfile";
import { ScoreOutlook } from "../components/ScoreOutlook";
import { NotebookFacts } from "../components/CommentatorsNotebook";
import { InsightCards } from "../components/InsightCards";
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
  const [mode] = useForecastMode();

  // Single fetch owner: the council, form strips, style profile, and score
  // outlook all read this one leak-safe analysis (coalesced + cached in api.ts).
  const [retryTick, setRetryTick] = useState(0);
  const analysisState = useAsync(() => fetchMatchAnalysis(id), [id, retryTick]);
  const analysis =
    analysisState.status === "ready" && analysisState.data.available
      ? analysisState.data.analysis
      : null;

  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <Breadcrumb label={`${match.home_team} v ${match.away_team}`} />

      <MatchHeader
        home={match.home_team}
        away={match.away_team}
        competition={match.competition}
        kickoffUtc={match.kickoff_utc}
        venue={venue}
        chips={
          <>
            <StatusPill match={match} future={future} />
            {match.neutral && <span className="chip chip--neutral">Neutral venue</span>}
            {hasForecast && <span className="chip chip--sealed">Sealed forecast</span>}
          </>
        }
      />

      {analysis && <FormStripsRow analysis={analysis} />}

      <ModelCouncil
        state={analysisState}
        home={match.home_team}
        away={match.away_team}
        onRetry={() => setRetryTick((t) => t + 1)}
      />

      {analysis && <TeamStyleProfile analysis={analysis} expert={mode === "expert"} />}
      {analysis && <ScoreOutlook analysis={analysis} home={match.home_team} away={match.away_team} />}

      {hasForecast ? (
        <ForecastLinks forecasts={match.forecasts} linkedBy={linked_by} />
      ) : match.is_complete ? (
        <PlayedNoForecast match={match} />
      ) : (
        <SealAction detail={detail} />
      )}

      <InsightCards source={{ kind: "match", matchId: id }} />

      <MatchNotebookBlock matchId={id} />

      <AiDeepRead source={{ kind: "match", matchId: id }} />
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
          The sealed numbers live on the forecast page — this card only links to them. Nothing here
          restates or recomputes a probability.
        </p>
      </div>
    </section>
  );
}

/** (b) Played, no seal — the engine-recorded score as the hero, and an honest,
 *  always-visible refusal to retro-forecast (detail behind ⓘ). */
function PlayedNoForecast({ match }: { match: MatchRow }) {
  return (
    <section className="panel" aria-labelledby="md-final">
      <div className="panel__head">
        <h2 id="md-final">Final score</h2>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: "1rem" }}>
        <div className="score-hero">
          <span className="score-hero__team">{match.home_team}</span>
          <span className="score-hero__score num">
            {match.home_score}<span className="score-hero__dash">–</span>{match.away_score}
          </span>
          <span className="score-hero__team">{match.away_team}</span>
        </div>
        <TrustStrip
          items={[
            {
              icon: <ShieldCheckIcon />,
              label: "No retro-forecast",
              tipLabel: "Why there is no forecast here",
              tip: "Golavo never retro-forecasts a played match — a forecast is only honest if it was sealed before kickoff. This result is recorded from the vendored data, not scored against a forecast that never existed.",
            },
          ]}
        />
        <p className="small dim measure" style={{ margin: 0 }}>
          The model council above shows a <em>replay</em> — what each method would have said with
          pre-kickoff data. To see how the models perform on fixtures that <em>were</em> sealed
          before kickoff, open the <a href="#/lab/backtests">backtests ›</a>
        </p>
      </div>
    </section>
  );
}

/** (c) Upcoming, no seal — the in-app forecast action, driven by the server's
 *  typed eligibility verdict. An eligible fixture gets a real Generate button;
 *  everything else gets an honest, specific reason (never implying a club league
 *  is forecastable, or that a passed window can still be sealed). */
function SealAction({ detail }: { detail: MatchDetailResponse }) {
  const { match } = detail;
  const eligibility = detail.seal_eligibility;
  const [state, setState] = useState<{ status: "idle" | "sealing" | "error"; error?: SealApiError }>(
    { status: "idle" },
  );
  const inFlight = useRef(false);

  // An older backend that doesn't report eligibility: keep an honest neutral note.
  if (!eligibility) return <SealUnknown match={match} />;
  if (!eligibility.eligible) return <SealIneligible eligibility={eligibility} />;

  const onSeal = async () => {
    if (inFlight.current) return; // guard a double-click (primary + retry both call this)
    inFlight.current = true;
    setState({ status: "sealing" });
    try {
      const result = await sealMatch(match.match_id, eligibility.family);
      // Hand off to the single renderer of sealed numbers.
      window.location.hash = `#/forecast/${encodeURIComponent(result.artifact_id)}`;
    } catch (err) {
      setState({
        status: "error",
        error:
          err instanceof SealApiError ? err : new SealApiError(String(err), 0, "seal_rejected"),
      });
    } finally {
      inFlight.current = false;
    }
  };

  // Sealing is a small side feature now — a compact prompt, not the showcase.
  // The analytics above are the point; this is the optional "put it on the record".
  return (
    <div className="callout callout--info seal-compact" aria-labelledby="md-seal">
      <SealIcon size={18} />
      <div className="stack" style={{ ["--gap" as string]: ".6rem" }}>
        <div id="md-seal">
          <b>Put this on the record?</b> Sealing freezes the council above before kickoff — the only
          thing that counts toward your track record. <a href="#/guide/sealing">What is sealing? ›</a>
        </div>
        <div className="seal-compact__actions">
          <button
            type="button"
            className="btn btn--primary"
            onClick={onSeal}
            disabled={state.status === "sealing"}
            aria-busy={state.status === "sealing"}
          >
            {state.status === "sealing" ? "Sealing…" : "Seal before kickoff"}
          </button>
          <span className="small muted">
            {FAMILY_LABELS[eligibility.family as ModelFamily] ?? eligibility.family} · deterministic · offline
          </span>
        </div>
        {state.status === "error" && state.error && (
          <div className="callout callout--void" role="alert">
            <InfoIcon size={18} />
            <div>
              <div className="callout__title">Couldn’t seal this forecast</div>
              {state.error.message}
              {state.error.reasonCode !== "preview_only" && (
                <>
                  {" "}
                  <button
                    type="button"
                    className="btn btn--ghost"
                    style={{ marginTop: ".5rem" }}
                    onClick={onSeal}
                  >
                    Try again
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** An ineligible fixture, explained with copy specific to the typed reason. */
function SealIneligible({ eligibility }: { eligibility: SealEligibility }) {
  const copy: Record<string, string> = {
    kickoff_passed:
      "The seal window has closed. A forecast is only honest if it was sealed before kickoff — for this date-only fixture, before its 00:00 UTC day proxy, which has already passed.",
    unsupported_competition:
      "Forward sealing currently covers men’s senior international fixtures. Club leagues are bundled for historical backtesting, not forward forecasts.",
    pack_unavailable:
      "The pinned data pack for this fixture isn’t available in this build yet, so a forecast can’t be sealed here.",
  };
  const message = copy[eligibility.reason_code] ?? eligibility.detail;
  const tone = eligibility.reason_code === "kickoff_passed" ? "callout--void" : "callout--info";
  return (
    <div className={`callout ${tone}`}>
      <InfoIcon size={18} />
      <div>
        <div className="callout__title">No forecast for this fixture</div>
        {message} <a href="#/guide/sealing">What is sealing? ›</a>
      </div>
    </div>
  );
}

/** Fallback for a backend that predates the eligibility verdict. */
function SealUnknown({ match }: { match: MatchRow }) {
  return (
    <div className="callout callout--info">
      <InfoIcon size={18} />
      <div>
        <div className="callout__title">No forecast sealed for this fixture yet</div>
        This build doesn’t report in-app sealing for this fixture.
        {match.source_kind === "club" && (
          <> Forward sealing currently covers internationals; club leagues are backtesting data.</>
        )}{" "}
        <a href="#/guide/sealing">What is sealing? ›</a>
      </div>
    </div>
  );
}

/** The Commentator's Notebook — always shown for a found match. Fed by the
 *  per-match notebook endpoint and rendered through the shared NotebookFacts
 *  renderer. Subordinate to any seal: it is descriptive history, never a forecast. */
function MatchNotebookBlock({ matchId }: { matchId: string }) {
  const [retryTick, setRetryTick] = useState(0);
  const state = useAsync(() => fetchMatchNotebook(matchId), [matchId, retryTick]);
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
        <NotebookBlockBody state={state} onRetry={() => setRetryTick((t) => t + 1)} />
      </div>
    </section>
  );
}

function NotebookBlockBody({
  state,
  onRetry,
}: {
  state: AsyncState<MatchNotebookResponse>;
  onRetry: () => void;
}) {
  if (state.status === "loading") return <BlockSkeleton lines={4} />;
  if (state.status === "error") {
    const warming = /HTTP 503/.test(state.error.message);
    return (
      <div className="stack" style={{ ["--gap" as string]: ".6rem" }}>
        <p className="small dim" style={{ margin: 0 }}>
          {warming
            ? "Notebook engine warming up — the facts aren’t ready yet."
            : "Couldn’t load the notebook for this fixture right now. The rest of the page is unaffected."}
        </p>
        <div>
          <button type="button" className="btn btn--ghost" onClick={onRetry}>
            Try again
          </button>
        </div>
      </div>
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
      <a href="#/">Matchday</a>
      {label && (
        <>
          <ChevronRight size={14} />
          <span aria-current="page">{label}</span>
        </>
      )}
    </nav>
  );
}
