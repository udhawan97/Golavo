import type { ForecastArtifact } from "../lib/contract";
import { FAMILY_LABELS } from "../lib/contract";
import { fetchForecasts } from "../lib/api";
import { pct, relative, utc } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { ClockIcon, GlobeIcon } from "../components/icons";
import { HorizonChip, StatusChip } from "../components/primitives";
import { EmptyState, ErrorState, ListSkeleton, Loading } from "../components/states";

export function MatchdayList() {
  const state = useAsync(fetchForecasts, []);

  return (
    <div className="stack" style={{ ["--gap" as string]: "1.4rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Matchday</h1>
        <p className="muted" style={{ maxWidth: "60ch" }}>
          Every forecast is sealed before kickoff and scored after full time. Newest first.
        </p>
      </header>

      {state.status === "loading" && (<><Loading label="Loading forecasts" /><ListSkeleton /></>)}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && (
        state.data.length === 0
          ? <EmptyState title="No forecasts sealed yet">When a forecast is sealed for an upcoming fixture, it will appear here.</EmptyState>
          : <ForecastGrid artifacts={state.data} />
      )}
    </div>
  );
}

function ForecastGrid({ artifacts }: { artifacts: ForecastArtifact[] }) {
  // A forecast is "superseded" if a later artifact points back to it.
  const supersededIds = new Set(artifacts.map((a) => a.supersedes).filter(Boolean) as string[]);
  return (
    <ul className="md-grid">
      {artifacts.map((a) => (
        <li key={a.artifact_id}>
          <MatchCard artifact={a} superseded={supersededIds.has(a.artifact_id)} />
        </li>
      ))}
    </ul>
  );
}

function MatchCard({ artifact, superseded }: { artifact: ForecastArtifact; superseded: boolean }) {
  const { match, forecast, model, evaluation, status } = artifact;
  const scored = status === "scored" && evaluation;

  return (
    <a className="md-card" href={`#/forecast/${artifact.artifact_id}`}>
      <div className="md-card__top">
        <span className="md-card__comp">
          {match.competition}{match.stage ? <span className="dim"> · {match.stage}</span> : null}
        </span>
        <span className="md-card__spacer" />
        {match.neutral_venue && <span className="chip chip--neutral">Neutral</span>}
        {superseded && <span className="chip chip--voided" title="A later seal supersedes this one">Superseded</span>}
        <HorizonChip horizon={forecast.horizon} />
        <StatusChip status={status} />
      </div>

      <div className="md-card__teams">
        <span>{match.home_team}</span>
        {scored
          ? <span className="md-card__score num">{evaluation.actual.home_goals}–{evaluation.actual.away_goals}</span>
          : <span className="md-card__vs">vs</span>}
        <span>{match.away_team}</span>
      </div>

      <div className="md-card__meta">
        <span><ClockIcon /> <span className="num">{utc(match.kickoff_utc)}</span> <span className="dim">({relative(match.kickoff_utc)})</span></span>
        <span><GlobeIcon /> {match.city ? `${match.city}, ${match.country}` : match.country ?? "—"}</span>
        <span className="dim">{FAMILY_LABELS[model.family]}</span>
      </div>

      {forecast.probs ? (
        <div className="md-card__prob">
          <MiniBar h={forecast.probs.home} d={forecast.probs.draw} a={forecast.probs.away}
                   home={match.home_team} away={match.away_team} />
        </div>
      ) : forecast.abstained ? (
        <p className="md-card__abstain">
          <b>Abstained.</b>
          <span className="muted">{firstSentence(forecast.abstain_reason)}</span>
        </p>
      ) : null}

      {status === "voided" && (
        <p className="md-card__abstain" style={{ color: "var(--text-dim)" }}>
          <b>Voided.</b> <span className="muted">Excluded from scoring.</span>
        </p>
      )}
    </a>
  );
}

/** Compact 3-segment bar with an accessible summary, for the list. */
function MiniBar({ h, d, a, home, away }: { h: number; d: number; a: number; home: string; away: string }) {
  const label = `${home} ${pct(h)}, draw ${pct(d)}, ${away} ${pct(a)}`;
  return (
    <div className="probbar" style={{ ["--h" as string]: "26px" }}>
      <div className="probbar__track" role="img" aria-label={label}>
        <div className="probbar__seg probbar__seg--home" style={{ width: `${h * 100}%` }} aria-hidden><span>{pct(h, 0)}</span></div>
        <div className="probbar__seg probbar__seg--draw" style={{ width: `${d * 100}%` }} aria-hidden><span>{pct(d, 0)}</span></div>
        <div className="probbar__seg probbar__seg--away" style={{ width: `${a * 100}%` }} aria-hidden><span>{pct(a, 0)}</span></div>
      </div>
    </div>
  );
}

function firstSentence(text: string | null): string {
  if (!text) return "";
  const dot = text.indexOf(". ");
  return dot > 0 ? text.slice(0, dot + 1) : text;
}
