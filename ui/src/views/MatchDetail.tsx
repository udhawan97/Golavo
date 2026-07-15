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
import type { ReactNode } from "react";
import type {
  MatchDetailResponse,
  MatchAnalysis,
  MatchForecastLink,
  MatchNotebookResponse,
  MatchRow,
  ModelFamily,
  SealEligibility,
} from "../lib/contract";
import { FAMILY_LABELS } from "../lib/contract";
import { fetchMatch, fetchMatchAnalysis, fetchMatchNotebook, sealMatch, SealApiError } from "../lib/api";
import { pct, utc } from "../lib/format";
import type { AsyncState } from "../lib/hooks";
import { useAsync, useForecastMode } from "../lib/hooks";
import { BookIcon, ChevronRight, DistributionIcon, InfoIcon, QuillIcon, ScaleIcon, SealIcon, ShieldCheckIcon, TrophyIcon } from "../components/icons";
import { HorizonChip, StatusChip, TrustStrip, UncertaintyTag } from "../components/primitives";
import { AiDeepRead } from "../components/ai/AiDeepRead";
import { MatchHeader } from "../components/MatchHeader";
import { ModelCouncil } from "../components/ModelCouncil";
import { ScoreOutlook } from "../components/ScoreOutlook";
import { SecondHalfStory } from "../components/SecondHalfStory";
import { WorldCupPedigree } from "../components/WorldCupPedigree";
import { MatchFormBook, MatchHeadToHead, MatchHistoryRecords, MatchNotesColophon, MatchStyleBook } from "../components/MatchNotes";
import { parseHalfTimeStory, parseWorldCupPedigree } from "../lib/factValues";
import { TourOverlay } from "../components/TourOverlay";
import { COCKPIT_TOUR, useTour } from "../lib/tour";
import { useUpdater } from "../lib/updater-context";
import { BlockSkeleton, EmptyState, ErrorState, Loading } from "../components/states";
import { PickPanel } from "../components/PickPanel";
import { ModeToggle } from "../components/ModeToggle";
import { chapterPullNumber } from "../lib/insights";
import { ProgrammePullNumber } from "../components/ProgrammePullNumber";
import { factKey } from "../components/CommentatorsNotebook";

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
  const [mode, setMode] = useForecastMode();

  // Single fetch owner: the council, form strips, style profile, and score
  // outlook all read this one leak-safe analysis (coalesced + cached in api.ts).
  const [retryTick, setRetryTick] = useState(0);
  const analysisState = useAsync(() => fetchMatchAnalysis(id), [id, retryTick]);
  const analysis =
    analysisState.status === "ready" && analysisState.data.available
      ? analysisState.data.analysis
      : null;
  const [notebookRetryTick, setNotebookRetryTick] = useState(0);
  const notebookState = useAsync(
    () => fetchMatchNotebook(id),
    [id, notebookRetryTick],
  );
  const notebook =
    notebookState.status === "ready" && notebookState.data.available
      ? notebookState.data.notebook
      : null;
  const halfTimeStory =
    match.source_kind === "club"
      ? parseHalfTimeStory(notebook, match.home_team, match.away_team)
      : null;
  const worldCupStory =
    match.source_kind === "international" && match.competition === "FIFA World Cup"
      ? parseWorldCupPedigree(notebook, match.home_team, match.away_team)
      : null;
  const consumedKeys = new Set([
    ...(halfTimeStory?.consumedKeys ?? []),
    ...(worldCupStory?.consumedKeys ?? []),
  ]);

  // The cockpit micro-tour fires the first time a match is opened. It yields to
  // the update-consent card and, via useTour, only starts once its panels exist,
  // so it never spotlights a bare loading skeleton with no anchor.
  const { consentNeeded } = useUpdater();
  const cockpitTour = useTour(COCKPIT_TOUR, !consentNeeded);
  const sealCompanion =
    mode === "expert" ? (
      hasForecast ? (
        <ForecastLinks forecasts={match.forecasts} linkedBy={linked_by} />
      ) : match.is_complete ? (
        <PlayedNoForecast match={match} />
      ) : (
        <SealAction detail={detail} />
      )
    ) : (
      <ExpertSealRow detail={detail} />
    );

  const notesProps = {
    notebook,
    analysis,
    omitKeys: consumedKeys,
    expert: mode === "expert",
  };
  const pullNotebook = notebook
    ? { ...notebook, facts: notebook.facts.filter((fact) => !consumedKeys.has(factKey(fact))) }
    : null;
  const pullContext = { analysis, notebook: pullNotebook };
  return (
    <div className={`match-programme match-programme--${mode} stack`} style={{ ["--gap" as string]: "1.25rem" }}>
      <Breadcrumb label={`${match.home_team} v ${match.away_team}`} />

      <div id="match-teaser">
        <MatchHeader
          home={match.home_team}
          away={match.away_team}
          competition={match.competition}
          kickoffUtc={match.kickoff_utc}
          venue={venue}
          className="programme-teaser"
          eyebrow="Matchday programme"
          chips={
            <>
              <StatusPill match={match} future={future} />
              {match.neutral && <span className="chip chip--neutral">Neutral venue</span>}
              {hasForecast && <span className="chip chip--sealed">Sealed forecast</span>}
            </>
          }
          right={<ModeToggle mode={mode} setMode={setMode} tour="cockpit-mode" />}
          footer={
            <div className="programme-teaser__footer">
              <span className="programme-mode-context" aria-live="polite">
                <b>{mode === "expert" ? "Expert read" : "Casual read"}</b>
                {mode === "expert"
                  ? "Full model values, market detail, sources and audit context."
                  : "The essential story, with technical depth kept out of the way."}
              </span>
              {analysis && <UncertaintyTag level={analysis.uncertainty} />}
            </div>
          }
        />
      </div>

      <ProgrammeContents />

      <ProgrammeChapter
        number="01"
        title="The form book"
        intro={`Recent results set the tone: where ${match.home_team} and ${match.away_team} have played, who they faced, and whether either side arrives with momentum.`}
        icon={<BookIcon />}
        pull={chapterPullNumber("form", pullContext)}
      >
        {analysisState.status === "loading" ? <BlockSkeleton lines={3} /> : <MatchFormBook {...notesProps} />}
      </ProgrammeChapter>

      <ProgrammeChapter
        number="02"
        title="How they play"
        intro={`Past scorelines sketch the contrast between ${match.home_team} and ${match.away_team}: their attacking force, defensive resistance, and the goals the model expects.`}
        icon={<DistributionIcon />}
        pull={chapterPullNumber("style", pullContext)}
        dividerLabel="Fitted from results"
      >
        {analysisState.status === "loading" ? <BlockSkeleton lines={4} /> : <MatchStyleBook {...notesProps} />}
      </ProgrammeChapter>

      <ProgrammeChapter
        number="03"
        title="The history"
        intro={`Previous meetings and tournament records place ${match.home_team} v ${match.away_team} in context, with every claim tied to its source and cutoff.`}
        icon={<TrophyIcon />}
        pull={chapterPullNumber("history", pullContext)}
        dividerLabel="Deterministic · source-backed"
        tour="cockpit-notebook"
      >
        <MatchHeadToHead {...notesProps} />
        <WorldCupPedigree
          competition={match.competition}
          sourceKind={match.source_kind}
          story={worldCupStory}
          headingLevel={3}
        />
        <SecondHalfStory sourceKind={match.source_kind} story={halfTimeStory} headingLevel={3} />
        <MatchNotebookBlock
          state={notebookState}
          onRetry={() => setNotebookRetryTick((tick) => tick + 1)}
          omitKeys={consumedKeys}
          analysis={analysis}
          expert={mode === "expert"}
        />
      </ProgrammeChapter>

      <ProgrammeChapter
        number="04"
        title="The models deliberate"
        intro={`Two deterministic voices examine the same fixture from different angles. Their agreement matters; their disagreement is part of the story.`}
        icon={<ScaleIcon />}
        pull={chapterPullNumber("models", pullContext)}
        dividerLabel="Two voices · no averaging"
        tour="cockpit-council"
      >
        <ModelCouncil
          state={analysisState}
          home={match.home_team}
          away={match.away_team}
          onRetry={() => setRetryTick((t) => t + 1)}
          headingLevel={3}
          expert={mode === "expert"}
        />
        {analysis && <ScoreOutlook analysis={analysis} home={match.home_team} away={match.away_team} headingLevel={3} expert={mode === "expert"} />}
      </ProgrammeChapter>

      <ProgrammeChapter
        number="05"
        title="The verdict"
        intro={`The evidence resolves into one model call for ${match.home_team} v ${match.away_team}. Then the programme hands the decision to you.`}
        icon={<SealIcon />}
        pull={chapterPullNumber("verdict", pullContext)}
        dividerLabel="Model call · your pick"
        id="match-verdict"
      >
        <MatchVerdict analysis={analysis} loading={analysisState.status === "loading"} home={match.home_team} away={match.away_team} />
        <PickPanel
          match={match}
          analysis={analysis}
          companion={sealCompanion}
          headingLevel={3}
          stickyTargetId="match-verdict"
          stickyAfterId="match-teaser"
        />
      </ProgrammeChapter>

      <ProgrammeChapter
        number="06"
        title="The analyst’s column"
        intro={`An optional, evidence-bound reading closes the programme by connecting the strongest signals without changing a single forecast number.`}
        icon={<QuillIcon />}
        dividerLabel="Optional · evidence-bound"
        tour="cockpit-ai"
      >
        <AiDeepRead
          source={{ kind: "match", matchId: id }}
          headingLevel={3}
          context={{
            homeTeam: match.home_team,
            awayTeam: match.away_team,
            uncertainty: analysis?.uncertainty,
            leadingOutcome: analysis?.council.leading_outcome,
          }}
        />
      </ProgrammeChapter>

      <MatchNotesColophon notebook={notebook} />

      <TourOverlay ctrl={cockpitTour} />
    </div>
  );
}

