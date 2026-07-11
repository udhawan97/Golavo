/**
 * Plain-language verdict for the Casual view.
 *
 * This is a pure, deterministic function of the SEALED numbers — fixed phrase
 * bands over forecast.probs and the score matrix. No AI is involved: the same
 * artifact always yields the same words, and the words never claim more
 * certainty than the probabilities do. If the model abstained, it says so.
 */

import type { ForecastArtifact, Outcome } from "./contract";
import { pct } from "./format";

export interface VerdictSummary {
  headline: string;
  detail: string;
}

/** Fixed strength bands for a team's leading probability (plural-friendly). */
function teamStrength(p: number): string {
  if (p >= 0.65) return "strong favourites";
  if (p >= 0.5) return "favoured";
  if (p >= 0.42) return "narrow favourites";
  return "the marginal pick";
}

function drawStrength(p: number): string {
  if (p >= 0.5) return "favoured";
  if (p >= 0.42) return "narrowly favoured";
  return "the marginal pick";
}

export function verdictSummary(artifact: ForecastArtifact): VerdictSummary {
  const { forecast, match } = artifact;
  if (forecast.abstained || !forecast.probs) {
    return {
      headline: "No forecast — the model abstained.",
      detail:
        forecast.abstain_reason ??
        "At least one side had too few recent matches to model honestly, so no probabilities were issued.",
    };
  }

  const probs = forecast.probs;
  const ranked: Array<[Outcome, number]> = [
    ["home", probs.home],
    ["draw", probs.draw],
    ["away", probs.away],
  ];
  ranked.sort((a, b) => b[1] - a[1]);
  const [topKey, topP] = ranked[0];
  const margin = topP - ranked[1][1];

  let headline: string;
  if (topP < 0.4 && margin < 0.06) {
    // Genuinely open: three-way spread with no clear leader.
    headline = `${match.home_team} v ${match.away_team} is too close to call.`;
  } else if (topKey === "draw") {
    headline = `A draw is ${drawStrength(topP)}.`;
  } else {
    const team = topKey === "home" ? match.home_team : match.away_team;
    headline = `${team} are ${teamStrength(topP)}.`;
  }

  const distribution =
    `${match.home_team} ${pct(probs.home)}, draw ${pct(probs.draw)}, ` +
    `${match.away_team} ${pct(probs.away)}`;
  let scoreline = "";
  const sm = forecast.score_matrix;
  if (sm) {
    const ml = sm.most_likely;
    scoreline =
      ` The single most likely score is ${match.home_team} ${ml.home}–${ml.away} ` +
      `${match.away_team}, at ${pct(ml.probability)}.`;
  }
  return { headline, detail: `Sealed probabilities: ${distribution}.${scoreline}` };
}
