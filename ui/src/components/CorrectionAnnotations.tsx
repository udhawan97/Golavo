import { useCorrections } from "../lib/correction-context";

const LABELS: Record<string, string> = {
  kickoff_time: "Kickoff",
  team_alias: "Team alias",
  venue: "Venue",
  final_score: "Final score",
  missing_fixture: "Missing fixture",
};

export function CorrectionAnnotations({ matchId }: { matchId: string }) {
  const corrections = useCorrections();
  const items = corrections.acceptedByMatch.get(matchId) ?? [];
  if (!items.length) return null;
  return (
    <aside className="correction-annotations panel" aria-labelledby="local-corrections-title">
      <div className="panel__head">
        <h2 id="local-corrections-title">Your local annotations</h2>
        <a href="#/corrections">Review queue ›</a>
      </div>
      <div className="panel__body stack">
        <p className="small dim">
          These proposals do not replace the source-backed match, change a forecast, or settle a seal.
        </p>
        {items.map((item) => (
          <div className="correction-compare" key={item.proposal_id}>
            <div>
              <b>{LABELS[item.correction_type]}</b>
              <span className="chip chip--neutral">
                {item.verification_level === "snapshot_verified"
                  ? "Verified local snapshot"
                  : "Unverified local proposal"}
              </span>
            </div>
            <div className="correction-compare__values">
              <span><small>Source-backed original</small><code>{JSON.stringify(item.original)}</code></span>
              <span><small>Your proposal</small><code>{JSON.stringify(item.proposed)}</code></span>
            </div>
            <p className="small dim">Source: {item.source_id}</p>
          </div>
        ))}
      </div>
    </aside>
  );
}
