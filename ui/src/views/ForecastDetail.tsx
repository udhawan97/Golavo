import type { ForecastArtifact } from "../lib/contract";
import type { ForecastMode } from "../lib/hooks";
import { FAMILY_LABELS } from "../lib/contract";
import { fetchForecast, fetchForecasts } from "../lib/api";
import { num, pct, utc, relative } from "../lib/format";
import { useAsync, useForecastMode } from "../lib/hooks";
import { verdictSummary } from "../lib/summary";
import { AlertIcon, ChevronRight, ClockIcon, GlobeIcon, InfoIcon, LinkIcon, VoidIcon } from "../components/icons";
import { Hash, HorizonChip, ProbabilityBar, StatusChip, UncertaintyTag } from "../components/primitives";
import { ScoreMatrixHeatmap } from "../components/ScoreMatrixHeatmap";
import { SealStamp } from "../components/SealStamp";
import { Provenance } from "../components/Provenance";
import { ScoredPanel } from "../components/ScoredPanel";
import { AiDeepRead } from "../components/AiDeepRead";
import { CommentatorsNotebook } from "../components/CommentatorsNotebook";
import { BlockSkeleton, EmptyState, ErrorState, Loading } from "../components/states";

export function ForecastDetail({ id }: { id: string }) {
  const state = useAsync(
    () => Promise.all([fetchForecast(id), fetchForecasts()]),
    [id],
  );

  if (state.status === "loading") return (<><Loading label="Loading forecast" /><Breadcrumb /><div style={{ marginTop: "1rem" }}><BlockSkeleton /></div></>);
  if (state.status === "error") return (<><Breadcrumb /><ErrorState error={state.error} /></>);

  const [artifact, all] = state.data;
  if (!artifact) {
    return (<><Breadcrumb /><EmptyState title="Forecast not found">No sealed artifact matches this id. It may have been superseded or never existed.</EmptyState></>);
  }
  const supersededBy = all.find((a) => a.supersedes === artifact.artifact_id)?.artifact_id ?? null;
  return <Detail artifact={artifact} supersededBy={supersededBy} />;
}

function Detail({ artifact, supersededBy }: { artifact: ForecastArtifact; supersededBy: string | null }) {
  const { match, forecast, model, status } = artifact;
  const [mode, setMode] = useForecastMode();
  const abstained = status === "abstained";
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <Breadcrumb label={`${match.home_team} v ${match.away_team}`} />

      <header className="stack" style={{ ["--gap" as string]: ".55rem" }}>
        <div className="badge-row">
          <StatusChip status={status} />
          <HorizonChip horizon={forecast.horizon} />
          {match.neutral_venue
            ? <span className="chip chip--neutral">Neutral venue</span>
            : <span className="chip chip--neutral">Home advantage · {match.home_team}</span>}
          {!abstained && <ModeToggle mode={mode} setMode={setMode} />}
        </div>
        <h1>{match.home_team} <span className="dim" style={{ fontWeight: 400 }}>v</span> {match.away_team}</h1>
        <div className="md-card__meta" style={{ marginTop: 0 }}>
          <span>{match.competition}{match.stage ? ` · ${match.stage}` : ""}</span>
          <span><ClockIcon /> <span className="num">{utc(match.kickoff_utc)}</span> <span className="dim">({relative(match.kickoff_utc)})</span></span>
          <span><GlobeIcon /> {match.city ? `${match.city}, ${match.country}` : match.country ?? "—"}</span>
          <span className="dim mono">{match.match_id}</span>
        </div>
      </header>

      {artifact.supersedes && (
        <div className="callout callout--info">
          <LinkIcon size={18} />
          <div>
            <div className="callout__title">Re-sealed</div>
            This artifact supersedes an earlier seal for the same fixture — a new immutable
            record rather than an edit. <a href={`#/forecast/${artifact.supersedes}`}>View the earlier seal ›</a>
          </div>
        </div>
      )}
      {supersededBy && (
        <div className="callout callout--warn">
          <AlertIcon size={18} />
          <div>
            <div className="callout__title">Superseded</div>
            A later seal replaces this one. This record is preserved unchanged for audit.{" "}
            <a href={`#/forecast/${supersededBy}`}>View the current seal ›</a>
          </div>
        </div>
      )}

      <div className="two-col">
        <div className="stack" style={{ ["--gap" as string]: "1.1rem" }}>
          {abstained
            ? <AbstainPanel reason={forecast.abstain_reason} />
            : (
              <>
                {status === "voided" && <VoidBanner reason={artifact.void_reason ?? null} />}
                <VerdictPanel artifact={artifact} showBar={status !== "scored"} dim={status === "voided"} />
                {mode === "casual"
                  ? <CasualDetails artifact={artifact} />
                  : <ExpertDetails artifact={artifact} />}
                {status === "scored" && <ScoredPanel artifact={artifact} />}
              </>
            )}
        </div>
        <div className="stack" style={{ ["--gap" as string]: "1.1rem" }}>
          <SealStamp artifact={artifact} />
          <Provenance inputs={artifact.inputs} />
          <p className="small dim">
            Model family: {FAMILY_LABELS[model.family]}. This surface is read-only; nothing here
            can alter a sealed artifact.
          </p>
        </div>
      </div>

      {/* Deterministic, source-backed match facts — subordinate to the seal. */}
      <CommentatorsNotebook artifact={artifact} />

      {/* Optional, off by default, and subordinate to the sealed numbers above. */}
      <AiDeepRead artifact={artifact} />
    </div>
  );
}

