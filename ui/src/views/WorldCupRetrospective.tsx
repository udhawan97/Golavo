/**
 * World Cup 2026 retrospective — two layers that must never blur.
 *
 * STORY ("what the app would have said before each match"): every row is refit
 * at its OWN kickoff-1s cutoff, the same conservative boundary the real seal
 * uses. TRUST ("did these models have skill?"): the WC2026 evaluation fold,
 * trained ONCE at a single pre-tournament cutoff and never shown a match inside
 * the window. Different cutoffs, different questions — so a trust metric never
 * describes a row, and the two are never averaged.
 *
 * Neither layer is a record. v1 ships no sealed-pick layer, which RAISES the
 * labelling burden rather than lowering it: with a real seal beside them the
 * distinction would be self-evident, but alone on the page a backtest can be
 * misread as a track record. Hence the disclosure at the top, before any number.
 */
import { useEffect, useRef, useState } from "react";
import { ChevronRight } from "../components/icons";
import { ErrorState } from "../components/states";
import {
  cancelWorldCupRetrospective,
  fetchRetrospectiveJob,
  startWorldCupRetrospective,
  type RetrospectiveJob,
} from "../lib/api";
import { newJobId } from "../lib/aiProgress";
import type {
  ModelFamily,
  RetrospectiveRow,
  SnapshotAgreement,
  TournamentRetrospective,
  TrustFold,
  TrustFoldModel,
} from "../lib/contract";
import { FAMILY_LABELS } from "../lib/contract";
import { num, pct, shortHash, utcDate } from "../lib/format";

/**
 * The family the trust table refuses to list as a voice.
 *
 * `trust.models` comes from evaluation.py, which iterates all FIVE families.
 * The story layer's `families` deliberately carries four — it drops
 * bivariate_poisson because the family is numerically identical to
 * poisson_independent on every recorded fold, so offering both implies two
 * independent opinions where there is one. That reasoning is about the models,
 * not about one table, so it binds here too: rendering trust unfiltered would
 * list a voice the story table does not, and the two tables would visibly
 * contradict each other.
 */
const DUPLICATE_VOICE: ModelFamily = "bivariate_poisson";

/** Split a fold's models into the voices we show and the duplicates we drop.
 *  `omitted` is what lets the page tell a reader where a family went instead of
 *  leaving a silent gap. */
export function trustVoices(fold: TrustFold): {
  shown: TrustFoldModel[];
  omitted: ModelFamily[];
} {
  const shown: TrustFoldModel[] = [];
  const omitted: ModelFamily[] = [];
  for (const model of fold.models) {
    if (model.family === DUPLICATE_VOICE) omitted.push(model.family);
    else shown.push(model);
  }
  return { shown, omitted };
}

/** Contract-permissive: only family/log_loss are guaranteed, so an unknown
 *  future family shows its raw id rather than "undefined". */
function familyLabel(family: ModelFamily): string {
  return FAMILY_LABELS[family] ?? family;
}

/** A metric the fold may not carry. Never rendered as a zero. */
const metricCell = (value: number | undefined) => (value === undefined ? "—" : num(value, 3));

/** The server's snapshot check, stated as exactly what it is.
 *
 *  "verified" is the only wording that claims the two layers share a snapshot,
 *  and only a digest comparison the server actually ran can produce it — an
 *  unverified check says so rather than defaulting either way. */
function agreementNote(agreement: SnapshotAgreement): string {
  if (agreement.status === "verified")
    return `both layers verified on pack ${shortHash(agreement.pack_sha256)}`;
  if (agreement.status === "mismatched")
    return `layers on DIFFERENT packs: index ${shortHash(agreement.index_pack_sha256)}, fold ${shortHash(agreement.pack_sha256)}`;
  return `one-snapshot check could not run (${agreement.cause})`;
}