function ProgrammeContents() {
  const chapters = [
    ["01", "The form book", "programme-01"],
    ["02", "How they play", "programme-02"],
    ["03", "The history", "programme-03"],
    ["04", "The models deliberate", "programme-04"],
    ["05", "The verdict", "match-verdict"],
    ["06", "The analyst’s column", "programme-06"],
  ];
  const goToChapter = (id: string) => {
    const target = document.getElementById(id);
    if (!target) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  };
  return (
    <nav className="programme-contents" aria-label="Programme chapters">
      <span className="programme-contents__label upper">In this programme</span>
      <ol>
        {chapters.map(([number, label, id]) => (
          <li key={number}><button type="button" aria-controls={id} onClick={() => goToChapter(id)}><span className="num">{number}</span>{label}</button></li>
        ))}
      </ol>
    </nav>
  );
}

function ProgrammeChapter({
  number,
  title,
  intro,
  icon,
  pull = null,
  dividerLabel,
  children,
  id = `programme-${number}`,
  tour,
}: {
  number: string;
  title: string;
  intro: ReactNode;
  icon: ReactNode;
  pull?: ReturnType<typeof chapterPullNumber>;
  dividerLabel?: string;
  children: ReactNode;
  id?: string;
  tour?: "cockpit-council" | "cockpit-notebook" | "cockpit-ai";
}) {
  const titleId = `${id}-title`;
  return (
    <section id={id} className="programme-chapter" aria-labelledby={titleId} data-tour={tour}>
      {dividerLabel && <div className="programme-chapter__divider" aria-hidden><span>{dividerLabel}</span></div>}
      <header className="programme-chapter__masthead">
        <div className="programme-chapter__folio">
          <span className="programme-chapter__icon" aria-hidden>{icon}</span>
          <span className="upper">Chapter</span>
          <span className="programme-chapter__number num">{number}</span>
        </div>
        <div className="programme-chapter__heading">
          <h2 id={titleId}>{title}</h2>
          <p>{intro}</p>
        </div>
      </header>
      <div className="programme-chapter__rule" aria-hidden />
      <ProgrammePullNumber pull={pull} />
      <div className="programme-chapter__body stack" style={{ ["--gap" as string]: "1rem" }}>{children}</div>
    </section>
  );
}

