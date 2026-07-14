import { Fragment } from "react";
import type { ForecastArtifact } from "../lib/contract";
import type { ForecastMode } from "../lib/hooks";
import { FAMILY_LABELS, HORIZON_LABELS } from "../lib/contract";
import { fetchForecast, fetchForecasts } from "../lib/api";
import { deriveMarkets } from "../lib/markets";
import { num, pct, pctWhole, inWords, largestRemainder, utc, utcDate } from "../lib/format";
import { useAsync, useForecastMode } from "../lib/hooks";
import { verdictSummary } from "../lib/summary";
import { AlertIcon, ChevronRight, InfoIcon, LinkIcon, ScaleIcon, ShieldCheckIcon, SparkIcon, VoidIcon } from "../components/icons";
import { Hash, HorizonChip, ProbabilityBar, StatTile, StatusChip, TrustStrip, UncertaintyTag } from "../components/primitives";
import { MatchHeader } from "../components/MatchHeader";
import { Drawer } from "../components/disclosure";
import { ScoreMatrixHeatmap } from "../components/ScoreMatrixHeatmap";
import { SealStamp } from "../components/SealStamp";
import { Provenance } from "../components/Provenance";
import { ScoredPanel } from "../components/ScoredPanel";
import { AiDeepRead } from "../components/ai/AiDeepRead";
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
    return (<><Breadcrumb /><EmptyState title="Forecast not found">No sealed artifact matches this id. It may have been superseded or never existed.{" "}<a href="#/matches">Search matches ›</a></EmptyState></>);
  }
  const supersededBy = all.find((a) => a.supersedes === artifact.artifact_id)?.artifact_id ?? null;
  const previous = artifact.supersedes
    ? all.find((a) => a.artifact_id === artifact.supersedes) ?? null
    : null;
  return <Detail artifact={artifact} supersededBy={supersededBy} previous={previous} />;
}

