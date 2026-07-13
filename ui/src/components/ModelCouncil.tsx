/**
 * ModelCouncil — the Match Cockpit's on-demand multi-model read.
 *
 * Fetches the leak-safe MatchAnalysis for ANY match and renders it honestly:
 *   - an object-type chip (Replay / Preview) that never lets a reconstruction
 *     pass as a forecast that existed at the time;
 *   - a descriptive "at a glance" summary — NOT an averaged consensus;
 *   - the two voices (Elo ratings, Dixon–Coles goal model) side by side, with a
 *     climatology baseline shown as a reference, and the Poisson variants
 *     disclosed (never counted as extra opinions);
 *   - the goal model's exact-score grid, labelled as such.
 *
 * This component renders model numbers, but only ones the deterministic engine
 * produced for this exact fixture at a pre-kickoff cutoff. It never seals.
 */
import type {
  CouncilModel,
  MatchAnalysis,
  MatchAnalysisResponse,
  Outcome,
  Probs,
} from "../lib/contract";
import { pctWhole, utc } from "../lib/format";
import type { AsyncState } from "../lib/hooks";
import { ProbabilityBar, TrustStrip } from "./primitives";
import { BlockSkeleton, Loading } from "./states";
import { InfoIcon, ShieldCheckIcon } from "./icons";

const VOICE_LABEL: Record<string, string> = {
  elo_ordlogit: "Elo · ratings",
  dixon_coles: "Dixon–Coles · goals",
};

const OUTCOME_TEXT = (o: Outcome, home: string, away: string): string =>
  o === "home" ? home : o === "away" ? away : "a draw";

type AnalysisState = AsyncState<MatchAnalysisResponse>;

export function ModelCouncil({
  state,
  home,
  away,
  onRetry,
}: {
  state: AnalysisState;
  home: string;
  away: string;
  onRetry: () => void;
}) {
  return (
    <section className="panel" aria-labelledby="mc-h">
      <div className="panel__head">
        <h2 id="mc-h">Model council</h2>
        <KindChip state={state} />
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: "1.1rem" }}>
        <Body state={state} home={home} away={away} onRetry={onRetry} />
      </div>
    </section>
  );
}

function KindChip({ state }: { state: AnalysisState }) {
  if (state.status !== "ready" || !state.data.available || !state.data.analysis) return null;
  const kind = state.data.analysis.analysis_kind;
  return (
    <span
      className={`chip ${kind === "replay" ? "chip--neutral" : "chip--horizon"}`}
      style={{ marginLeft: "auto" }}
    >
      {kind === "replay" ? "Replay" : "Preview"}
    </span>
  );
}