/** Casual ⇄ Expert depth switch. Two buttons, aria-pressed; it changes how much
 *  detail is shown, never the probabilities. */
function ModeToggle({ mode, setMode }: { mode: ForecastMode; setMode: (m: ForecastMode) => void }) {
  const modes: Array<[ForecastMode, string]> = [["casual", "Casual"], ["expert", "Expert"]];
  return (
    <div className="mode-toggle" role="group" aria-label="Detail level" style={{ marginLeft: "auto" }}>
      {modes.map(([value, label]) => (
        <button
          key={value}
          type="button"
          className={`mode-toggle__btn${mode === value ? " is-active" : ""}`}
          aria-pressed={mode === value}
          onClick={() => setMode(value)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/** The verdict bar + one plain-language headline. Identical in both modes — the
 *  sealed certainty never changes when the depth toggle flips. */
function VerdictPanel({ artifact, showBar, dim }: { artifact: ForecastArtifact; showBar: boolean; dim: boolean }) {
  const { forecast, match } = artifact;
  const summary = verdictSummary(artifact);
  const awaitingKickoff = artifact.status === "sealed" && new Date(match.kickoff_utc).getTime() > Date.now();
  return (
    <section className="panel" aria-labelledby="fc-h">
      <div className="panel__head">
        <h2 id="fc-h">Forecast</h2>
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>1X2 · regulation</span>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: "1rem", opacity: dim ? 0.6 : 1 }}>
        <p className="verdict">{summary.headline}</p>
        {showBar && forecast.probs && (
          <ProbabilityBar probs={forecast.probs} home={match.home_team} away={match.away_team} height={44} />
        )}
        {awaitingKickoff && (
          <p className="callout callout--info" style={{ fontSize: ".88rem" }}>
            <InfoIcon size={18} />
            <span>Sealed and awaiting kickoff. When full time is reached, the result is scored
            against these exact probabilities — they will not change.</span>
          </p>
        )}
      </div>
    </section>
  );
}

/** Casual depth: the plain-language reading plus a few cited, sealed-number facts. */
function CasualDetails({ artifact }: { artifact: ForecastArtifact }) {
  const { forecast, match } = artifact;
  const summary = verdictSummary(artifact);
  const sm = forecast.score_matrix;
  const xg = forecast.expected_goals;
  return (
    <section className="panel" aria-labelledby="cas-h">
      <div className="panel__head">
        <h2 id="cas-h">In plain terms</h2>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: ".85rem" }}>
        <p className="casual-detail">{summary.detail}</p>
        <div className="cited">
          <div className="cited__cap">Straight from the sealed model — no AI wrote these.</div>
          <ul className="cited__list">
            {sm && (
              <li>
                Most likely score{" "}
                <b className="num">{match.home_team} {sm.most_likely.home}–{sm.most_likely.away} {match.away_team}</b>{" "}
                at <b className="num">{pct(sm.most_likely.probability)}</b>
              </li>
            )}
            {xg && (
              <li>
                Expected goals <b className="num">{num(xg.home, 1)}</b> {match.home_team}{" · "}
                <b className="num">{num(xg.away, 1)}</b> {match.away_team}
              </li>
            )}
            <li>Model uncertainty for this fixture: <b>{forecast.uncertainty}</b></li>
          </ul>
        </div>
        <p className="small dim">
          Switch to <b>Expert</b> for the full exact-score grid, model versions, and calibration
          context. The probabilities are the same in either view.
        </p>
      </div>
    </section>
  );
}

/** Expert depth: exact-score heatmap, the model's own spread, versions, and
 *  where to check its live calibration. Same sealed numbers, more of them. */
function ExpertDetails({ artifact }: { artifact: ForecastArtifact }) {
  const { forecast, match, model, inputs } = artifact;
  const sm = forecast.score_matrix;
  const xg = forecast.expected_goals;
  return (
    <>
      <section className="panel" aria-labelledby="grid-h">
        <div className="panel__head">
          <h2 id="grid-h">Exact-score distribution</h2>
          <UncertaintyTag level={forecast.uncertainty} />
        </div>
        <div className="panel__body stack" style={{ ["--gap" as string]: ".9rem" }}>
          {sm ? (
            <>
              <ScoreMatrixHeatmap matrix={sm} home={match.home_team} away={match.away_team} />
              <div className="metric-grid">
                <Stat value={`${sm.most_likely.home}–${sm.most_likely.away}`} label="Most likely score"
                  hint={`${pct(sm.most_likely.probability)} of the time`} />
                {xg && <Stat value={num(xg.home, 2)} label={`Expected goals · ${match.home_team}`} />}
                {xg && <Stat value={num(xg.away, 2)} label={`Expected goals · ${match.away_team}`} />}
                <Stat value={pct(sm.tail.probability)} label={`Beyond ${sm.max_goals} goals a side`}
                  hint="folded into the tail" />
              </div>
              <p className="small dim">
                Every cell is the sealed model's probability of that exact score. The grid's
                win/draw/loss totals reproduce the 1X2 bar above; {pct(sm.tail.probability)} of the
                distribution lies beyond {sm.max_goals} goals for a side (the tail: {match.home_team}{" "}
                {pct(sm.tail.home)}, draw {pct(sm.tail.draw)}, {match.away_team} {pct(sm.tail.away)}).
              </p>
            </>
          ) : (
            <p className="callout callout--info" style={{ fontSize: ".9rem" }}>
              <InfoIcon size={18} />
              <span>
                This model family ({FAMILY_LABELS[model.family]}) forecasts match outcomes, not
                goals, so it implies no exact-score distribution. The 1X2 probabilities above are
                its full output — no grid is shown rather than a fabricated one.
              </span>
            </p>
          )}
        </div>
      </section>

      <section className="panel" aria-labelledby="ver-h">
        <div className="panel__head">
          <h2 id="ver-h">Model &amp; versions</h2>
        </div>
        <div className="panel__body">
          <dl className="kv">
            <dt>Family</dt><dd>{FAMILY_LABELS[model.family]}</dd>
            <dt>Model id</dt><dd className="mono">{model.model_id}</dd>
            <dt>Engine version</dt><dd className="num">{model.version}</dd>
            <dt>Seed</dt><dd className="num">{model.seed}</dd>
            <dt>Training cutoff</dt><dd className="num">{utc(inputs.training_cutoff_utc)}</dd>
            <dt>Params hash</dt><dd><Hash value={model.params_hash} /></dd>
            <dt>Code git sha</dt><dd><Hash value={model.code_git_sha} /></dd>
          </dl>
        </div>
      </section>

      <div className="callout callout--info" style={{ fontSize: ".9rem" }}>
        <InfoIcon size={18} />
        <div>
          <div className="callout__title">Calibration context</div>
          The model flags <b>{forecast.uncertainty}</b> uncertainty here. How well this engine's
          sealed probabilities have matched reality — across every scored seal — is tracked in the{" "}
          <a href="#/ledger">prediction ledger ›</a>
        </div>
      </div>
    </>
  );
}

function Stat({ value, label, hint }: { value: string; label: string; hint?: string }) {
  return (
    <div className="metric">
      <div className="metric__val num">{value}</div>
      <div className="metric__label">{label}</div>
      {hint && <div className="metric__hint">{hint}</div>}
    </div>
  );
}

function AbstainPanel({ reason }: { reason: string | null }) {
  return (
    <section className="panel" aria-labelledby="ab-h">
      <div className="panel__head">
        <VoidIcon size={17} style={{ color: "var(--wave)" }} />
        <h2 id="ab-h">Abstained — no forecast issued</h2>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: ".8rem" }}>
        <div className="callout callout--info">
          <InfoIcon size={18} />
          <div>
            <div className="callout__title">Why there are no probabilities</div>
            {reason ?? "The model declined to forecast this fixture."}
          </div>
        </div>
        <p className="small dim">
          Abstaining is a first-class outcome: the model records that it could not honestly
          forecast, rather than emit a number it does not stand behind. With no probabilities there
          is no exact-score grid either — the seal and provenance below still pin exactly which
          model and inputs made that call.
        </p>
      </div>
    </section>
  );
}

function VoidBanner({ reason }: { reason: string | null }) {
  return (
    <div className="callout callout--void">
      <VoidIcon size={18} />
      <div>
        <div className="callout__title">Voided — excluded from scoring</div>
        The sealed forecast is preserved below for audit, but this fixture is not scored.
        {reason && <> Recorded reason: <i>{reason}</i>.</>}
      </div>
    </div>
  );
}

function Breadcrumb({ label }: { label?: string }) {
  return (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      <a href="#/">Matchday</a>
      {label && <><ChevronRight size={14} /><span aria-current="page">{label}</span></>}
    </nav>
  );
}
