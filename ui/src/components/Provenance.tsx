import type { InputsBlock, Snapshot } from "../lib/contract";
import { utc } from "../lib/format";
import { Hash } from "./primitives";

/** Every input snapshot that fed the sealed forecast — a receipt: identifiers,
 *  then source → retrieved → sha256 per input. Sources are copyable and the
 *  sha256 pins the exact bytes retrieved. Body-only; a Drawer supplies the frame.
 *  The raw match/artifact ids live here (demoted out of the page header). */
export function Provenance({
  inputs,
  matchId,
  artifactId,
}: {
  inputs: InputsBlock;
  matchId?: string;
  artifactId?: string;
}) {
  return (
    <div className="stack" style={{ ["--gap" as string]: ".8rem" }}>
      <dl className="kv">
        {artifactId && (<><dt>Artifact id</dt><dd className="mono">{artifactId}</dd></>)}
        {matchId && (<><dt>Match id</dt><dd className="mono">{matchId}</dd></>)}
        <dt>Training cutoff</dt>
        <dd className="num">{utc(inputs.training_cutoff_utc)}</dd>
      </dl>
      {inputs.snapshots.map((s) => <SnapshotRow key={s.snapshot_id} snap={s} />)}
    </div>
  );
}

function SnapshotRow({ snap }: { snap: Snapshot }) {
  return (
    <div className="snap">
      <div className="snap__head">
        <span className="snap__id mono">{snap.source_id}</span>
        <span className="chip chip--neutral">{snap.license}</span>
      </div>
      <dl className="snap__grid">
        <dt>Snapshot</dt>
        <dd className="mono">{snap.snapshot_id}</dd>

        <dt>Upstream ref</dt>
        <dd className="mono">{snap.upstream_ref}</dd>

        <dt>Source</dt>
        <dd style={{ minWidth: 0 }}>
          <a href={snap.url} target="_blank" rel="noreferrer noopener">{snap.url}</a>
        </dd>

        <dt>Retrieved</dt>
        <dd className="num">{utc(snap.retrieved_at_utc)}</dd>

        <dt>sha256</dt>
        <dd><Hash value={snap.sha256} /></dd>
      </dl>
    </div>
  );
}