function Body({
  state,
  home,
  away,
  onRetry,
}: {
  state: AnalysisState;
  home: string;
  away: string;
  onRetry: () => void;
}) {
  if (state.status === "loading")
    return (
      <>
        <Loading label="Fitting the models" />
        <BlockSkeleton lines={4} />
      </>
    );
  if (state.status === "error") {
    const warming = /HTTP 503/.test(state.error.message);
    return (
      <div className="stack" style={{ ["--gap" as string]: ".6rem" }}>
        <p className="small dim" style={{ margin: 0 }}>
          {warming
            ? "Model engine warming up — the council isn’t ready yet."
            : "Couldn’t compute the model council for this fixture right now. The rest of the page is unaffected."}
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
  if (!resp.available || !resp.analysis) {
    return (
      <div className="callout callout--info">
        <InfoIcon size={18} />
        <div>
          <div className="callout__title">Model council unavailable here</div>
          {resp.reason ??
            "This fixture can’t be modelled from the current snapshot."}
        </div>
      </div>
    );
  }

  const a = resp.analysis;
  if (a.abstained) return <Abstained analysis={a} />;
  return <Council analysis={a} home={home} away={away} />;
}

/** Not enough history — the same honest floor a seal uses. No fabricated numbers. */
function Abstained({ analysis }: { analysis: MatchAnalysis }) {
  const [home, away] = [analysis.match.home_team, analysis.match.away_team];
  return (
    <div className="callout callout--info">
      <InfoIcon size={18} />
      <div>
        <div className="callout__title">Not enough history to model this fixture</div>
        {analysis.abstain_reason ??
          `The models need at least ${analysis.min_team_matches} qualifying matches per side.`}
        <div className="small dim" style={{ marginTop: ".4rem" }}>
          {home}: {analysis.team_history[home] ?? 0} · {away}: {analysis.team_history[away] ?? 0}{" "}
          qualifying matches before kickoff. Abstaining is the honest answer, not a guess.
        </div>
      </div>
    </div>
  );
}

function Council({
  analysis,
  home,
  away,
}: {
  analysis: MatchAnalysis;
  home: string;
  away: string;
}) {
  const models = analysis.models;
  const voices = models.filter((m) => m.role === "voice" && m.probs);
  const baseline = models.find((m) => m.role === "baseline" && m.probs);
  const variants = models.filter((m) => m.role === "variant" && m.probs);
  const c = analysis.council;

  const lead =
    c.voices_agree && c.leading_outcome
      ? `Both models lean toward ${OUTCOME_TEXT(c.leading_outcome, home, away)}.`
      : "The two models disagree on the likeliest outcome.";

  return (
    <>
      <ObjectTypeTrust analysis={analysis} />

      {/* At a glance — a descriptive summary, never an averaged consensus. */}
      <p className="measure" style={{ margin: 0 }}>
        <strong>{lead}</strong>{" "}
        <span className="muted">
          Two independent methods; a climatology baseline is shown for reference. Nothing here is
          an average — you always see each voice.
        </span>
      </p>

      {/* The voices, side by side. */}
      <div className="stack" style={{ ["--gap" as string]: "1rem" }}>
        {voices.map((m) => (
          <VoiceRow key={m.family} model={m} home={home} away={away} />
        ))}
      </div>

      {c.max_delta_p != null && !c.voices_agree && (
        <div className="callout callout--info">
          <InfoIcon size={18} />
          <div>
            <div className="callout__title">Why they differ</div>
            The ratings model weighs overall team strength; the goal model weighs recent
            attack/defence rates. They diverge by up to{" "}
            <span className="num">{Math.round((c.max_delta_p ?? 0) * 100)}</span> points on an
            outcome here — a genuine disagreement worth noting, not a rounding gap.
          </div>
        </div>
      )}

      {/* Likely goals & score live in the Score outlook section below, from the
          same goal model. */}

      {/* Baseline + variants — disclosed, never a vote. */}
      <details className="council-more">
        <summary>Baseline &amp; model variants</summary>
        <div className="stack" style={{ ["--gap" as string]: ".8rem", marginTop: ".75rem" }}>
          {baseline?.probs && (
            <p className="small muted" style={{ margin: 0 }}>
              <strong>Climatology baseline</strong> (league base rates, not a team opinion):{" "}
              {home} {pctWhole(baseline.probs.home)} · Draw {pctWhole(baseline.probs.draw)} · {away}{" "}
              {pctWhole(baseline.probs.away)}. A voice earns its keep by beating this.
            </p>
          )}
          {variants.length > 0 && (
            <div className="small muted">
              <strong>Goal-model variants</strong> — the same fit, different low-score handling.
              They are disclosure, not extra votes:
              <ul style={{ margin: ".4rem 0 0" }}>
                {variants.map((m) => (
                  <li key={m.family}>
                    {m.family}: {m.probs && (
                      <span className="num">
                        {pctWhole(m.probs.home)}/{pctWhole(m.probs.draw)}/{pctWhole(m.probs.away)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </details>
    </>
  );
}

function VoiceRow({ model, home, away }: { model: CouncilModel; home: string; away: string }) {
  const probs = model.probs as Probs;
  return (
    <div className="council-voice">
      <div className="council-voice__head">
        <span className="council-voice__name">{VOICE_LABEL[model.family] ?? model.family}</span>
      </div>
      <ProbabilityBar probs={probs} home={home} away={away} height={34} />
    </div>
  );
}

/** The object-type guarantee: a Replay is reconstructed pre-kickoff and is NOT a
 *  forecast that existed at the time; a Preview will move and is not sealed. */
function ObjectTypeTrust({ analysis }: { analysis: MatchAnalysis }) {
  const replay = analysis.analysis_kind === "replay";
  return (
    <TrustStrip
      items={[
        {
          icon: <ShieldCheckIcon />,
          label: replay
            ? "Replay — reconstructed with pre-kickoff data only"
            : "Preview — computed now, not sealed",
          tipLabel: "What this analysis is",
          tip: replay
            ? `Every model was fit using only matches before kickoff (cutoff ${utc(
                analysis.information_cutoff_utc,
              )}). This is what the methods WOULD have said — it is not a forecast that existed at the time, and it never enters the track record.`
            : `Computed from everything known so far (up to ${utc(
                analysis.information_cutoff_utc,
              )}). It will move as new results arrive and is not sealed. To put a forecast on the record, seal it before kickoff.`,
        },
      ]}
    />
  );
}
