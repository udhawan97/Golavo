import { useEffect, useMemo, useState, type FormEvent } from "react";
import { BlockSkeleton, EmptyState } from "../components/states";
import { fetchMatch } from "../lib/api";
import { useCorrections } from "../lib/correction-context";
import {
  acceptLocalCorrection,
  attachCorrectionEvidence,
  createCorrection,
  exportCorrection,
  fetchCorrection,
  markCorrectionSubmitted,
  redactCorrectionEvidence,
  saveCorrectionExport,
  validateCorrection,
  type CorrectionProposal,
  type CorrectionSource,
  type CorrectionType,
} from "../lib/corrections";
import type { MatchDetailResponse } from "../lib/contract";
import { openExternalUrl } from "../lib/external-links";

const TYPE_LABELS: Record<CorrectionType, string> = {
  missing_fixture: "Missing fixture",
  kickoff_time: "Kickoff time",
  team_alias: "Team alias",
  venue: "Venue",
  final_score: "Final score",
};

const STATE_LABELS: Record<string, string> = {
  draft: "Draft",
  evidence_attached: "Needs validation",
  validated_candidate: "Validated candidate",
  conflict: "Conflict — closed",
  accepted_local: "Local annotation",
  exported: "Exported",
  submitted: "Marked submitted",
  withdrawn: "Withdrawn",
  superseded: "Superseded",
};

function QueueCard({
  proposal,
  currentIndexFingerprint,
}: {
  proposal: CorrectionProposal;
  currentIndexFingerprint?: string | null;
}) {
  const proposed = proposal.proposed;
  const needsRevalidation =
    proposal.local_visibility === "local_annotation" &&
    proposal.target.index_fingerprint !== currentIndexFingerprint;
  const title =
    proposal.correction_type === "missing_fixture"
      ? `${String(proposed.home_team ?? "?")} v ${String(proposed.away_team ?? "?")}`
      : TYPE_LABELS[proposal.correction_type];
  return (
    <article className="correction-card">
      <div className="correction-card__head">
        <div><b>{title}</b><span className="small dim">{proposal.source_id}</span></div>
        <span className={`chip ${proposal.state === "conflict" || needsRevalidation ? "chip--voided" : "chip--neutral"}`}>
          {needsRevalidation ? "Needs revalidation" : (STATE_LABELS[proposal.state] ?? proposal.state)}
        </span>
      </div>
      <p className="small dim">
        {needsRevalidation
          ? "The authoritative index changed. This annotation is hidden until you revalidate it."
          : proposal.verification_level === "snapshot_verified"
          ? "Exact evidence found in a hash-verified local source snapshot."
          : proposal.verification_level === "structural_only"
            ? "Structure and provenance checked; the evidence remains an unverified claim."
            : "Untrusted draft."}
      </p>
      <details>
        <summary>Proposal and provenance</summary>
        <div className="correction-compare__values">
          <span><small>Original</small><code>{JSON.stringify(proposal.original)}</code></span>
          <span><small>Proposed</small><code>{JSON.stringify(proposal.proposed)}</code></span>
        </div>
        {proposal.validation.reason_codes.length > 0 && (
          <p className="small dim">Checks: {proposal.validation.reason_codes.join(" · ")}</p>
        )}
        {proposal.evidence.map((item) => (
          <div className="correction-evidence" key={item.evidence_id}>
            <small>{item.redacted ? "Redacted evidence receipt" : "Captured evidence · untrusted text"}</small>
            <a href={item.source_url} target="_blank" rel="noreferrer">{item.hostname}</a>
            <blockquote>{item.sanitized_text}</blockquote>
            <code>SHA-256 {item.raw_sha256}</code>
          </div>
        ))}
      </details>
      <div className="correction-card__actions">
        {proposal.target.match_id && (
          <a href={`#/match/${encodeURIComponent(proposal.target.match_id)}`}>Open match</a>
        )}
        <a href={`#/corrections/review/${encodeURIComponent(proposal.proposal_id)}`}>Review</a>
      </div>
    </article>
  );
}

