/**
 * The REAL prediction ledger: every genuine seal and what became of it.
 *
 * This view renders sealed→scored/voided chains aggregated from immutable
 * artifacts — never evaluation backtests. Those live under #/lab/backtests and
 * are labeled as such; the split is the product's honesty boundary.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  CalibrationChain,
  CalibrationSummary,
  Probs,
  SettlementPendingReason,
  SettlementReport,
} from "../lib/contract";
import { FAMILY_LABELS, HORIZON_LABELS } from "../lib/contract";
import { DATA_SOURCE, fetchCalibration, settleForecasts } from "../lib/api";
import { num, pct, utc, utcDate } from "../lib/format";
import { METRIC_GLOSS } from "../lib/glossary";
import { useAsync } from "../lib/hooks";
import { useDataRefreshPolicy } from "../lib/fixtures";
import { beginActivity, endActivity } from "../lib/activity";
import { ReliabilityDiagram } from "../components/ReliabilityDiagram";
import { BlockSkeleton, EmptyState, ErrorState, Loading } from "../components/states";

type SettlementState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "ready"; report: SettlementReport }
  | { status: "error"; error: Error };

export function PredictionLedger() {
  const [revision, setRevision] = useState(0);
  const [refreshPolicy] = useDataRefreshPolicy();
  const [settlement, setSettlement] = useState<SettlementState>({ status: "idle" });
  const state = useAsync(fetchCalibration, [revision]);
  const checkResults = useCallback(async () => {
    if (DATA_SOURCE !== "live") return;
    setSettlement({ status: "checking" });
    beginActivity("results", "Checking finished match results…");
    try {
      const report = await settleForecasts();
      setSettlement({ status: "ready", report });
      setRevision((value) => value + 1);
    } catch (error) {
      setSettlement({
        status: "error",
        error: error instanceof Error ? error : new Error(String(error)),
      });
    } finally {
      endActivity("results");
    }
  }, []);

  // Existing privacy preference: no automatic internet access unless the user
  // enabled keep-data-fresh. A manual result check remains available regardless.
  useEffect(() => {
    if (refreshPolicy === "auto_refresh") void checkResults();
  }, [checkResults, refreshPolicy]);

  return (
    <div className="stack" style={{ ["--gap" as string]: "1.6rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Track record</h1>
        <p className="muted" style={{ maxWidth: "64ch" }}>
          Real sealed forecasts and what happened after the whistle — never backtests.
          Each row is an immutable seal; scoring appends a successor from a strictly
          newer data snapshot and can never edit the seal.{" "}
          <a href="#/lab/backtests"><b style={{ color: "var(--text)" }}>Backtest folds live under Backtests ›</b></a>
        </p>
      </header>

      {state.status === "loading" && (
        <>
          <Loading label="Loading the prediction ledger" />
          <BlockSkeleton lines={6} />
        </>
      )}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && (
        <Ledger data={state.data} settlement={settlement} onCheckResults={checkResults} />
      )}
    </div>
  );
}

function Ledger({
  data,
  settlement,
  onCheckResults,
}: {
  data: CalibrationSummary;
  settlement: SettlementState;
  onCheckResults: () => Promise<void>;
}) {
  const { counts } = data;
  const total = counts.sealed + counts.abstained;
  if (total === 0) {
    return (
      <EmptyState title="No sealed forecasts yet">
        The ledger fills only with genuine pre-kickoff seals. When an upcoming
        international is sealed, it appears here; after full time Golavo checks a
        newer trusted result snapshot and appends the scored outcome.
      </EmptyState>
    );
  }
  return (
    <>
      <section aria-label="Ledger counts" className="card card--pad">
        <div className="controls" style={{ flexWrap: "wrap", gap: ".5rem" }}>
          <span className="chip chip--sealed">{counts.sealed} sealed</span>
          <span className="chip chip--abstained">{counts.abstained} abstained</span>
          <span className="chip chip--scored">{counts.scored} scored</span>
          <span className="chip chip--voided">{counts.voided} voided</span>
          <span className="chip chip--neutral">{counts.pending} unresolved</span>
          {DATA_SOURCE === "live" && (
            <button
              type="button"
              className="btn btn--ghost"
              disabled={settlement.status === "checking"}
              onClick={() => { void onCheckResults(); }}
              style={{ marginLeft: ".35rem" }}
            >
              {settlement.status === "checking" ? "Checking results…" : "Check results now"}
            </button>
          )}
          <span className="muted small" style={{ marginLeft: "auto" }}>
            {data.generated_from}
          </span>
        </div>
      </section>

      <SettlementNotice state={settlement} />

      <RunningCalibration data={data} />

      <ChainsTable
        chains={data.chains}
        pendingReasons={
          settlement.status === "ready"
            ? new Map(
                settlement.report.still_pending.map((item) => [item.artifact_id, item.reason]),
              )
            : new Map()
        }
      />
    </>
  );
}

function SettlementNotice({ state }: { state: SettlementState }) {
  if (state.status === "idle" || state.status === "checking") return null;
  if (state.status === "error") {
    return (
      <div className="callout callout--warning" role="alert">
        <div>
          <div className="callout__title">Results could not be checked</div>
          <p className="small" style={{ margin: ".3rem 0 0" }}>{state.error.message}</p>
        </div>
      </div>
    );
  }
  const { report } = state;
  if (report.scored.length > 0) {
    return (
      <div className="callout callout--success" role="status">
        <div>
          <div className="callout__title">
            {report.scored.length === 1 ? "1 forecast settled" : `${report.scored.length} forecasts settled`}
          </div>
          <p className="small" style={{ margin: ".3rem 0 0" }}>
            {report.scored.map((item) => (
              `${item.home_team} ${item.home_goals}–${item.away_goals} ${item.away_team}`
            )).join(" · ")}
          </p>
        </div>
      </div>
    );
  }
  if (report.errors.length > 0) {
    return (
      <div className="callout callout--warning" role="status">
        <div>
          <div className="callout__title">Result check needs attention</div>
          <p className="small" style={{ margin: ".3rem 0 0" }}>
            {report.errors.map((error) => error.message).join(" · ")}
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="callout callout--info" role="status">
      <div>
        <div className="callout__title">
          {report.eligible > 0 ? "Results checked — publication pending" : "No results are due yet"}
        </div>
        <p className="small" style={{ margin: ".3rem 0 0" }}>
          {report.eligible > 0
            ? "The trusted sources have not published a final score for every finished fixture yet. Golavo will never guess one."
            : "There are no unscored forecasts more than three hours past kickoff."}
        </p>
      </div>
    </div>
  );
}

type ChainCategory = "scored" | "awaiting" | "voided" | "abstained";
const CATEGORY_LABELS: Record<ChainCategory, string> = {
  scored: "Scored",
  awaiting: "Unresolved",
  voided: "Voided",
  abstained: "Abstained",
};

/** One resolution bucket per chain. Terminal outcomes (scored/voided) win over
 *  an abstention flag; a still-pending abstained seal reads as "abstained". */
