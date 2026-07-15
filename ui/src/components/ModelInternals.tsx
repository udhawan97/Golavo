import type { CouncilModel, MatchAnalysis } from "../lib/contract";

interface ParamRow {
  key: string;
  label: string;
  value: number;
  explanation: string;
}

const LABELS: Record<string, string> = {
  elo_ordlogit: "Elo ratings voice",
  dixon_coles: "Dixon–Coles goals voice",
};

function numberAt(record: Record<string, unknown> | null, key: string): number | null {
  const value = record?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function nestedNumber(
  record: Record<string, unknown> | null,
  key: string,
  team: string,
): number | null {
  const values = record?.[key];
  if (!values || typeof values !== "object" || Array.isArray(values)) return null;
  const value = (values as Record<string, unknown>)[team];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function valueText(value: number): string {
  if (Math.abs(value) >= 100) return value.toFixed(0);
  if (Math.abs(value) >= 10) return value.toFixed(1).replace(/\.0$/, "");
  return value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function multiplierText(value: number, kind: "attack" | "defence"): string {
  const points = Math.round(Math.abs(value - 1) * 100);
  if (value === 1) return kind === "attack" ? "scores at the dataset average" : "concedes at the dataset average";
  const direction = value > 1 ? "more" : "less";
  return `${kind === "attack" ? "scores" : "concedes"} ${points}% ${direction} than an average side in this dataset`;
}

function eloRows(model: CouncilModel, home: string, away: string): ParamRow[] {
  const params = model.params;
  const rows: ParamRow[] = [];
  const homeRating = numberAt(params, "home_rating") ?? numberAt(params, "home_elo") ?? nestedNumber(params, "ratings", home);
  const awayRating = numberAt(params, "away_rating") ?? numberAt(params, "away_elo") ?? nestedNumber(params, "ratings", away);
  if (homeRating != null) rows.push({ key: "home-rating", label: `${home} rating`, value: homeRating, explanation: "higher ratings indicate stronger results against the opposition faced" });
  if (awayRating != null) rows.push({ key: "away-rating", label: `${away} rating`, value: awayRating, explanation: "higher ratings indicate stronger results against the opposition faced" });

  const explanations: Record<string, [string, string]> = {
    home_advantage: ["Home advantage", "rating points added for a non-neutral home side; neutral fixtures use zero"],
    k_factor: ["Update rate", "controls how quickly a result moves each team’s rating"],
    scale: ["Rating scale", "controls how a rating gap translates into outcome chances"],
    threshold: ["Draw corridor", "the fitted middle band mapped to a draw"],
  };
  for (const [key, [label, explanation]] of Object.entries(explanations)) {
    const value = numberAt(params, key);
    if (value != null) rows.push({ key, label, value, explanation });
  }
  return rows;
}

function goalRows(model: CouncilModel, analysis: MatchAnalysis, home: string, away: string): ParamRow[] {
  const rows: ParamRow[] = [];
  const params = model.params;
  const style = analysis.team_style?.family === model.family ? analysis.team_style.teams : null;
  for (const [team, side] of [[home, "home"], [away, "away"]] as const) {
    const attack = style?.[team]?.attack ?? nestedNumber(params, "attack", team);
    const defence = style?.[team]?.defence ?? nestedNumber(params, "defence", team);
    if (attack != null) rows.push({ key: `${side}-attack`, label: `${team} attack`, value: attack, explanation: multiplierText(attack, "attack") });
    if (defence != null) rows.push({ key: `${side}-defence`, label: `${team} defence`, value: defence, explanation: multiplierText(defence, "defence") });
  }

  const explanations: Record<string, [string, string]> = {
    rho: ["ρ low-score correction", "rebalances the four low-scoring outcomes without adding another model voice"],
    home_advantage: ["Home advantage", "the goal-model adjustment for a non-neutral home side"],
    xi: ["Recency decay", "controls how quickly older match results lose weight"],
    prior_matches: ["Prior strength", "average-team matches blended into sparse team histories"],
  };
  for (const [key, [label, explanation]] of Object.entries(explanations)) {
    const value = numberAt(params, key);
    if (value != null) rows.push({ key, label, value, explanation });
  }
  return rows;
}

export function ModelInternals({ analysis, home, away }: { analysis: MatchAnalysis; home: string; away: string }) {
  const voices = analysis.models
    .filter((model) => model.role === "voice" && model.params)
    .map((model) => ({
      model,
      rows: model.method === "ratings" ? eloRows(model, home, away) : goalRows(model, analysis, home, away),
    }))
    .filter(({ rows }) => rows.length > 0);
  if (voices.length === 0) return null;

  return (
    <aside className="model-internals" aria-labelledby="model-internals-title">
      <header>
        <span className="upper">Expert</span>
        <h4 id="model-internals-title">Under the hood</h4>
        <p>Fitted values the two council voices used for this fixture.</p>
      </header>
      <div className="model-internals__voices">
        {voices.map(({ model, rows }) => (
          <section key={model.family} aria-label={LABELS[model.family] ?? model.family}>
            <h5>{LABELS[model.family] ?? model.family}</h5>
            <dl>
              {rows.map((row) => (
                <div key={row.key}>
                  <dt>{row.label}</dt>
                  <dd><span className="num">{valueText(row.value)}</span><span>{row.explanation}.</span></dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>
      <p className="small dim model-internals__note">Only fields carried by this analysis payload are shown.</p>
    </aside>
  );
}