export function CorrectionsQueue() {
  const corrections = useCorrections();
  return (
    <div className="stack corrections-view">
      <header className="corrections-hero">
        <div>
          <p className="eyebrow">Local-first evidence queue</p>
          <h1>Correction proposals</h1>
          <p className="measure dim">
            Proposals stay on this Mac. They never silently change source data, fixtures,
            forecasts, settlement, calibration, or model inputs.
          </p>
        </div>
        <a className="btn btn--primary" href="#/corrections/new-fixture">Propose missing fixture</a>
      </header>
      <div className="correction-trust-note" role="note">
        <b>No central moderation service.</b> Golavo can validate format, exact identity and local
        snapshot evidence. External contribution always requires your final action.
      </div>
      {corrections.loading ? (
        <BlockSkeleton lines={4} />
      ) : corrections.error ? (
        <p role="alert">{corrections.error.message}</p>
      ) : corrections.list.items.length === 0 ? (
        <EmptyState title="No local proposals">
          Use <b>Propose correction</b> on Matchday or a match page. A source URL and captured
          evidence are required before validation.
        </EmptyState>
      ) : (
        <div className="correction-grid">
          {corrections.list.items.map((item) => (
            <QueueCard
              key={item.proposal_id}
              proposal={item}
              currentIndexFingerprint={corrections.capabilities?.current_index_fingerprint}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function toLocalInput(value: string): string {
  const date = new Date(value);
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

function toUtc(value: string): string {
  return new Date(value).toISOString().replace(".000Z", "Z");
}

function SourceDisclosure({ source }: { source: CorrectionSource | undefined }) {
  if (!source) return null;
  return (
    <p className="settings__hint">
      Namespace: <code>{source.license_namespace}</code> · {source.license}.{" "}
      {source.redistributable_export
        ? "A reviewed deterministic export is available after validation."
        : "This license namespace stays local; export is disabled."}
    </p>
  );
}

export function CorrectionEditor({ matchId }: { matchId?: string }) {
  const corrections = useCorrections();
  const missing = !matchId;
  const [detail, setDetail] = useState<MatchDetailResponse | null>(null);
  const [loadingMatch, setLoadingMatch] = useState(Boolean(matchId));
  const [type, setType] = useState<CorrectionType>(missing ? "missing_fixture" : "kickoff_time");
  const [sourceId, setSourceId] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceRevision, setSourceRevision] = useState("");
  const [evidence, setEvidence] = useState("");
  const [kickoff, setKickoff] = useState("");
  const [homeTeam, setHomeTeam] = useState("");
  const [awayTeam, setAwayTeam] = useState("");
  const [competition, setCompetition] = useState("");
  const [upstreamKey, setUpstreamKey] = useState("");
  const [alias, setAlias] = useState("");
  const [canonicalTeam, setCanonicalTeam] = useState("");
  const [venueName, setVenueName] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [homeScore, setHomeScore] = useState("");
  const [awayScore, setAwayScore] = useState("");
  const [proposal, setProposal] = useState<CorrectionProposal | null>(null);
  const [reviewedExport, setReviewedExport] = useState(false);
  const [exportId, setExportId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let live = true;
    setLoadingMatch(true);
    void fetchMatch(matchId)
      .then((value) => {
        if (!live) return;
        setDetail(value);
        if (value) {
          setKickoff(toLocalInput(value.match.kickoff_utc));
          setCanonicalTeam(value.match.home_team);
          setCity(value.match.city ?? "");
          setCountry(value.match.country ?? "");
        }
      })
      .finally(() => live && setLoadingMatch(false));
    return () => { live = false; };
  }, [matchId]);

  const sources = corrections.capabilities?.sources ?? [];
  const allowedSources = useMemo(
    () => sources.filter((source) => source.allowed_types.includes(type)),
    [sources, type],
  );
  useEffect(() => {
    if (!allowedSources.some((source) => source.source_id === sourceId)) {
      setSourceId(allowedSources[0]?.source_id ?? "");
    }
  }, [allowedSources, sourceId]);
  const source = allowedSources.find((item) => item.source_id === sourceId);

  const proposedValue = (): Record<string, unknown> => {
    if (type === "kickoff_time") {
      return { kickoff_utc: toUtc(kickoff), kickoff_precision: "exact" };
    }
    if (type === "team_alias") {
      return {
        alias,
        canonical_team: canonicalTeam,
        scope: {
          source_id: sourceId,
          competition: detail?.match.competition ?? null,
          country: detail?.match.country ?? null,
        },
      };
    }
    if (type === "venue") return { venue_name: venueName, city, country };
    if (type === "final_score") {
      return {
        home_score: Number(homeScore),
        away_score: Number(awayScore),
        score_basis: "regulation_plus_extra_time",
      };
    }
    return {
      home_team: homeTeam,
      away_team: awayTeam,
      competition,
      kickoff_utc: toUtc(kickoff),
      kickoff_precision: "exact",
      upstream_record_key: upstreamKey,
    };
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await createCorrection({
        correction_type: type,
        source_id: sourceId,
        target: matchId ? { match_id: matchId } : {},
        proposed: proposedValue(),
      });
      const attached = await attachCorrectionEvidence(created.proposal_id, {
        source_url: sourceUrl,
        captured_text: evidence,
        ...(sourceRevision ? { source_revision: sourceRevision } : {}),
      });
      const validated = await validateCorrection(attached.proposal_id);
      setProposal(validated);
      await corrections.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  const accept = async () => {
    if (!proposal) return;
    setBusy(true);
    try {
      const next = await acceptLocalCorrection(proposal);
      setProposal(next);
      await corrections.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  const exportReviewed = async () => {
    if (!proposal || !reviewedExport) return;
    setBusy(true);
    try {
      const receipt = await exportCorrection(proposal);
      setExportId(receipt.export_id);
      await saveCorrectionExport(receipt.export_id);
      setProposal(await fetchCorrection(proposal.proposal_id));
      await corrections.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  const markSubmitted = async () => {
    if (!proposal) return;
    setBusy(true);
    try {
      const current = await fetchCorrection(proposal.proposal_id);
      setProposal(await markCorrectionSubmitted(current));
      await corrections.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  if (loadingMatch) return <BlockSkeleton lines={5} />;
  if (corrections.error) {
    return (
      <EmptyState title="Corrections unavailable">
        {corrections.error.message} Your match data and sealed forecasts are unchanged.
      </EmptyState>
    );
  }
  if (matchId && !detail) return <EmptyState title="Match not found">The exact match identity is unavailable.</EmptyState>;

  return (
    <div className="stack corrections-view">
      <header>
        <p className="eyebrow">Untrusted candidate data</p>
        <h1>{missing ? "Propose a missing fixture" : "Propose a match correction"}</h1>
        <p className="measure dim">
          A local proposal is not an official fixture or result. The source-backed original stays
          unchanged and visible. Golavo never checks the evidence page or submits this proposal.
        </p>
      </header>
      {detail && (
        <div className="correction-match-summary">
          <b>{detail.match.home_team} v {detail.match.away_team}</b>
          <span>{detail.match.competition} · {detail.match.kickoff_utc}</span>
          <span>Authoritative source: {detail.match.source_id}</span>
        </div>
      )}
      {!proposal ? (
        <form className="panel correction-form" onSubmit={submit}>
          <div className="panel__body stack">
            {!missing && (
              <label className="settings__field">
                <span>Correction type</span>
                <select className="select" value={type} onChange={(event) => setType(event.target.value as CorrectionType)}>
                  {(["kickoff_time", "team_alias", "venue", "final_score"] as CorrectionType[]).map((value) => (
                    <option key={value} value={value}>{TYPE_LABELS[value]}</option>
                  ))}
                </select>
              </label>
            )}
            <label className="settings__field">
              <span>Evidence source</span>
              <select className="select" value={sourceId} onChange={(event) => setSourceId(event.target.value)} required>
                {allowedSources.map((item) => <option key={item.source_id} value={item.source_id}>{item.name} · {item.license}</option>)}
              </select>
              <SourceDisclosure source={source} />
            </label>
            {(type === "kickoff_time" || type === "missing_fixture") && (
              <label className="settings__field"><span>Proposed kickoff in your local timezone</span><input type="datetime-local" value={kickoff} onChange={(event) => setKickoff(event.target.value)} required /></label>
            )}
            {type === "missing_fixture" && <>
              <div className="correction-two-col">
                <label><span>Home team</span><input value={homeTeam} onChange={(event) => setHomeTeam(event.target.value)} required /></label>
                <label><span>Away team</span><input value={awayTeam} onChange={(event) => setAwayTeam(event.target.value)} required /></label>
              </div>
              <label><span>Competition</span><input value={competition} onChange={(event) => setCompetition(event.target.value)} required /></label>
              <label><span>Exact upstream record key</span><input value={upstreamKey} onChange={(event) => setUpstreamKey(event.target.value)} required /></label>
            </>}
            {type === "team_alias" && <>
              <label><span>Alias as published</span><input value={alias} onChange={(event) => setAlias(event.target.value)} required /></label>
              <label><span>Exact canonical team</span><select className="select" value={canonicalTeam} onChange={(event) => setCanonicalTeam(event.target.value)}>{detail && <><option>{detail.match.home_team}</option><option>{detail.match.away_team}</option></>}</select></label>
            </>}
            {type === "venue" && <>
              <label><span>Venue name</span><input value={venueName} onChange={(event) => setVenueName(event.target.value)} required /></label>
              <div className="correction-two-col"><label><span>City</span><input value={city} onChange={(event) => setCity(event.target.value)} required /></label><label><span>Country</span><input value={country} onChange={(event) => setCountry(event.target.value)} required /></label></div>
            </>}
            {type === "final_score" && <div className="correction-two-col"><label><span>Home score</span><input type="number" min="0" max="99" value={homeScore} onChange={(event) => setHomeScore(event.target.value)} required /></label><label><span>Away score</span><input type="number" min="0" max="99" value={awayScore} onChange={(event) => setAwayScore(event.target.value)} required /></label></div>}
            <hr />
            <label><span>Source URL</span><input type="url" inputMode="url" placeholder="https://…" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} required /></label>
            <label><span>Source revision, if shown</span><input value={sourceRevision} onChange={(event) => setSourceRevision(event.target.value)} /></label>
            <label><span>Captured evidence</span><textarea rows={6} maxLength={65536} value={evidence} onChange={(event) => setEvidence(event.target.value)} required /></label>
            <p className="settings__hint">Golavo is not checking this page. Paste only the part you relied on; it is stored locally as untrusted plain text.</p>
            {error && <p role="alert" className="correction-error">{error.message}</p>}
            <div className="correction-card__actions"><button className="btn btn--primary" disabled={busy || !sourceId}>{busy ? "Validating…" : "Save and validate candidate"}</button><a href="#/corrections">Cancel</a></div>
          </div>
        </form>
      ) : (
        <section className="panel correction-review" aria-live="polite">
          <div className="panel__head"><h2>Review result</h2><span className={`chip ${proposal.state === "conflict" ? "chip--voided" : "chip--neutral"}`}>{STATE_LABELS[proposal.state]}</span></div>
          <div className="panel__body stack">
            <div className="correction-compare__values"><span><small>Source-backed original</small><code>{JSON.stringify(proposal.original)}</code></span><span><small>Your proposal</small><code>{JSON.stringify(proposal.proposed)}</code></span></div>
            <p><b>{proposal.verification_level === "snapshot_verified" ? "Verified local snapshot evidence" : "Structurally validated, unverified evidence"}</b></p>
            {proposal.validation.reason_codes.length > 0 && <p className="small dim">Checks: {proposal.validation.reason_codes.join(" · ")}</p>}
            {proposal.state === "conflict" && <p role="alert">Conflicting candidates fail closed. This proposal cannot become a local annotation or export.</p>}
            {proposal.state === "validated_candidate" && <button className="btn" disabled={busy} onClick={() => void accept()}>Show as my local annotation</button>}
            {proposal.local_visibility === "local_annotation" && <p className="correction-trust-note">Accepted locally means shown as your note. It does not change source data, forecasts, or settlement.</p>}
            {source?.redistributable_export && ["validated_candidate", "accepted_local", "exported", "submitted"].includes(proposal.state) && <>
              <label className="correction-consent"><input type="checkbox" checked={reviewedExport} onChange={(event) => setReviewedExport(event.target.checked)} /> I reviewed this export; it may become public.</label>
              <button className="btn" disabled={busy || !reviewedExport} onClick={() => void exportReviewed()}>Export JSON with native save dialog</button>
            </>}
            {!source?.redistributable_export && <p className="correction-trust-note">This proposal stays in its isolated license namespace and cannot be exported from Golavo.</p>}
            {exportId && source && <>
              <p className="small dim">Export only. Golavo never files an issue or sends this data.</p>
              <button className="btn" onClick={() => void openExternalUrl(source.contribution_url)}>Open contribution page</button>
              {proposal.state === "exported" && <button className="btn btn--ghost" onClick={() => void markSubmitted()}>I completed the external submission</button>}
            </>}
            {error && <p role="alert" className="correction-error">{error.message}</p>}
            <a href="#/corrections">Back to correction queue</a>
          </div>
        </section>
      )}
    </div>
  );
}

export function CorrectionReview({ proposalId }: { proposalId: string }) {
  const corrections = useCorrections();
  const proposal = corrections.list.items.find((item) => item.proposal_id === proposalId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [redactId, setRedactId] = useState<string | null>(null);
  const [reviewedExport, setReviewedExport] = useState(false);
  const [exportId, setExportId] = useState<string | null>(null);
  if (corrections.loading) return <BlockSkeleton lines={4} />;
  if (!proposal) return <EmptyState title="Proposal not found">It may have been removed from this Mac.</EmptyState>;
  const needsRevalidation =
    proposal.target.index_fingerprint !==
    corrections.capabilities?.current_index_fingerprint;
  const source = corrections.capabilities?.sources.find(
    (item) => item.source_id === proposal.source_id,
  );

  const revalidate = async () => {
    setBusy(true);
    setError(null);
    try {
      await validateCorrection(proposal.proposal_id);
      await corrections.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  const accept = async () => {
    setBusy(true);
    setError(null);
    try {
      await acceptLocalCorrection(proposal);
      await corrections.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  const redact = async (evidenceId: string) => {
    if (redactId !== evidenceId) {
      setRedactId(evidenceId);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await redactCorrectionEvidence(proposal, evidenceId);
      setRedactId(null);
      await corrections.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  const exportReviewed = async () => {
    if (!reviewedExport) return;
    setBusy(true);
    setError(null);
    try {
      const receipt = await exportCorrection(proposal);
      setExportId(receipt.export_id);
      await saveCorrectionExport(receipt.export_id);
      await corrections.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  const markSubmitted = async () => {
    setBusy(true);
    setError(null);
    try {
      await markCorrectionSubmitted(proposal);
      await corrections.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack corrections-view">
      <header><p className="eyebrow">Local audit record</p><h1>{TYPE_LABELS[proposal.correction_type]}</h1></header>
      <QueueCard
        proposal={proposal}
        currentIndexFingerprint={corrections.capabilities?.current_index_fingerprint}
      />
      {needsRevalidation && (
        <button className="btn" disabled={busy} onClick={() => void revalidate()}>
          Revalidate against current source data
        </button>
      )}
      {!needsRevalidation && proposal.state === "validated_candidate" && (
        <button className="btn" disabled={busy} onClick={() => void accept()}>
          Show as my local annotation
        </button>
      )}
      {proposal.evidence.some((item) => !item.redacted) && (
        <section className="panel">
          <div className="panel__head"><h2>Captured evidence</h2></div>
          <div className="panel__body stack">
            <p className="small dim">
              Removing evidence deletes its raw local capture, invalidates any local annotation,
              and removes staged exports. A copy you already saved or submitted cannot be recalled.
            </p>
            {proposal.evidence.filter((item) => !item.redacted).map((item) => (
              <div className="settings__row" key={item.evidence_id}>
                <span>{item.hostname} · {item.raw_bytes} bytes</span>
                <button
                  className="btn btn--ghost"
                  disabled={busy}
                  onClick={() => void redact(item.evidence_id)}
                >
                  {redactId === item.evidence_id ? "Confirm remove evidence" : "Remove evidence"}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
      {source?.redistributable_export &&
        ["validated_candidate", "accepted_local", "exported", "submitted"].includes(
          proposal.state,
        ) && (
          <section className="panel">
            <div className="panel__head"><h2>External contribution</h2></div>
            <div className="panel__body stack">
              <p className="small dim">
                Export creates a reviewed JSON file only. Golavo never files an issue, opens a pull
                request, or transmits this proposal.
              </p>
              <label className="correction-consent">
                <input
                  type="checkbox"
                  checked={reviewedExport}
                  onChange={(event) => setReviewedExport(event.target.checked)}
                />
                I reviewed the proposed values, source, license and evidence excerpt; this export
                may become public.
              </label>
              <button
                className="btn"
                disabled={busy || !reviewedExport}
                onClick={() => void exportReviewed()}
              >
                Save deterministic correction JSON
              </button>
              {exportId && (
                <>
                  <button className="btn" onClick={() => void openExternalUrl(source.contribution_url)}>
                    Open contribution page
                  </button>
                  {proposal.state === "exported" && (
                    <button className="btn btn--ghost" onClick={() => void markSubmitted()}>
                      I completed the external submission
                    </button>
                  )}
                </>
              )}
            </div>
          </section>
        )}
      {source && !source.redistributable_export && (
        <p className="correction-trust-note">
          {source.license} proposals stay in <code>{source.license_namespace}</code> and cannot be
          exported from Golavo.
        </p>
      )}
      {error && <p role="alert" className="correction-error">{error.message}</p>}
      <p className="correction-trust-note">This record is a candidate claim. It is not an official fixture or result and never becomes authoritative merely because it is newer.</p>
      <a href="#/corrections">Back to correction queue</a>
    </div>
  );
}