function MatchVerdict({
  analysis,
  loading,
  home,
  away,
}: {
  analysis: MatchAnalysis | null;
  loading: boolean;
  home: string;
  away: string;
}) {
  if (loading) return <BlockSkeleton lines={3} />;
  if (!analysis || analysis.abstained || !analysis.score_matrix) {
    return (
      <section className="programme-verdict" aria-labelledby="match-verdict-call">
        <span className="upper">Model call</span>
        <h3 id="match-verdict-call">No verdict issued</h3>
        <p>The deterministic models did not clear the history needed to make an honest call.</p>
      </section>
    );
  }
  const leading = analysis.council.leading_outcome;
  const call = leading === "home" ? `${home} to win` : leading === "away" ? `${away} to win` : leading === "draw" ? "Draw" : "Models split";
  const score = analysis.score_matrix.most_likely;
  return (
    <section className="programme-verdict" aria-labelledby="match-verdict-call">
      <div className="programme-verdict__call">
        <span className="upper">Leading outcome</span>
        <h3 id="match-verdict-call">{call}</h3>
      </div>
      <div className="programme-verdict__score">
        <span className="upper">Most likely score</span>
        <strong className="num">{score.home}–{score.away}</strong>
        <span className="small muted">{pct(score.probability)} for this exact score</span>
      </div>
      <div className="programme-verdict__confidence">
        <span className="upper">Confidence</span>
        <UncertaintyTag level={analysis.uncertainty} />
      </div>
    </section>
  );
}