function Detail({
  artifact,
  supersededBy,
  previous,
}: {
  artifact: ForecastArtifact;
  supersededBy: string | null;
  previous: ForecastArtifact | null;
}) {
  const { match, forecast, status } = artifact;
  const [mode, setMode] = useForecastMode();
  const abstained = status === "abstained";
  const venue = match.city ? `${match.city}, ${match.country}` : match.country ?? "—";
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <Breadcrumb label={`${match.home_team} v ${match.away_team}`} />

      <MatchHeader
        home={match.home_team}
        away={match.away_team}
        competition={`${match.competition}${match.stage ? ` · ${match.stage}` : ""}`}
        kickoffUtc={match.kickoff_utc}
        venue={venue}
        chips={
          <>
            <StatusChip status={status} />
            <HorizonChip horizon={forecast.horizon} />
            {match.neutral_venue
              ? <span className="chip chip--neutral">Neutral venue</span>
              : <span className="chip chip--neutral">Home · {match.home_team}</span>}
          </>
        }
        right={!abstained ? <ModeToggle mode={mode} setMode={setMode} /> : undefined}
      />

      <ForecastTrustStrip artifact={artifact} />

      {artifact.supersedes && (
        <div className="callout callout--info">
          <LinkIcon size={18} />
          <div>
            <div className="callout__title">Re-sealed</div>
            This artifact supersedes an earlier seal for the same fixture — a new immutable
            record rather than an edit. <a href={`#/forecast/${artifact.supersedes}`}>View the earlier seal ›</a>
            <WhatChanged current={artifact} previous={previous} />
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
                <PlainTerms artifact={artifact} />
                {status === "scored" && <ScoredPanel artifact={artifact} />}
              </>
            )}
        </div>
        <div className="stack" style={{ ["--gap" as string]: "1.1rem" }}>
          <SealStamp artifact={artifact} />
        </div>
      </div>

      {/* Deterministic briefing + source-backed notebook — subordinate to the seal. */}
      <CommentatorsNotebook artifact={artifact} />

      {/* Expert depth — same sealed numbers, collapsed in Casual, opened in Expert. */}
      <ExpertDrawers artifact={artifact} mode={mode} />

      {/* Optional, off by default, and subordinate to the sealed numbers above. */}
      <AiDeepRead
        source={{ kind: "forecast", artifactId: artifact.artifact_id }}
        context={{
          homeTeam: match.home_team,
          awayTeam: match.away_team,
          uncertainty: forecast.uncertainty,
        }}
      />
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

/** What moved between the earlier seal and this one — deterministic line movement
 *  between two sealed pre-kickoff forecasts, not an edit and not AI. Whole-number
 *  points via the same largest-remainder rounding, so the three deltas sum to 0. */
function WhatChanged({ current, previous }: { current: ForecastArtifact; previous: ForecastArtifact | null }) {
  const cur = current.forecast.probs;
  const prev = previous?.forecast.probs;
  if (!prev || !cur) return null;
  const [ph, pd, pa] = largestRemainder([prev.home, prev.draw, prev.away]);
  const [ch, cd, ca] = largestRemainder([cur.home, cur.draw, cur.away]);
  const rows = [
    { label: current.match.home_team, was: ph, now: ch },
    { label: "Draw", was: pd, now: cd },
    { label: current.match.away_team, was: pa, now: ca },
  ];
  if (rows.every((r) => r.now === r.was)) {
    return <p className="whatmoved__same small muted">Identical to the earlier seal — nothing moved.</p>;
  }
  return (
    <ul className="whatmoved">
      {rows.map((r) => {
        const delta = r.now - r.was;
        const dir = delta > 0 ? "up" : delta < 0 ? "down" : "flat";
        return (
          <li className="whatmoved__row" key={r.label}>
            <span className="whatmoved__team">{r.label}</span>
            <span className="whatmoved__nums num">
              <span className="dim">{r.was}%</span> → <b>{r.now}%</b>
            </span>
            <span className={`whatmoved__delta whatmoved__delta--${dir}`}>
              {dir === "up" ? "▲" : dir === "down" ? "▼" : "±"} {delta > 0 ? `+${delta}` : delta === 0 ? "0" : delta}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** The single trust row. Each guarantee is stated once here; the full wording
 *  lives behind ⓘ, so panels below need not restate it. "Sealed before kickoff"
 *  and "AI never changes the numbers" are always visible, never hidden. */
function ForecastTrustStrip({ artifact }: { artifact: ForecastArtifact }) {
  const { forecast } = artifact;
  return (
    <TrustStrip
      items={[
        {
          icon: <ShieldCheckIcon />,
          label: (
            <>
              Sealed {utcDate(forecast.sealed_at_utc)} · {HORIZON_LABELS[forecast.horizon]} before kickoff
            </>
          ),
          tipLabel: "How sealing works",
          tip: "A forecast is only honest if it was sealed before kickoff. These probabilities were locked at the seal and are scored, unchanged, against the result — Golavo never retro-forecasts a played match.",
        },
        {
          icon: <ScaleIcon />,
          label: "Deterministic",
          tipLabel: "What deterministic means",
          tip: "The same inputs and seed reproduce this artifact byte-for-byte. Nothing here is random, and nothing on this read-only page can alter a sealed number.",
        },
        {
          icon: <SparkIcon />,
          label: "AI never changes the numbers",
          tipLabel: "The role of AI here",
          tip: "The optional AI Deep Read (below, off by default) can only read and cite these sealed numbers. It cannot change a probability or improve accuracy.",
        },
      ]}
    />
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
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>Win · Draw · Win — 90 min</span>
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

/** The always-visible plain-language reading: a few cited, sealed-number facts in
 *  whole percentages with a natural-frequency gloss. Identical in both modes. */
function PlainTerms({ artifact }: { artifact: ForecastArtifact }) {
  const { forecast, match } = artifact;
  const probs = forecast.probs;
  const sm = forecast.score_matrix;
  const xg = forecast.expected_goals;
  const ranked = probs
    ? [
        { who: match.home_team, suffix: " to win", p: probs.home },
        { who: "A draw", suffix: "", p: probs.draw },
        { who: match.away_team, suffix: " to win", p: probs.away },
      ].sort((a, b) => b.p - a.p)
    : [];
  const leader = ranked[0] ?? null;
  return (
    <section className="panel" aria-labelledby="cas-h">
      <div className="panel__head">
        <h2 id="cas-h">In plain terms</h2>
      </div>
      <div className="panel__body">
        <div className="cited">
          <div className="cited__cap">Straight from the sealed model — no AI wrote these.</div>
          <ul className="cited__list">
            {leader && (
              <li>
                Most likely outcome: <b>{leader.who}{leader.suffix}</b> at{" "}
                <b className="num">{pctWhole(leader.p)}</b>{" "}
                <span className="dim">({inWords(leader.p)})</span>
              </li>
            )}
            {sm && (
              <li>
                Most likely score{" "}
                <b className="num">{match.home_team} {sm.most_likely.home}–{sm.most_likely.away} {match.away_team}</b>{" "}
                at <b className="num">{pctWhole(sm.most_likely.probability)}</b>{" "}
                <span className="dim">({inWords(sm.most_likely.probability)})</span>
              </li>
            )}
            {xg && (
              <li>
                Expected goals <b className="num">{num(xg.home, 1)}</b> {match.home_team}{" · "}
                <b className="num">{num(xg.away, 1)}</b> {match.away_team}
              </li>
            )}
            <li>How uncertain the model is here: <b>{forecast.uncertainty}</b></li>
          </ul>
        </div>
      </div>
    </section>
  );
}

/** Expert depth as collapsible drawers over the SAME sealed numbers — collapsed
 *  in Casual, opened in Expert. Nothing here is a different number; it is more of
 *  the same one, plus the provenance an auditor needs. */
function ExpertDrawers({ artifact, mode }: { artifact: ForecastArtifact; mode: ForecastMode }) {
  const { forecast, match, model, inputs } = artifact;
  const open = mode === "expert";
  const sm = forecast.score_matrix;
  const xg = forecast.expected_goals;
  const markets = deriveMarkets(forecast);
  const hasMarkets = !!(markets.doubleChance || markets.thresholds);
  return (
    <div className="stack" style={{ ["--gap" as string]: ".7rem" }}>
      <Drawer title="Exact-score distribution" defaultOpen={open} chip={<UncertaintyTag level={forecast.uncertainty} />}>
        {sm ? (
          <div className="stack" style={{ ["--gap" as string]: ".9rem" }}>
            <ScoreMatrixHeatmap matrix={sm} home={match.home_team} away={match.away_team} />
            <div className="stat-grid">
              <StatTile value={`${sm.most_likely.home}–${sm.most_likely.away}`} label="Most likely score"
                hint={`${pctWhole(sm.most_likely.probability)} of the time`} />
              {xg && <StatTile value={num(xg.home, 2)} label={`Expected goals · ${match.home_team}`} />}
              {xg && <StatTile value={num(xg.away, 2)} label={`Expected goals · ${match.away_team}`} />}
              <StatTile value={pct(sm.tail.probability)} label={`Very high scores (${sm.max_goals + 1}+ a side)`}
                hint="grouped into one number" />
            </div>
            <p className="small dim measure">
              Every cell is the sealed model's probability of that exact score. The grid's
              win/draw/win totals reproduce the bar above; {pct(sm.tail.probability)} of the
              distribution lies beyond {sm.max_goals} goals for a side.
            </p>
          </div>
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
      </Drawer>

      {hasMarkets && (
        <Drawer title="Outcome & goal summaries" defaultOpen={open} chip={<span className="chip chip--neutral">same grid, re-sliced</span>}>
          <DerivedMarketsBody artifact={artifact} />
        </Drawer>
      )}

      <Drawer title="Model & versions" defaultOpen={open}>
        <dl className="kv">
          <dt>Family</dt><dd>{FAMILY_LABELS[model.family]}</dd>
          <dt>Model id</dt><dd className="mono">{model.model_id}</dd>
          <dt>Engine version</dt><dd className="num">{model.version}</dd>
          <dt>Seed</dt><dd className="num">{model.seed}</dd>
          <dt>Training cutoff</dt><dd className="num">{utc(inputs.training_cutoff_utc)}</dd>
          <dt>Params hash</dt><dd><Hash value={model.params_hash} /></dd>
          <dt>Code git sha</dt><dd><Hash value={model.code_git_sha} /></dd>
        </dl>
      </Drawer>

      <Drawer title="Provenance & inputs" defaultOpen={open}>
        <Provenance inputs={inputs} matchId={match.match_id} artifactId={artifact.artifact_id} />
      </Drawer>

      <Drawer title="Calibration context" defaultOpen={open}>
        <p className="measure" style={{ margin: 0 }}>
          The model flags <b>{forecast.uncertainty}</b> uncertainty for this fixture. How well this
          engine's sealed probabilities have matched reality — across every scored seal — is tracked
          in the <a href="#/lab/track-record">prediction track record ›</a>
        </p>
      </Drawer>
    </div>
  );
}

/** Exact re-buckets of the sealed distribution — analysis, not a betting product.
 *  Every figure is a marginal of the same grid the heatmap shows, so they reconcile
 *  with the numbers above by construction. Body only; a Drawer supplies the frame. */
function DerivedMarketsBody({ artifact }: { artifact: ForecastArtifact }) {
  const { forecast, match } = artifact;
  const markets = deriveMarkets(forecast);
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.1rem" }}>
      <p className="small dim measure" style={{ margin: 0 }}>
        Re-buckets of the sealed distribution above — no new model, no new data. Every number here is
        a re-slice of the same score grid, so it always adds up to the win/draw/win and score numbers.
      </p>
      {markets.doubleChance && (
        <div>
          <h3 className="small muted" style={{ margin: "0 0 .5rem" }}>Combined outcomes</h3>
          <div className="stat-grid">
            <StatTile value={pct(markets.doubleChance.home_or_draw)} label={`${match.home_team} or draw`} />
            <StatTile value={pct(markets.doubleChance.draw_or_away)} label={`Draw or ${match.away_team}`} />
            <StatTile value={pct(markets.doubleChance.home_or_away)} label="Either side wins (no draw)" />
          </div>
        </div>
      )}
      {markets.thresholds && (
        <div>
          <h3 className="small muted" style={{ margin: "0 0 .5rem" }}>Chance of more than…</h3>
          <dl className="kv">
            {markets.thresholds.map((t) => (
              <Fragment key={t.line}>
                <dt><span className="num">{t.line}</span> total goals</dt>
                <dd className="num">{pct(t.over)}</dd>
              </Fragment>
            ))}
          </dl>
        </div>
      )}
      {markets.bands && (
        <div>
          <h3 className="small muted" style={{ margin: "0 0 .5rem" }}>Total goals in the match</h3>
          <div className="small" style={{ display: "flex", flexWrap: "wrap", gap: ".35rem 1.1rem" }}>
            {markets.bands.map((b) => (
              <span key={b.total}>
                <span className="num">{b.total}</span>{" "}
                <span className="dim">{pct(b.probability)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
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
      <a href="#/lab/forecasts">Sealed forecasts</a>
      {label && <><ChevronRight size={14} /><span aria-current="page">{label}</span></>}
    </nav>
  );
}
