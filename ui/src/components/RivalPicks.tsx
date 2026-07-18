import type { PickView, RivalPick } from "../lib/contract";
import { RIVALS, rivalLabel } from "../lib/picks";

const OUTCOME = { home: "Home win", draw: "Draw", away: "Away win" } as const;

export function RivalPicks({
  rivals,
  pick,
}: {
  rivals: RivalPick[];
  pick: PickView | null;
}) {
  const revealed = pick !== null;
  const frozen = pick && pick.status !== "draft";
  if (rivals.length === 0 || rivals.every((rival) => rival.capability === "abstained")) {
    return (
      <div className="rivals-empty small muted">
        The rivals sit this one out — not enough history to model this match. Your pick still
        counts (no bonus available).
      </div>
    );
  }
  return (
    <section className="rivals" aria-labelledby="rivals-title">
      <div className="rivals__head">
        <h3 id="rivals-title">You vs the machines</h3>
        <span className="small muted">
          {!revealed
            ? "Five deterministic model rivals have made their calls. Save yours to see theirs."
            : frozen
              ? "Calls frozen at kickoff."
              : "Rival picks can still shift until kickoff — like yours."}
        </span>
      </div>
      <div className={`rivals__grid${revealed ? "" : " is-hidden"}`}>
        {rivals.map((rival) => (
          <article className="rival-card" key={rival.family} aria-label={revealed ? rivalLabel(rival.family) : "Hidden rival pick"}>
            <div className="rival-card__name">{RIVALS[rival.family].name}</div>
            <div className="rival-card__pick num" aria-hidden={!revealed}>
              {rival.capability === "abstained"
                ? "Sits out"
                : rival.score_pick
                  ? `${rival.score_pick.home_goals}–${rival.score_pick.away_goals}`
                  : rival.outcome_pick
                    ? OUTCOME[rival.outcome_pick]
                    : "Unavailable"}
            </div>
            <div className="rival-card__sub">
              {rival.capability === "outcome_only"
                ? "calls the winner only · tops out at 1 pt"
                : rival.capability === "score"
                  ? "calls an exact score"
                  : "not enough history"}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