function chainCategory(chain: CalibrationChain): ChainCategory {
  if (chain.resolution.status === "scored") return "scored";
  if (chain.resolution.status === "voided") return "voided";
  if (chain.abstained) return "abstained";
  return "awaiting";
}

/** The sealed→scored chains table with client-side filters. The top count chips
 *  stay UNfiltered (they summarize the whole ledger); this table narrows to a
 *  resolution bucket and/or competition, and captions "showing n of m chains". */
function ChainsTable({
  chains,
  pendingReasons,
}: {
  chains: CalibrationChain[];
  pendingReasons: Map<string, SettlementPendingReason>;
}) {
  const [category, setCategory] = useState<ChainCategory | "all">("all");
  const [competition, setCompetition] = useState<string>("all");

  const categories = useMemo(() => {
    const present = new Set(chains.map(chainCategory));
    return (["scored", "awaiting", "voided", "abstained"] as ChainCategory[]).filter((c) => present.has(c));
  }, [chains]);
  const competitions = useMemo(
    () => Array.from(new Set(chains.map((c) => c.match.competition))).sort((a, b) => a.localeCompare(b)),
    [chains],
  );

  const filtered = useMemo(
    () =>
      chains.filter((chain) => {
        if (category !== "all" && chainCategory(chain) !== category) return false;
        if (competition !== "all" && chain.match.competition !== competition) return false;
        return true;
      }),
    [chains, category, competition],
  );

  return (
    <section className="stack" style={{ ["--gap" as string]: "1rem" }} aria-labelledby="chains-h">
      <div className="hgroup">
        <h2 id="chains-h" className="upper muted">Sealed → scored chains</h2>
        <div className="mv-filters" role="group" aria-label="Filter chains">
          <div className="mv-filter-chips" role="group" aria-label="Filter by resolution">
            <FilterChip label="All" active={category === "all"} onClick={() => setCategory("all")} />
            {categories.map((c) => (
              <FilterChip key={c} label={CATEGORY_LABELS[c]} active={category === c} onClick={() => setCategory(c)} />
            ))}
          </div>
          <label className="field mv-filter-field">
            Competition
            <select
              className="select"
              value={competition}
              onChange={(e) => setCompetition(e.target.value)}
            >
              <option value="all">All competitions</option>
              {competitions.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
        </div>
      </div>
      <p className="mv-filter-count small muted" role="status" aria-live="polite">
        Showing {filtered.length} of {chains.length} chains
      </p>
      <div className="card">
        <div className="table-wrap" style={{ border: "none", borderRadius: 0 }}>
          <table className="grid">
            <thead>
              <tr>
                <th scope="col">Fixture</th>
                <th scope="col">Match day</th>
                <th scope="col">Sealed</th>
                <th scope="col">Home / Draw / Away</th>
                <th scope="col">Outcome</th>
                <th scope="col" className="headline-col">
                  <abbr className="th-gloss" title={METRIC_GLOSS.logLoss}>Log loss</abbr>
                </th>
                <th scope="col"><abbr className="th-gloss" title={METRIC_GLOSS.brier}>Brier</abbr></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((chain) => (
                <ChainRow
                  key={chain.sealed_artifact_id}
                  chain={chain}
                  pendingReason={pendingReasons.get(chain.sealed_artifact_id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="small dim" style={{ maxWidth: "70ch" }}>
        Result checks use pinned, hashed CC0 source snapshots. When two trusted
        sources publish different scores, Golavo refuses to settle the row until the
        conflict is resolved. A voided row records a postponement or abandonment; it
        never fabricates a result.
      </p>
    </section>
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

function probsLabel(probs: Probs | null): string {
  if (!probs) return "abstained";
  return `${pct(probs.home)} / ${pct(probs.draw)} / ${pct(probs.away)}`;
}

function ChainRow({
  chain,
  pendingReason,
}: {
  chain: CalibrationChain;
  pendingReason?: SettlementPendingReason;
}) {
  const { match, resolution } = chain;
  return (
    <tr>
      <th scope="row" style={{ fontWeight: 550 }}>
        <a href={`#/forecast/${encodeURIComponent(chain.sealed_artifact_id)}`}>
          {match.home_team} v {match.away_team}
        </a>
        <div className="small dim">
          {match.competition} · {FAMILY_LABELS[chain.family]} · {HORIZON_LABELS[chain.horizon]}
        </div>
      </th>
      <td>{utcDate(match.kickoff_utc)}</td>
      <td title={utc(chain.sealed_at_utc)}>{utcDate(chain.sealed_at_utc)}</td>
      <td className="num">{probsLabel(chain.probs)}</td>
      <td><Resolution chain={chain} pendingReason={pendingReason} /></td>
      <td className="num headline-col">
        {resolution.metrics ? num(resolution.metrics.log_loss, 3) : "—"}
      </td>
      <td className="num">{resolution.metrics ? num(resolution.metrics.brier, 3) : "—"}</td>
    </tr>
  );
}

export function pendingResolutionLabel(
  chain: CalibrationChain,
  nowMs = Date.now(),
  reason?: SettlementPendingReason,
): string {
  if (reason === "result_not_published") return "result not published";
  if (reason === "source_conflict") return "source conflict";
  if (reason === "scoring_refused") return "review needed";
  const kickoff = Date.parse(chain.match.kickoff_utc);
  if (Number.isFinite(kickoff) && nowMs >= kickoff + 3 * 60 * 60 * 1000)
    return "result check needed";
  if (Number.isFinite(kickoff) && nowMs >= kickoff) return "match in progress";
  return "awaiting full time";
}

function Resolution({
  chain,
  pendingReason,
}: {
  chain: CalibrationChain;
  pendingReason?: SettlementPendingReason;
}) {
  const { resolution } = chain;
  if (resolution.status === "scored" && resolution.actual) {
    return (
      <span className="chip chip--scored" title={`scored ${utc(resolution.resolved_at_utc ?? "")}`}>
        {resolution.actual.home_goals}–{resolution.actual.away_goals} ({resolution.actual.outcome})
      </span>
    );
  }
  if (resolution.status === "voided") {
    return (
      <span className="chip chip--voided" title={resolution.void_reason ?? undefined}>
        voided
      </span>
    );
  }
  return <span className="chip chip--neutral">{pendingResolutionLabel(chain, Date.now(), pendingReason)}</span>;
}

function RunningCalibration({ data }: { data: CalibrationSummary }) {
  const { running } = data;
  const populated = data.reliability_bins.some((b) => b.count > 0 && b.accuracy != null);
  return (
    <section className="stack" style={{ ["--gap" as string]: "1rem" }} aria-labelledby="running-h">
      <h2 id="running-h" className="upper muted">Running calibration</h2>
      {running ? (
        <div className="card card--pad stack" style={{ ["--gap" as string]: "1rem" }}>
          <div className="controls" style={{ flexWrap: "wrap", gap: "1.5rem" }}>
            <Stat label="Scored seals" value={String(running.n_scored)} />
            <Stat label="Running log loss" value={num(running.log_loss, 3)} headline />
            <Stat label="Running Brier" value={num(running.brier, 3)} />
            <Stat label="Mean chance on the result" value={pct(running.prob_assigned_to_outcome)} />
          </div>
          <p className="small dim" style={{ margin: 0 }}>
            Log loss near <span className="num">1.10</span> is the guess-nothing baseline; lower is better.
            Both figures update as each sealed forecast is scored.
          </p>
          {populated && (
            <div className="reliability">
              <ReliabilityDiagram
                bins={data.reliability_bins}
                caption={`Sealed forecasts · ${running.n_scored} scored`}
              />
            </div>
          )}
        </div>
      ) : (
        <div className="card card--pad">
          <EmptyState title="No scored seals yet">
            Running log loss and the reliability diagram appear after the first sealed
            forecast is scored from a newer snapshot.
          </EmptyState>
        </div>
      )}
    </section>
  );
}

function Stat({ label, value, headline }: { label: string; value: string; headline?: boolean }) {
  return (
    <div className="stack" style={{ ["--gap" as string]: ".15rem" }}>
      <span className="small upper muted">{label}</span>
      <span
        className="num"
        style={{
          fontSize: "1.35rem",
          fontWeight: 620,
          color: headline ? "var(--gold)" : "var(--text)",
        }}
      >
        {value}
      </span>
    </div>
  );
}
