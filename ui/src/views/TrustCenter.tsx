import { useState } from "react";
import type { ArchivePreview, CheckpointStatus, ProofVerificationResult, RefreshReceipt } from "../lib/contract";
import {
  createCheckpoint,
  downloadPersonalArchive,
  fetchCheckpointStatus,
  fetchRefreshReceipts,
  previewPersonalArchive,
  restorePersonalArchive,
  verifyProofFile,
} from "../lib/api";
import { formatBytes, formatWhen } from "../lib/updater";
import { useAsync } from "../lib/hooks";
import { ErrorState, Loading } from "../components/states";
import { DATA_GENERATION_CHANGED_EVENT } from "../lib/data-refresh-context";

function ErrorText({ value }: { value: string | null }) {
  return value ? <p className="small" role="alert">{value}</p> : null;
}

export function TrustCenter() {
  const checkpoint = useAsync(fetchCheckpointStatus, []);
  const receipts = useAsync(fetchRefreshReceipts, []);
  const [proof, setProof] = useState<ProofVerificationResult | null>(null);
  const [proofError, setProofError] = useState<string | null>(null);
  const [archiveFile, setArchiveFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ArchivePreview | null>(null);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [replace, setReplace] = useState(false);
  const [checkpointState, setCheckpointState] = useState<CheckpointStatus | null>(null);
  const [checkpointError, setCheckpointError] = useState<string | null>(null);
  const [checkpointInvalidated, setCheckpointInvalidated] = useState(false);

  const inspectProof = async (file?: File) => {
    if (!file) return;
    setProof(null); setProofError(null);
    try { setProof(await verifyProofFile(file)); }
    catch (error) { setProofError(error instanceof Error ? error.message : "Proof verification failed"); }
  };
  const inspectArchive = async (file?: File) => {
    if (!file) return;
    setArchiveFile(file); setPreview(null); setReplace(false); setArchiveError(null);
    try { setPreview(await previewPersonalArchive(file)); }
    catch (error) { setArchiveError(error instanceof Error ? error.message : "Archive verification failed"); }
  };
  const restore = async () => {
    if (!archiveFile || !preview || preview.restore_blocked_reason) return;
    setArchiveError(null);
    let restored: ArchivePreview;
    try {
      restored = await restorePersonalArchive(archiveFile, replace, preview.restore_preview_token);
    }
    catch (error) {
      setArchiveError(error instanceof Error ? error.message : "Restore failed");
      return;
    }
    setPreview(restored);
    window.dispatchEvent(new Event(DATA_GENERATION_CHANGED_EVENT));
    setCheckpointInvalidated(true);
    setCheckpointState(null);
    setCheckpointError(null);
    try {
      setCheckpointState(await fetchCheckpointStatus());
      setCheckpointInvalidated(false);
    } catch (error) {
      setCheckpointError(
        error instanceof Error ? error.message : "Checkpoint verification failed after restore",
      );
    }
  };
  const checkpointValue = checkpointInvalidated
    ? null
    : checkpointState ?? (checkpoint.status === "ready" ? checkpoint.data : null);

  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <header>
        <p className="eyebrow">Local integrity tools</p>
        <h1>Trust Center</h1>
        <p className="dim">Verify portable evidence, back up the forecast ledger, and inspect local history. Nothing here contacts a provider.</p>
      </header>

      <section className="panel">
        <div className="panel__head"><h2>Verify a forecast proof</h2></div>
        <div className="panel__body stack">
          <p className="small dim">Select an exported <code>.proof.json</code>. Verification runs in the local engine and does not persist the file.</p>
          <label className="small">Forecast proof file <input type="file" accept="application/json,.json" onChange={(event) => void inspectProof(event.target.files?.[0])} /></label>
          {proof && <div className="callout callout--success"><div><div className="callout__title">Included bytes verified</div><p className="small">{proof.artifact_count} artifacts · {proof.embedded_source_count} embedded source manifests · {proof.descriptor_only_source_count} descriptor-only sources</p><ul className="small">{proof.source_checks.map((source) => <li key={`${source.source_id}:${source.sha256}`}>{source.source_id}: {source.status === "embedded-manifest-hash-valid" ? "embedded manifest hash valid" : "descriptor only — source bytes not verified"}</li>)}</ul><p className="small dim">{proof.limits.join(" ")}</p></div></div>}
          <ErrorText value={proofError} />
        </div>
      </section>

      <section className="panel">
        <div className="panel__head"><h2>Forecast-ledger archive</h2></div>
        <div className="panel__body stack">
          <p className="small dim">Forecasts, picks, followed-match state, and the verified linked checkpoint chain when one exists. Team favorites, credentials, provider settings, licensed overlays, weather, research captures, refresh generations, and caches are excluded.</p>
          <div className="controls"><button className="btn" type="button" onClick={() => void downloadPersonalArchive()}>Download verified backup</button><label className="btn btn--ghost">Preview restore<input className="visually-hidden" type="file" accept="application/zip,.zip" onChange={(event) => void inspectArchive(event.target.files?.[0])} /></label></div>
          {preview && <div className="card card--pad stack"><strong>{preview.restored ? "Restore complete" : "Archive verified"}</strong><span className="small dim">{preview.file_count} files · {formatBytes(preview.total_bytes)} · {preview.conflicts.length} conflicts</span><p className="small">{preview.checkpoint_recovery.available ? `Recovery drill passed for ${preview.checkpoint_recovery.checkpoint_count} linked checkpoint(s)${preview.checkpoint_recovery.legacy_checkpoint_count ? `, including ${preview.checkpoint_recovery.legacy_checkpoint_count} legacy-format checkpoint(s)` : ""}.` : "No checkpoint chain was present; forecast, pick, and follow files remain recoverable."}</p>{preview.checkpoint_recovery.missing_artifacts.length > 0 && <p className="small dim">The recovered chain still records {preview.checkpoint_recovery.missing_artifacts.length} artifact(s) that were already absent when this backup was made.</p>}{preview.restore_blocked_reason && !preview.restored && <p className="small" role="alert">{preview.restore_blocked_reason}</p>}{preview.conflicts.length > 0 && !preview.restored && <div><span className="small"><strong>Different local files</strong></span><ul className="small">{preview.conflicts.slice(0, 20).map((path) => <li key={path}><code>{path}</code></li>)}</ul>{preview.conflicts.length > 20 && <p className="small dim">And {preview.conflicts.length - 20} more.</p>}</div>}{preview.requires_replace_confirmation && !preview.restored && !preview.restore_blocked_reason && <label className="small"><input type="checkbox" checked={replace} onChange={(event) => setReplace(event.target.checked)} /> Replace exactly the different local files listed above</label>}{!preview.restored && !preview.restore_blocked_reason && <button className="btn" type="button" disabled={preview.requires_replace_confirmation && !replace} onClick={() => void restore()}>Restore verified files</button>}{preview.restored && preview.pre_restore_backup && <p className="small dim">{preview.pre_restore_backup_verified === false ? "The prior corrupt bytes were preserved as an unverified quarantine copy" : "The verified pre-restore backup remains available locally as"} <code>{preview.pre_restore_backup}</code>.</p>}</div>}
          <ErrorText value={archiveError} />
        </div>
      </section>

      <section className="panel">
        <div className="panel__head"><h2>Ledger checkpoints</h2></div>
        <div className="panel__body stack">
          {checkpoint.status === "loading" && <Loading label="Checking ledger chain" />}
          {checkpoint.status === "error" && !checkpointInvalidated && <ErrorState error={checkpoint.error} />}
          {checkpointValue && <><p className="small">{checkpointValue.checkpoint_count} linked checkpoint(s) · {checkpointValue.missing_artifacts.length} explicitly absent · {checkpointValue.uncheckpointed_artifacts.length} not yet checkpointed</p>{checkpointValue.migration_required && <p className="small">This verified legacy chain can be continued in the current format by creating its next checkpoint.</p>}{checkpointValue.legacy_checkpoint_count > 0 && !checkpointValue.migration_required && <p className="small dim">The current head preserves {checkpointValue.legacy_checkpoint_count} verified legacy-format checkpoint(s) behind it.</p>}<p className="small dim">{checkpointValue.limits.join(" ")}</p><button className="btn" type="button" onClick={() => { setCheckpointError(null); void createCheckpoint().then((value) => { setCheckpointState(value); setCheckpointInvalidated(false); }, (error) => setCheckpointError(error instanceof Error ? error.message : "Checkpoint failed")); }}>Create checkpoint now</button></>}
          <ErrorText value={checkpointError} />
        </div>
      </section>

      <section className="panel">
        <div className="panel__head"><h2>Data application receipts</h2></div>
        <div className="panel__body stack">
          {receipts.status === "loading" && <Loading label="Reading receipts" />}
          {receipts.status === "error" && <ErrorState error={receipts.error} />}
          {receipts.status === "ready" && <>{receipts.data.application_gap && <p className="small" role="alert">A data generation was applied, but its secondary receipt could not be appended: {receipts.data.application_gap.message}</p>}{receipts.data.items.length ? receipts.data.items.map((receipt: RefreshReceipt) => <Receipt key={receipt.receipt_id} receipt={receipt} />) : <p className="small dim">No refresh generation has been applied on this installation.</p>}</>}
        </div>
      </section>
    </div>
  );
}

function Receipt({ receipt }: { receipt: RefreshReceipt }) {
  const counts = receipt.change_summary.stable_identity_counts;
  return <div className="card card--pad stack"><strong>{receipt.operation === "rollback" ? "Rollback applied" : "Data generation applied"}</strong><p className="small dim">{formatWhen(Date.parse(receipt.occurred_at_utc))} · {receipt.active_generation_id.slice(0, 12)} · index {receipt.active_index_sha256?.slice(0, 12) ?? "hash unavailable"}</p>{counts ? <p className="small">Stable identities: +{counts.added} / −{counts.removed} · {counts.new_results} new results · {counts.rekeyed} rekeyed</p> : <p className="small">Stable-identity comparison unavailable.</p>}<p className="small dim">{receipt.change_summary.reason}</p><p className="small dim">{receipt.source_summaries.length} source receipt(s) · {receipt.capability_summaries.length} capability certificate(s). Local application history, not a tamper-proof external audit.</p></div>;
}
