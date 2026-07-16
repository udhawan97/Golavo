import { useEffect, useMemo, useRef, useState } from "react";
import { useAiModels, useAiProvider } from "../lib/ai";
import {
  cancelResearchRun,
  createResearchRun,
  discoverResearchSources,
  fetchResearchCapabilities,
  fetchResearchRun,
  fetchResearchRuns,
  queueResearchCandidate,
} from "../lib/research";
import type {
  DiscoveryItem,
  ResearchCandidate,
  ResearchCapabilities,
  ResearchRun,
} from "../lib/research";
import { handleExternalLinkClick } from "../lib/external-links";

const terminal = new Set(["candidates_ready", "partial", "cancelled", "offline", "failed"]);
export const MAX_RESEARCH_PAGES = 4;
export const RESEARCH_POLL_FAILURE_LIMIT = 3;

export function claimResearchCreation(lock: { current: boolean }): boolean {
  if (lock.current) return false;
  lock.current = true;
  return true;
}

export function nextResearchPollFailure(consecutiveFailures: number) {
  const count = consecutiveFailures + 1;
  return { count, paused: count >= RESEARCH_POLL_FAILURE_LIMIT };
}

export function researchSelectionState(selectedCount: number, selected: boolean) {
  const atLimit = selectedCount >= MAX_RESEARCH_PAGES;
  return {
    disabled: atLimit && !selected,
    message: `${selectedCount} of ${MAX_RESEARCH_PAGES} pages selected.${atLimit ? " Selection limit reached; remove one to choose another." : ""}`,
  };
}

