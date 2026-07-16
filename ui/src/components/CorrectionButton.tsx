export function CorrectionButton({ matchId, compact = false }: { matchId: string; compact?: boolean }) {
  return (
    <a
      className={`btn btn--ghost correction-button${compact ? " correction-button--compact" : ""}`}
      href={`#/corrections/new/${encodeURIComponent(matchId)}`}
      aria-label="Propose a source-backed correction for this match"
      title="Propose correction"
    >
      {compact ? "Correct" : "Propose correction"}
    </a>
  );
}
