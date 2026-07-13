/**
 * FormStripsRow — each side's last-five results as W/D/L chips.
 *
 * Descriptive history straight from the leak-safe analysis payload (pre-kickoff
 * only), so it renders even when the council abstains. Nothing here is a forecast.
 */
import type { FormEntry, MatchAnalysis } from "../lib/contract";
import { utc } from "../lib/format";

function chipTitle(e: FormEntry): string {
  const where = e.neutral ? "neutral" : e.is_home ? "home" : "away";
  const verb = e.result === "W" ? "Won" : e.result === "L" ? "Lost" : "Drew";
  return `${verb} ${e.gf}–${e.ga} v ${e.opponent} · ${e.date} · ${where}`;
}

function TeamForm({ team, entries }: { team: string; entries: FormEntry[] }) {
  return (
    <div className="form-row">
      <span className="form-row__team">{team}</span>
      {entries.length === 0 ? (
        <span className="small dim">No prior results in this data.</span>
      ) : (
        <span className="form-row__chips" aria-label={`${team} last ${entries.length}`}>
          {entries.map((e, i) => (
            <span
              key={`${e.date}-${i}`}
              className={`form-chip form-chip--${e.result.toLowerCase()}`}
              title={chipTitle(e)}
              aria-label={chipTitle(e)}
            >
              {e.result}
            </span>
          ))}
        </span>
      )}
    </div>
  );
}

export function FormStripsRow({ analysis }: { analysis: MatchAnalysis }) {
  const form = analysis.team_form;
  if (!form) return null;
  const home = analysis.match.home_team;
  const away = analysis.match.away_team;
  return (
    <section className="form-strips card" aria-label="Recent form">
      <div className="form-strips__head">
        <span className="form-strips__title">Recent form</span>
        <span className="small dim">
          Last 5 · pre-kickoff only (cutoff {utc(analysis.information_cutoff_utc)})
        </span>
      </div>
      <TeamForm team={home} entries={form[home] ?? []} />
      <TeamForm team={away} entries={form[away] ?? []} />
    </section>
  );
}