export function MatchResearch({
  matchId,
  home,
  away,
  competition,
}: {
  matchId: string;
  home: string;
  away: string;
  competition: string;
}) {
  const [capabilities, setCapabilities] = useState<ResearchCapabilities | null>(null);
  const [preflight, setPreflight] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [discoveryComplete, setDiscoveryComplete] = useState(false);
  const [items, setItems] = useState<DiscoveryItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [run, setRun] = useState<ResearchRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [pollingIssue, setPollingIssue] = useState<string | null>(null);
  const [queued, setQueued] = useState<Set<string>>(new Set());
  const [queueing, setQueueing] = useState<Set<string>>(new Set());
  const [useLocalAi, setUseLocalAi] = useState(false);
  const discoveryAbort = useRef<AbortController | null>(null);
  const createAbort = useRef<AbortController | null>(null);
  const creatingRef = useRef(false);
  const queueingRef = useRef<Set<string>>(new Set());
  const [provider] = useAiProvider();
  const { fastModel } = useAiModels();
  const localProvider = provider === "ollama" || provider === "llama_server" ? provider : null;
  const query = useMemo(() => `${home} ${away} ${competition}`.trim(), [home, away, competition]);

  useEffect(() => {
    let live = true;
    fetchResearchCapabilities().then(
      (value) => {
        if (!live) return;
        setCapabilities(value);
        if (value.enabled) {
          fetchResearchRuns(matchId, 1).then(
            (runs) => { if (live && runs[0]) setRun(runs[0]); },
            () => { /* a fresh run remains available */ },
          );
        }
      },
      () => { if (live) setCapabilities(null); },
    );
    return () => {
      live = false;
      discoveryAbort.current?.abort();
      createAbort.current?.abort();
      createAbort.current = null;
      creatingRef.current = false;
    };
  }, [matchId]);

  useEffect(() => {
    if (!run || terminal.has(run.state) || pollingIssue) return;
    let live = true;
    let timer: number | undefined;
    let requestController: AbortController | null = null;
    let consecutiveFailures = 0;
    const schedule = () => { timer = window.setTimeout(poll, 800); };
    const poll = () => {
      requestController = new AbortController();
      fetchResearchRun(run.run_id, requestController.signal).then(
        (value) => {
          if (!live) return;
          consecutiveFailures = 0;
          setRun(value);
          if (!terminal.has(value.state)) schedule();
        },
        (cause) => {
          if (!live || (cause instanceof DOMException && cause.name === "AbortError")) return;
          const next = nextResearchPollFailure(consecutiveFailures);
          consecutiveFailures = next.count;
          if (next.paused) {
            setPollingIssue(
              "Golavo lost contact with the local research worker and stopped checking automatically. The run remains stored locally; its status is not being guessed.",
            );
          } else {
            schedule();
          }
        },
      );
    };
    schedule();
    return () => {
      live = false;
      if (timer !== undefined) window.clearTimeout(timer);
      requestController?.abort();
    };
  }, [run?.run_id, run?.state, pollingIssue]);

  const fail = (reason: unknown) => {
    if (reason instanceof DOMException && reason.name === "AbortError") return;
    setError(reason instanceof Error ? reason.message : "Match research could not continue.");
  };

  const reset = () => {
    discoveryAbort.current?.abort();
    createAbort.current?.abort();
    createAbort.current = null;
    creatingRef.current = false;
    setPreflight(false);
    setDiscovering(false);
    setDiscoveryComplete(false);
    setItems([]);
    setSelected(new Set());
    setRun(null);
    setError(null);
    setCreating(false);
    setPollingIssue(null);
    setQueued(new Set());
    queueingRef.current.clear();
    setQueueing(new Set());
  };

  if (!capabilities) return null;
  if (!capabilities.enabled) {
    return (
      <section className="panel research-panel" aria-labelledby="match-research-title">
        <div className="panel__head"><h2 id="match-research-title">Source desk</h2></div>
        <div className="panel__body">
          <p>Optional match research is off. Enable it in <a href="#/settings">Settings</a>; enabling alone makes no network request.</p>
        </div>
      </section>
    );
  }

  const candidates = run?.candidates ?? [];
  return (
    <section className="panel research-panel" aria-labelledby="match-research-title">
      <div className="panel__head">
        <div>
          <span className="upper">Optional · untrusted candidates</span>
          <h2 id="match-research-title">Source desk</h2>
        </div>
      </div>
      <div className="panel__body stack">
        {!preflight && !run && (
          <>
            <p>Discover permitted pages for this match. Search results never become facts, and nothing is fetched until you review the preflight.</p>
            <button type="button" className="btn btn--primary" onClick={() => setPreflight(true)}>Research this match</button>
          </>
        )}

        {preflight && items.length === 0 && !discoveryComplete && !run && (
          <div className="research-preflight">
            <h3>Before Golavo connects</h3>
            <ul>
              <li>Query: <b>{query}</b></li>
              <li>Discovery: documented Wikipedia and Wikidata APIs only</li>
              <li>At most 4 selected pages, 512 KiB each, foreground only</li>
              <li>Captured text stays untrusted and cannot change probabilities or settlement</li>
            </ul>
            <div className="row">
              <button
                type="button"
                className="btn btn--primary"
                disabled={discovering}
                onClick={() => {
                  discoveryAbort.current?.abort();
                  const controller = new AbortController();
                  discoveryAbort.current = controller;
                  setDiscovering(true); setDiscoveryComplete(false); setError(null);
                  discoverResearchSources(query, controller.signal).then((found) => {
                    if (controller.signal.aborted) return;
                    setItems(found);
                    setSelected(new Set());
                    setDiscoveryComplete(true);
                  }, fail).finally(() => {
                    if (!controller.signal.aborted) setDiscovering(false);
                  });
                }}
              >{discovering ? "Discovering…" : "Discover permitted sources"}</button>
              <button type="button" className="btn btn--quiet" onClick={reset}>Cancel</button>
            </div>
          </div>
        )}

        {preflight && discoveryComplete && items.length === 0 && !run && (
          <div role="status" className="stack">
            <p>No permitted Wikipedia or Wikidata pages matched this search. Nothing was captured.</p>
            <div className="row">
              <button type="button" className="btn btn--primary" onClick={() => setDiscoveryComplete(false)}>Try again</button>
              <button type="button" className="btn btn--quiet" onClick={reset}>Close</button>
            </div>
          </div>
        )}

        {items.length > 0 && !run && (
          <div className="stack">
            <h3>Select pages to capture</h3>
            <p
              id="research-selection-status"
              className="small dim"
              role="status"
              aria-live="polite"
            >
              {researchSelectionState(selected.size, false).message}
            </p>
            <div className="research-results">
              {items.map((item) => {
                const isSelected = selected.has(item.url);
                const selectionState = researchSelectionState(selected.size, isSelected);
                return (
                  <label key={item.url} className="research-result">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      disabled={selectionState.disabled}
                      aria-describedby="research-selection-status"
                      onChange={(event) => setSelected((current) => {
                        const next = new Set(current);
                        if (event.target.checked && next.size < MAX_RESEARCH_PAGES) next.add(item.url);
                        else next.delete(item.url);
                        return next;
                      })}
                    />
                    <span>
                      <b>{item.title}</b>
                      {item.description && <small>{item.description}</small>}
                      <small>{item.provider} · {item.license_namespace} · {new URL(item.url).host}</small>
                    </span>
                  </label>
                );
              })}
            </div>
            {localProvider && (
              <label className="research-local-ai">
                <input type="checkbox" checked={useLocalAi} onChange={(event) => setUseLocalAi(event.target.checked)} />
                If deterministic parsing finds nothing, ask {localProvider === "ollama" ? "Ollama" : "llama.cpp"} ({fastModel || "configured local model"}) to extract quoted candidates locally
              </label>
            )}
            <button
              type="button"
              className="btn btn--primary"
              disabled={creating || selected.size === 0 || !capabilities.current_index_fingerprint}
              aria-busy={creating}
              onClick={() => {
                if (!claimResearchCreation(creatingRef)) return;
                setError(null);
                setPollingIssue(null);
                setCreating(true);
                const controller = new AbortController();
                createAbort.current = controller;
                createResearchRun({
                  matchId,
                  indexFingerprint: capabilities.current_index_fingerprint ?? "",
                  selectedUrls: [...selected],
                  localAi: useLocalAi && localProvider
                    ? { provider: localProvider, ...(fastModel ? { model: fastModel } : {}) }
                    : undefined,
                }, controller.signal).then(setRun, fail).finally(() => {
                  if (createAbort.current !== controller) return;
                  createAbort.current = null;
                  creatingRef.current = false;
                  if (!controller.signal.aborted) setCreating(false);
                });
              }}
            >{creating ? "Starting research…" : "Capture selected sources"}</button>
          </div>
        )}

        {run && !terminal.has(run.state) && (
          <div className="research-progress">
            <div role="status" aria-live="polite">
              <b>{pollingIssue ? "Research status unavailable" : "Researching selected sources…"}</b>
              <span>
                {pollingIssue
                  ? "Automatic status checks are paused."
                  : `${run.counts.captured} of ${run.counts.selected} captured`}
              </span>
            </div>
            {pollingIssue && (
              <button type="button" className="btn btn--quiet" onClick={() => setPollingIssue(null)}>
                Retry status check
              </button>
            )}
            <button
              type="button"
              className="btn btn--quiet"
              onClick={() => void cancelResearchRun(run.run_id).then(({ run: value }) => {
                setPollingIssue(null);
                setRun(value);
              }, fail)}
            >
              Cancel
            </button>
          </div>
        )}
        {pollingIssue && <p role="alert" className="small dim">{pollingIssue}</p>}

        {run && terminal.has(run.state) && (
          <div className="stack">
            <p className="small dim" role="status" aria-live="polite">
              Run {run.state.replaceAll("_", " ")} · {run.counts.captured} captured · {run.counts.failed} failed · {run.counts.candidates} candidates
            </p>
            {run.reason_codes.length > 0 && (
              <p className="small dim">Reason: {run.reason_codes.map(reasonLabel).join(" · ")}</p>
            )}
            {candidates.length === 0 && (
              <p>No reviewable alias or venue was stated in the selected evidence. Golavo did not fill anything in.</p>
            )}
            {candidates.map((candidate) => (
              <CandidateCard
                key={candidate.candidate_id}
                candidate={candidate}
                queued={queued.has(candidate.candidate_id) || Boolean(candidate.queued_proposal_id)}
                pending={queueing.has(candidate.candidate_id)}
                onQueue={() => {
                  if (queueingRef.current.has(candidate.candidate_id)) return;
                  queueingRef.current.add(candidate.candidate_id);
                  setQueueing((current) => new Set(current).add(candidate.candidate_id));
                  setError(null);
                  queueResearchCandidate(candidate).then(() => {
                    setQueued((current) => new Set(current).add(candidate.candidate_id));
                  }, fail).finally(() => {
                    queueingRef.current.delete(candidate.candidate_id);
                    setQueueing((current) => {
                      const next = new Set(current);
                      next.delete(candidate.candidate_id);
                      return next;
                    });
                  });
                }}
              />
            ))}
            <button type="button" className="btn btn--quiet" onClick={reset}>Research again</button>
          </div>
        )}
        {error && <p role="alert" className="small dim">{error}</p>}
      </div>
    </section>
  );
}

