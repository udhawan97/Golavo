import type { ForecastArtifact } from "../lib/contract";
import { FAMILY_LABELS } from "../lib/contract";
import { fetchForecast, fetchForecasts } from "../lib/api";
import { num, relative, utc } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { AlertIcon, ChevronRight, ClockIcon, GlobeIcon, InfoIcon, LinkIcon, VoidIcon } from "../components/icons";
import { HorizonChip, ProbabilityBar, StatusChip, UncertaintyTag } from "../components/primitives";
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
          {status === "abstained"
            ? <AbstainPanel reason={forecast.abstain_reason} />
            : (
              <>
                {status === "voided" && <VoidBanner reason={artifact.void_reason ?? null} />}
                <ForecastReadPanel artifact={artifact} showBar={status !== "scored"} dim={status === "voided"} />
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

function ForecastReadPanel({ artifact, showBar, dim }: { artifact: ForecastArtifact; showBar: boolean; dim: boolean }) {
  const { forecast, match } = artifact;
  const xg = forecast.expected_goals;
  const awaitingKickoff = artifact.status === "sealed" && new Date(match.kickoff_utc).getTime() > Date.now();
  return (
    <section className="panel" aria-labelledby="fc-h">
      <div className="panel__head">
        <h2 id="fc-h">Forecast</h2>
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>1X2 · regulation</span>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: "1rem", opacity: dim ? 0.6 : 1 }}>
        <div className="badge-row" style={{ justifyContent: "space-between" }}>
          <UncertaintyTag level={forecast.uncertainty} />
          {xg && (
            <span className="small muted">
              Expected goals <b className="num" style={{ color: "var(--text)" }}>{num(xg.home, 1)}</b> {match.home_team}
              {" · "}<b className="num" style={{ color: "var(--text)" }}>{num(xg.away, 1)}</b> {match.away_team}
            </span>
          )}
        </div>
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
          forecast, rather than emit a number it does not stand behind. The seal and provenance
          below still pin exactly which model and inputs made that call.
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
