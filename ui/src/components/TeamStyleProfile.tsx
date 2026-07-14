/**
 * TeamStyleProfile — "how they attack & defend", fitted from results.
 *
 * Honest by construction: these are the goal voice's OWN fitted per-team
 * multipliers (attack = league-relative goals-for rate; defence = goals-against
 * rate, lower is tighter), plus this fixture's expected goals. Golavo has no
 * shots/xG/lineups/event data — this is how the teams' RESULTS look to the goal
 * model, not a tactical scouting report, and the UI says so plainly.
 */
import type { MatchAnalysis, TeamStyle, TeamStyleEntry } from "../lib/contract";

/** Map a multiplier in [clipMin, ~2.0] to a 0..1 bar fraction. */
function frac(value: number, clipMin: number): number {
  const top = 2.0; // typical upper end; multipliers clip at 2.8 but bars saturate here
  return Math.max(0, Math.min(1, (value - clipMin) / (top - clipMin)));
}

/** A mirrored row: home grows left of the spine, away grows right. */
export function MirrorRow({
  label,
  hint,
  homeFrac,
  awayFrac,
  homeText,
  awayText,
  expert,
  ariaLabel,
}: {
  label: string;
  hint?: string;
  homeFrac: number;
  awayFrac: number;
  homeText: string;
  awayText: string;
  expert: boolean;
  ariaLabel?: string;
}) {
  return (
    <div className="style-row">
      <div className="style-row__label">
        {label}
        {hint && <span className="style-row__hint small dim"> · {hint}</span>}
      </div>
      <div className="style-row__bars" role="img" aria-label={ariaLabel ?? label}>
        <div className="style-row__side style-row__side--home">
          {expert && <span className="style-row__num num">{homeText}</span>}
          <span className="style-bar style-bar--home" style={{ width: `${homeFrac * 100}%` }} />
        </div>
        <span className="style-row__spine" aria-hidden />
        <div className="style-row__side style-row__side--away">
          <span className="style-bar style-bar--away" style={{ width: `${awayFrac * 100}%` }} />
          {expert && <span className="style-row__num num">{awayText}</span>}
        </div>
      </div>
    </div>
  );
}

export function TeamStyleProfile({
  analysis,
  expert = false,
}: {
  analysis: MatchAnalysis;
  expert?: boolean;
}) {
  const style: TeamStyle | null | undefined = analysis.team_style;
  if (!style) return null;
  const home = analysis.match.home_team;
  const away = analysis.match.away_team;
  const h: TeamStyleEntry | undefined = style.teams[home];
  const a: TeamStyleEntry | undefined = style.teams[away];
  if (!h || !a) return null;
  const clipMin = style.clip.min;

  return (
    <section className="panel style-profile" aria-labelledby="ts-h">
      <div className="panel__head">
        <h2 id="ts-h">How they attack &amp; defend</h2>
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>
          fitted from results · no event data
        </span>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: ".8rem" }}>
        <div className="style-profile__teams small muted">
          <span>{home}</span>
          <span>{away}</span>
        </div>

        <MirrorRow
          label="Attack"
          hint={`baseline ${style.baseline.toFixed(1)}`}
          homeFrac={frac(h.attack, clipMin)}
          awayFrac={frac(a.attack, clipMin)}
          homeText={h.attack.toFixed(2)}
          awayText={a.attack.toFixed(2)}
          expert={expert}
        />
        {/* Defence is inverted so a LONGER bar = tighter defence; the legend says so. */}
        <MirrorRow
          label="Defence"
          hint="longer = tighter"
          homeFrac={frac(2.35 - h.defence, clipMin)}
          awayFrac={frac(2.35 - a.defence, clipMin)}
          homeText={h.defence.toFixed(2)}
          awayText={a.defence.toFixed(2)}
          expert={expert}
        />
        {h.expected_goals_for != null && a.expected_goals_for != null && (
          <MirrorRow
            label="Model goals"
            hint="expected, not predicted"
            homeFrac={Math.min(1, h.expected_goals_for / 3.5)}
            awayFrac={Math.min(1, a.expected_goals_for / 3.5)}
            homeText={h.expected_goals_for.toFixed(2)}
            awayText={a.expected_goals_for.toFixed(2)}
            expert={expert}
          />
        )}
        {h.expected_goals_against != null && a.expected_goals_against != null && (
          <MirrorRow
            label="Model goals against"
            hint="expected · lower = tighter"
            homeFrac={Math.min(1, h.expected_goals_against / 3.5)}
            awayFrac={Math.min(1, a.expected_goals_against / 3.5)}
            homeText={h.expected_goals_against.toFixed(2)}
            awayText={a.expected_goals_against.toFixed(2)}
            expert={expert}
          />
        )}

        <p className="small dim" style={{ margin: 0 }}>
          These are the goal model’s multipliers fitted from past scorelines (time-decayed,
          prior-shrunk), against a {style.baseline.toFixed(1)} league baseline. Golavo has no shots,
          xG, lineups or event data — this is how the teams’ <b>results</b> look to the model, not a
          tactical scouting report.
        </p>
      </div>
    </section>
  );
}