export function CandidateCard({ candidate, queued, pending, onQueue }: { candidate: ResearchCandidate; queued: boolean; pending: boolean; onQueue: () => void }) {
  const value = candidate.correction_type === "team_alias"
    ? String(candidate.proposed.alias ?? "")
    : String(candidate.proposed.venue_name ?? "");
  return (
    <article className="research-candidate">
      <header>
        <div><span className="upper">{candidate.correction_type.replace("_", " ")}</span><h3>{value}</h3></div>
        <span className="chip">{candidate.extractor.kind === "local_ai" ? "Local AI candidate" : "Deterministic parser"}</span>
      </header>
      <details>
        <summary>View exact captured quote</summary>
        <blockquote>{candidate.evidence.exact_quote}</blockquote>
      </details>
      <dl>
        <div><dt>Source</dt><dd><a href={candidate.source.canonical_url} onClick={handleExternalLinkClick}>{candidate.source.attribution}</a></dd></div>
        <div><dt>Retrieved</dt><dd>{new Date(candidate.source.retrieved_at_utc).toLocaleString()}</dd></div>
        <div><dt>License</dt><dd><a href={candidate.source.license_url} onClick={handleExternalLinkClick}>{candidate.source.license}</a> · {candidate.source.modifications}</dd></div>
        <div><dt>Content hash</dt><dd><code>{candidate.evidence.raw_sha256.slice(0, 16)}…</code></dd></div>
      </dl>
      {queued ? (
        <p className="small"><b>Added as a correction draft.</b> It still requires Phase 6 validation and review. <a href="#/corrections">Open queue ›</a></p>
      ) : (
        <button type="button" className="btn btn--primary" disabled={pending} aria-busy={pending} onClick={onQueue}>
          {pending ? "Adding to correction queue…" : "Add to correction queue"}
        </button>
      )}
    </article>
  );
}

function reasonLabel(code: string): string {
  const labels: Record<string, string> = {
    app_interrupted: "Golavo closed before the run completed",
    cancelled: "cancelled by you",
    dns_failed: "offline or DNS unavailable",
    network_failed: "source could not be reached",
    source_busy: "source asked Golavo to slow down",
    response_too_large: "source response exceeded the safety cap",
  };
  return labels[code] ?? code.replaceAll("_", " ");
}
