import { useMemo, useState } from "react";
import type { ArtifactStatus, ForecastArtifact } from "../lib/contract";
import { FAMILY_LABELS, STATUS_LABELS } from "../lib/contract";
import { fetchForecasts } from "../lib/api";
import { largestRemainder, kickoffRelative, utc } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { ClockIcon, GlobeIcon } from "../components/icons";
import { HorizonChip, StatusChip } from "../components/primitives";
import { EmptyState, ErrorState, ListSkeleton, Loading } from "../components/states";

export function MatchdayList() {
  const state = useAsync(fetchForecasts, []);

  return (
    <div className="stack" style={{ ["--gap" as string]: "1.4rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <a href="#/lab">Model Lab</a>
        </nav>
        <h1>Sealed forecasts</h1>
        <p className="muted" style={{ maxWidth: "60ch" }}>
          Predictions you sealed before kickoff, scored after full time. Newest first. Open a match
          from Matchday to seal a new one.
        </p>
      </header>

      {state.status === "loading" && (<><Loading label="Loading forecasts" /><ListSkeleton /></>)}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && (
        state.data.length === 0
          ? <EmptyState title="No forecasts sealed yet">Seal an upcoming international from its match page to start your record. <a href="#/guide/sealing">How sealing works ›</a></EmptyState>
          : <ForecastGrid artifacts={state.data} />
      )}
    </div>
  );
}

type StatusFilter = ArtifactStatus | "all";

function ForecastGrid({ artifacts }: { artifacts: ForecastArtifact[] }) {
  // A forecast is "superseded" if a later artifact points back to it. Computed
  // over the FULL list so the flag stays correct even when its successor is
  // filtered out of view.
  const supersededIds = new Set(artifacts.map((a) => a.supersedes).filter(Boolean) as string[]);

  const [status, setStatus] = useState<StatusFilter>("all");
  const [competition, setCompetition] = useState<string>("all");
  const [team, setTeam] = useState("");

  // Only offer status chips and competitions that actually appear — no dead filters.
  const statuses = useMemo(() => {
    const present = new Set(artifacts.map((a) => a.status));
    return (["sealed", "scored", "abstained", "voided"] as ArtifactStatus[]).filter((s) => present.has(s));
  }, [artifacts]);
  const competitions = useMemo(
    () => Array.from(new Set(artifacts.map((a) => a.match.competition))).sort((a, b) => a.localeCompare(b)),
    [artifacts],
  );

  const query = team.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      artifacts.filter((a) => {
        if (status !== "all" && a.status !== status) return false;
        if (competition !== "all" && a.match.competition !== competition) return false;
        if (query && !`${a.match.home_team} ${a.match.away_team}`.toLowerCase().includes(query)) return false;
        return true;
      }),
    [artifacts, status, competition, query],
  );

  return (
    <div className="stack" style={{ ["--gap" as string]: "1rem" }}>
      <div className="mv-filters" role="group" aria-label="Filter forecasts">
        <div className="mv-filter-chips" role="group" aria-label="Filter by status">
          <FilterChip label="All" active={status === "all"} onClick={() => setStatus("all")} />
          {statuses.map((s) => (
            <FilterChip key={s} label={STATUS_LABELS[s]} active={status === s} onClick={() => setStatus(s)} />
          ))}
        </div>
        <label className="field mv-filter-field">
          Competition
          <select
            className="select"
            value={competition}
            onChange={(e) => setCompetition(e.target.value)}
          >
            <option value="all">All competitions</option>
            {competitions.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="field mv-filter-field">
          Team
          <input
            className="mv-filter-input"
            type="search"
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            placeholder="Filter by team…"
          />
        </label>
      </div>

      <p className="mv-filter-count small muted" role="status" aria-live="polite">
        Showing {filtered.length} of {artifacts.length} forecasts
      </p>

      {filtered.length === 0 ? (
        <EmptyState title="No forecasts match these filters">
          Adjust or clear the status, competition, or team filters to see sealed forecasts again.
        </EmptyState>
      ) : (
        <ul className="md-grid">
          {filtered.map((a) => (
            <li key={a.artifact_id}>
              <MatchCard artifact={a} superseded={supersededIds.has(a.artifact_id)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      className={`mv-filter-chip${active ? " is-active" : ""}`}
      aria-pressed={active}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function MatchCard({ artifact, superseded }: { artifact: ForecastArtifact; superseded: boolean }) {
  const { match, forecast, model, evaluation, status } = artifact;
  const scored = status === "scored" && evaluation;

  return (
    <a
      className="md-card"
      href={`#/forecast/${artifact.artifact_id}`}
      aria-label={`${match.home_team} versus ${match.away_team}, ${match.competition}, ${STATUS_LABELS[status]} forecast`}
    >
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
        <span><ClockIcon /> <span className="num">{utc(match.kickoff_utc)}</span>{kickoffRelative(match.kickoff_utc) && <> <span className="dim">({kickoffRelative(match.kickoff_utc)})</span></>}</span>
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

/** Compact 3-segment bar with an accessible summary, for the list. Whole-number
 *  labels that sum to 100 (widths stay exact from the raw probabilities). */
function MiniBar({ h, d, a, home, away }: { h: number; d: number; a: number; home: string; away: string }) {
  const [hw, dw, aw] = largestRemainder([h, d, a]);
  const label = `${home} ${hw}%, draw ${dw}%, ${away} ${aw}%`;
  return (
    <div className="probbar" style={{ ["--h" as string]: "26px" }}>
      <div className="probbar__track" role="img" aria-label={label}>
        <div className="probbar__seg probbar__seg--home" style={{ width: `${h * 100}%` }} aria-hidden><span>{hw}%</span></div>
        <div className="probbar__seg probbar__seg--draw" style={{ width: `${d * 100}%` }} aria-hidden><span>{dw}%</span></div>
        <div className="probbar__seg probbar__seg--away" style={{ width: `${a * 100}%` }} aria-hidden><span>{aw}%</span></div>
      </div>
    </div>
  );
}

function firstSentence(text: string | null): string {
  if (!text) return "";
  const dot = text.indexOf(". ");
  return dot > 0 ? text.slice(0, dot + 1) : text;
}
