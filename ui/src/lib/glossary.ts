/** Plain-language glosses for the scoring metrics, in one place so the Backtests
 *  table, Track record, and the Scored panel all explain them the same way.
 *  Rendered as an <abbr title> or an InfoPopover — never as a wall of text. */
export const METRIC_GLOSS = {
  logLoss:
    "How surprised the model was by the results — lower means it saw them coming. " +
    "About 1.10 is the guess-nothing baseline; lower is better.",
  brier: "Squared error of the probabilities across all three outcomes (0–2). Lower is better.",
  ece: "Calibration error — how far the stated confidence drifts from what actually happened. Lower is better.",
  rps: "Ranked probability score — rewards getting the ordering of outcomes right, not just the winner. Lower is better.",
} as const;
