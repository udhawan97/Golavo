import type { InputsBlock, Snapshot } from "../lib/contract";
import { utc } from "../lib/format";
import { Hash } from "./primitives";

/** Every input snapshot that fed the sealed forecast. Sources are copyable and
 *  the sha256 pins the exact bytes retrieved. */
export function Provenance({ inputs }: { inputs: InputsBlock }) {
  return (
    <section className="panel" aria-labelledby="prov-h">
      <div className="panel__head">
        <h2 id="prov-h">Provenance</h2>
        <span className="muted small" style={{ marginLeft: "auto" }}>
          {inputs.snapshots.length} snapshot{inputs.snapshots.length === 1 ? "" : "s"}
        </span>
      </div>
      <div className="panel__body">
        <dl className="kv" style={{ marginBottom: "1rem" }}>
          <dt>Training cutoff</dt>
          <dd className="num">{utc(inputs.training_cutoff_utc)}</dd>
        </dl>
        {inputs.snapshots.map((s) => <SnapshotRow key={s.snapshot_id} snap={s} />)}
      </div>
    </section>
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