function StoryRow({ row, family }: { row: RetrospectiveRow; family: string }) {
  const call = row.families[family];
  const proxyRows = row.training_same_day_proxy_rows;
  return (
    <tr>
      <th scope="row" style={{ fontWeight: 550 }}>
        {row.home_team} {row.home_score}–{row.away_score} {row.away_team}
        {row.kickoff_precision === "day" && (
          <span className="small dim" style={{ display: "block", fontWeight: 400 }}>
            Kickoff is a date proxy, so same-day order is not provable.
          </span>
        )}
        {proxyRows > 0 && (
          // kickoff_precision "exact" says nothing about the TRAINING frame, so
          // a reader seeing "exact" would wrongly assume nothing later leaked in.
          <span className="small dim" style={{ display: "block", fontWeight: 400 }}>
            Trained on {proxyRows} same-day date-proxy result{proxyRows === 1 ? "" : "s"} that
            cannot be shown to have been played first.
          </span>
        )}
      </th>
      <td className="num">
        {call ? `${pct(call.probs.home)} / ${pct(call.probs.draw)} / ${pct(call.probs.away)}` : "—"}
      </td>
      <td className="num">{num(row.log_loss, 3)}</td>
    </tr>
  );
}

function TrustPanel({ trust }: { trust: NonNullable<TournamentRetrospective["trust"]> }) {
  if (trust.status === "unavailable") {
    // A typed state with the server's own reason — never an empty table, which
    // a reader could read as "measured, and it is zero".
    return (
      <div className="callout callout--info" role="status">
        <div>
          <div className="callout__title">Model skill could not be measured</div>
          <p>{trust.reason}</p>
        </div>
      </div>
    );
  }
  const { shown, omitted } = trustVoices(trust);
  const best = shown.length > 0 ? Math.min(...shown.map((m) => m.log_loss)) : null;
  return (
    <>
      <div className="table-wrap">
        <table className="grid">
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col" className="headline-col">Log loss</th>
              <th scope="col">Brier</th>
              <th scope="col">ECE</th>
              <th scope="col">RPS</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((model) => (
              <tr key={model.family} className={model.log_loss === best ? "is-leader" : undefined}>
                <th scope="row" style={{ fontWeight: 550 }}>{familyLabel(model.family)}</th>
                <td className={`num headline-col${model.log_loss === best ? " cell-best" : ""}`}>
                  {num(model.log_loss, 3)}
                </td>
                <td className="num">{metricCell(model.brier)}</td>
                <td className="num">{metricCell(model.ece)}</td>
                <td className="num">{metricCell(model.rps)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small dim measure" style={{ margin: ".65rem 0 0" }}>
        No skill interval is shown: a single fold has nothing to bootstrap one against. Compare each
        voice with the {familyLabel("climatological")} baseline instead — a voice earns its keep only
        by beating it.
      </p>
      {omitted.length > 0 && (
        <p className="small dim measure" style={{ margin: ".4rem 0 0" }}>
          {familyLabel(DUPLICATE_VOICE)} is not listed. It is numerically identical to{" "}
          {familyLabel("poisson_independent")} on every recorded fold, so showing both would imply
          two independent opinions where there is one — the same reason the matches above are
          backtested with four voices, not five.
        </p>
      )}
      {/* Metadata only. A disagreement with the story's count is a broken
          cross-layer guarantee, so it is raised as a callout beside the page's
          other broken guarantees — never trailed here in dim small print. */}
      <p className="small dim measure" style={{ margin: ".4rem 0 0" }}>
        Fold {trust.fold_id} · {trust.n_matches} matches
        {trust.training_cutoff_utc ? ` · trained once at ${utcDate(trust.training_cutoff_utc)}` : ""}
      </p>
    </>
  );
}

export function WorldCupRetrospectiveBody({ data }: { data: TournamentRetrospective }) {
  if (data.status !== "available") {
    // Covers the mid-compute index change too: the server returns that as an
    // unavailable envelope whose reason carries the pause, verbatim.
    return (
      <div className="callout callout--info" role="status">
        <div>
          <div className="callout__title">Retrospective unavailable</div>
          <p>{data.reason}</p>
        </div>
      </div>
    );
  }

  const rankingFamily = data.ranking_family ?? "dixon_coles";
  const exposed = data.exposure?.rows_with_same_day_proxies ?? 0;
  const scored = data.coverage?.scored ?? data.biggest_surprises.length;
  const agreement = data.provenance?.snapshot_agreement;
  // Only an available fold carries a count to reconcile against. An unavailable
  // one already says why it has no number, and must not be read as zero.
  const fold = data.trust?.status === "available" ? data.trust : null;

  return (
    <>
      <div className="callout callout--info" role="status">
        <div>
          <div className="callout__title">Every number here is a backtest</div>
          <p>{data.label}</p>
          <p>
            Nothing on this page was called in advance. Golavo sealed no forecast for these matches
            before they kicked off — every number below is reconstructed now, by refitting the models
            on only what was known at the time. There are no sealed picks here to sit beside them and
            make the difference obvious, so the page has to say it plainly: read this as a backtest,
            never as a track record.
          </p>
        </div>
      </div>

      {/* Both of these outrank "the tournament isn't over yet" below: a page
          whose two layers describe different data is a broken guarantee, not a
          pending one. */}
      {agreement?.status === "mismatched" && (
        <div className="callout callout--warning" role="status">
          <div>
            <div className="callout__title">The two layers read different snapshots</div>
            {/* The server owns this comparison — it holds the digests. */}
            <p>{agreement.reason}</p>
            <p>
              The matches and the skill fold below therefore describe different datasets, so
              neither is a check on the other.
            </p>
          </div>
        </div>
      )}

      {fold && scored !== fold.n_matches && (
        <div className="callout callout--warning" role="status">
          <div>
            <div className="callout__title">The two layers’ match counts disagree</div>
            <p>
              {scored} matches were backtested below, but the {fold.fold_id} fold scored{" "}
              {fold.n_matches}. Both describe the 2026 World Cup, so these counts should agree.
            </p>
            <p>
              Two things can cause this, and the counts alone cannot tell them apart: the layers
              may have read different snapshots, or they may select the tournament window’s edges
              differently — the backtest selects on exact kickoff time, the fold on calendar date,
              so a match dated inside the window but kicking off outside it is scored by one and
              dropped by the other. Read the two layers as possibly describing different sets of
              matches.
            </p>
          </div>
        </div>
      )}

      {data.coverage?.status === "partial" && (
        <div className="callout callout--warning" role="status">
          <div>
            <div className="callout__title">Tournament still in progress</div>
            <p>{data.coverage.note}</p>
          </div>
        </div>
      )}

      {data.exposure && exposed > 0 && (
        <div className="callout callout--warning" role="status">
          <div>
            <div className="callout__title">Same-day date proxies in the training data</div>
            <p>
              {exposed} of {scored} backtested matches trained on at least one.
            </p>
            {/* The server owns this explanation. Never paraphrase it here. */}
            <p>{data.exposure.note}</p>
          </div>
        </div>
      )}

      <section className="stack" style={{ ["--gap" as string]: ".7rem" }} aria-labelledby="wc-story-h">
        <div>
          <h2 id="wc-story-h">What the app would have said before each match</h2>
          <p className="small dim measure" style={{ margin: ".25rem 0 0" }}>
            Each match is refit on results from before its own kickoff — the same cutoff the app’s
            real seal uses — then scored against what actually happened. Ranked by log loss on{" "}
            {familyLabel(rankingFamily)}, the family the app would have sealed with; the biggest
            surprise first. Higher log loss means the result was more of a shock to the model.
          </p>
        </div>
        <div className="table-wrap">
          <table className="grid">
            <thead>
              <tr>
                <th scope="col">Match</th>
                <th scope="col">Pre-kickoff call (H/D/A)</th>
                <th scope="col" className="headline-col">Log loss</th>
              </tr>
            </thead>
            <tbody>
              {data.biggest_surprises.map((row) => (
                <StoryRow key={row.match_id} row={row} family={rankingFamily} />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {data.trust && (
        <section className="stack" style={{ ["--gap" as string]: ".7rem" }} aria-labelledby="wc-trust-h">
          <div>
            <h2 id="wc-trust-h">Did these models have skill?</h2>
            <p className="small dim measure" style={{ margin: ".25rem 0 0" }}>
              A different question, on a different cutoff. This fold is trained once, before the
              tournament starts, and never sees a match inside it. These are whole-tournament
              numbers: not an average of the matches above, and they describe no single one of them.
              This is a backtest too — no forecast here was published in advance either.
            </p>
          </div>
          <TrustPanel trust={data.trust} />
        </section>
      )}

      <details className="outlook-method">
        <summary>How this page is built</summary>
        <p>
          Two layers, two different information boundaries — and one snapshot, checked rather than
          assumed. The matches replay the app’s own kickoff−1s cutoff, one fit per match. The skill
          fold trains once before the tournament and scores the whole window. The two are read from
          different files, so the server compares their snapshot digests and reports the verdict
          below rather than taking it on trust. Nothing on this page is written to the forecast
          ledger, and nothing was scored as a seal.
        </p>
        <p className="small dim">
          {data.tournament_name} · window {data.window_start ?? "unknown"} to{" "}
          {data.window_end ?? "unknown"} · {scored} backtested
          {data.coverage?.pending ? `, ${data.coverage.pending} not yet played` : ""} ·{" "}
          {(data.families ?? []).map(familyLabel).join(", ") || "families unstated"} · ranked by{" "}
          {data.ranking_metric ?? "log_loss"}
          {data.provenance?.index_sha256 ? ` · index ${shortHash(data.provenance.index_sha256)}` : ""}
          {data.provenance?.pack ? ` · pack ${data.provenance.pack}` : ""}
          {agreement ? ` · ${agreementNote(agreement)}` : ""}
        </p>
      </details>
    </>
  );
}

/** Thin fetch-and-branch wrapper: the ~6-minute backtest runs in its own job
 *  lane, so progress is real per-match counts and cancellation is always
 *  offered. All rendering lives in the pure body above. */
export function WorldCupRetrospective() {
  const [job, setJob] = useState<RetrospectiveJob | null>(null);
  const [data, setData] = useState<TournamentRetrospective | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [active, setActive] = useState<{ jobId: string } | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    // React Strict Mode mounts, cleans up, then remounts effects in dev. Reset
    // the flag on every mount so an in-flight poll is not discarded forever.
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!active) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const next = await fetchRetrospectiveJob(active.jobId);
        if (stopped || !mounted.current) return;
        setJob(next);
        if (next.state === "running") {
          timer = setTimeout(poll, 1200);
          return;
        }
        if (next.state === "done" && next.result) setData(next.result);
        else if (next.state === "cancelled") setNotice("Backtest cancelled. Nothing was saved.");
        else if (next.state === "failed") setError(new Error(next.error || "The backtest failed."));
        else setError(new Error("The backtest finished without a result."));
        setActive(null);
      } catch (err) {
        if (!stopped && mounted.current) {
          setError(err instanceof Error ? err : new Error("Progress was lost."));
          setActive(null);
        }
      }
    };
    void poll();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [active]);

  const start = async () => {
    setError(null);
    setNotice(null);
    setData(null);
    setJob(null);
    try {
      const jobId = newJobId().replace(/^cl-/, "rt-");
      const started = await startWorldCupRetrospective(jobId);
      setActive({ jobId: started });
    } catch (err) {
      setError(err instanceof Error ? err : new Error("The backtest could not start."));
    }
  };

  const cancel = async () => {
    if (!active) return;
    try {
      await cancelWorldCupRetrospective(active.jobId);
      setNotice("Cancelling…");
    } catch (err) {
      setError(err instanceof Error ? err : new Error("The backtest could not be cancelled."));
    }
  };

  const completed = job?.counts?.completed ?? 0;
  const total = job?.counts?.total ?? 0;
  // Never fabricate a percentage before the total is known.
  const percent = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : null;

  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/lab">Model Lab</a>
        <ChevronRight size={14} />
        <span aria-current="page">World Cup 2026</span>
      </nav>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>World Cup 2026 retrospective</h1>
        <p className="measure dim" style={{ margin: 0 }}>
          Every played match of the tournament, backtested at its own pre-kickoff cutoff — and, kept
          deliberately separate, whether the models had any skill over the window at all.
        </p>
      </header>

      {!data && !active && (
        <div className="stack" style={{ ["--gap" as string]: ".5rem" }}>
          <div>
            <button type="button" className="btn btn--primary" onClick={() => void start()}>
              Run the backtest
            </button>
          </div>
          <p className="small dim measure" style={{ margin: 0 }}>
            Refits the models once per match, at that match’s own cutoff. It takes several minutes
            the first time and is kept in memory afterwards. You can stop it at any point.
          </p>
        </div>
      )}

      {active && (
        <div className="ollama-download" aria-live="polite">
          <div className="ollama-download__label">
            <span>{job?.detail || "Starting the backtest…"}</span>
            <span>{percent === null ? "Preparing…" : `${percent}%`}</span>
          </div>
          <progress max={total || 1} value={total ? completed : undefined} />
          <div className="ollama-download__meta">
            <span>
              {total > 0 ? `${completed} of ${total} matches backtested` : "Counting the matches to replay"}
            </span>
            <button type="button" className="btn btn--ghost" onClick={() => void cancel()}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {notice && <p className="small muted" role="status">{notice}</p>}
      {error && <ErrorState error={error} onRetry={() => void start()} />}
      {data && <WorldCupRetrospectiveBody data={data} />}
    </div>
  );
}