/** Sealing stays available in the everyday cockpit without competing with the
 * user's call. Expert mode expands this row into the full audit treatment. */
function ExpertSealRow({ detail }: { detail: MatchDetailResponse }) {
  const { match } = detail;
  if (match.forecasts.length > 0) {
    const first = match.forecasts[0];
    return (
      <div className="expert-seal-row" aria-label="Expert forecast seal">
        <span className="upper">Expert</span>
        <span>The model’s forecast is on the record.</span>
        <a href={`#/forecast/${encodeURIComponent(first.artifact_id)}`}>View seal ›</a>
        <a href="#/guide/sealing">What is sealing? ›</a>
      </div>
    );
  }
  if (match.is_complete) {
    return (
      <div className="expert-seal-row" aria-label="Expert forecast seal">
        <span className="upper">Expert</span>
        <span>No model forecast was sealed before kickoff.</span>
        <a href="#/guide/sealing">What is sealing? ›</a>
      </div>
    );
  }
  return <SealAction detail={detail} quiet />;
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
    <section className="panel pick-seal-panel" aria-labelledby="md-fc">
      <div className="panel__head">
        <h3 id="md-fc">Sealed forecast{forecasts.length === 1 ? "" : "s"}</h3>
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
                <span className="md-fc-card__main">
                  <strong>View model prediction</strong>
                  <span className="small muted">Sealed {utc(f.sealed_at_utc)}</span>
                </span>
                <ChevronRight size={16} />
              </a>
            </li>
          ))}
        </ul>
        <p className="small dim" style={{ margin: 0 }}>
          Open the seal for the model’s outcome call, top exact score, and probabilities. This match
          page never restates or recomputes them.
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
        <h3 id="md-final">Final score</h3>
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
function SealAction({ detail, quiet = false }: { detail: MatchDetailResponse; quiet?: boolean }) {
  const { match } = detail;
  const eligibility = detail.seal_eligibility;
  const [state, setState] = useState<{ status: "idle" | "sealing" | "error"; error?: SealApiError }>(
    { status: "idle" },
  );
  const inFlight = useRef(false);

  // An older backend that doesn't report eligibility: keep an honest neutral note.
  if (!eligibility) {
    return quiet ? (
      <div className="expert-seal-row"><span className="upper">Expert</span><span>Model sealing is unavailable in this build.</span><a href="#/guide/sealing">What is sealing? ›</a></div>
    ) : <SealUnknown match={match} />;
  }
  if (!eligibility.eligible) {
    return quiet ? (
      <div className="expert-seal-row"><span className="upper">Expert</span><span>The model’s forecast can’t be sealed for this fixture.</span><a href="#/guide/sealing">Why? ›</a></div>
    ) : <SealIneligible eligibility={eligibility} />;
  }

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

  if (quiet) {
    return (
      <div className="expert-seal-row" aria-label="Expert forecast seal">
        <span className="upper">Expert</span>
        <span>Put the model’s forecast on the record.</span>
        <button type="button" className="link-button" onClick={onSeal} disabled={state.status === "sealing"}>
          {state.status === "sealing" ? "Sealing…" : "Seal it ›"}
        </button>
        <a href="#/guide/sealing">What is sealing? ›</a>
        {state.status === "error" && state.error && <span className="pick-ticket__error" role="alert">{state.error.message}</span>}
      </div>
    );
  }

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

/** The source-backed match notes — always shown for a found match. Fed by the
 *  per-match notebook and analysis endpoints. Subordinate to any seal: it is
 *  descriptive history, never a forecast. */
function MatchNotebookBlock({
  state,
  onRetry,
  omitKeys,
  analysis,
  expert,
}: {
  state: AsyncState<MatchNotebookResponse>;
  onRetry: () => void;
  omitKeys: ReadonlySet<string>;
  analysis: MatchAnalysis | null;
  expert: boolean;
}) {
  return <NotebookBlockBody state={state} onRetry={onRetry} omitKeys={omitKeys} analysis={analysis} expert={expert} />;
}

function NotebookBlockBody({
  state,
  onRetry,
  omitKeys,
  analysis,
  expert,
}: {
  state: AsyncState<MatchNotebookResponse>;
  onRetry: () => void;
  omitKeys: ReadonlySet<string>;
  analysis: MatchAnalysis | null;
  expert: boolean;
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
        <MatchHistoryRecords notebook={null} analysis={analysis} omitKeys={omitKeys} expert={expert} />
      </div>
    );
  }

  const resp = state.data;
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
      <MatchHistoryRecords notebook={resp.available ? resp.notebook : null} analysis={analysis} omitKeys={omitKeys} expert={expert} />
    </>
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
