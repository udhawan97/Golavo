import { useState } from "react";
import type { ResearchTeamAnalytics as Research } from "../lib/contract";
import { fetchResearchTeamAnalytics } from "../lib/api";
import { num } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { BlockSkeleton } from "./states";

export function ResearchTeamAnalyticsBody({ data }: { data: Research }) {
  const [teamId, setTeamId] = useState(data.teams[0]?.team_id ?? 0);
  const team = data.teams.find((item) => item.team_id === teamId) ?? data.teams[0];
  return (
    <details className="research-analytics">
      <summary>
        <span>
          <strong>{data.era} team event research</strong>
          <small>{data.coverage.matches.toLocaleString()} matches · {data.coverage.events.toLocaleString()} events</small>
        </span>
        <span className="chip chip--neutral">Historical · not a model input</span>
      </summary>
      <div className="stack research-analytics__body" style={{ ["--gap" as string]: ".9rem" }}>
        <div className="callout callout--info" role="note">
          <div>
            <div className="callout__title">Separate competition and era</div>
            <p>
              Team aggregates for {data.competition_name} {data.era} only. They are never mixed
              with current players, live matches, forecasts, or season simulations.
            </p>
          </div>
        </div>
        <label className="field research-team-select">Team
          <select
            className="select"
            value={team.team_id}
            onChange={(event) => setTeamId(Number(event.target.value))}
          >
            {data.teams.map((item) => (
              <option key={item.team_id} value={item.team_id}>{item.team}</option>
            ))}
          </select>
        </label>
        <div className="research-kpis" aria-label={`${team.team} historical research metrics`}>
          <Metric label="Pass completion" value={`${num(team.pass_completion_pct, 1)}%`} />
          <Metric label="Progressive passes / match" value={num(team.progressive_passes_per_match, 1)} />
          <Metric label="Shots / match" value={num(team.shots_per_match, 1)} />
          <Metric label="Goals / match" value={num(team.goals_per_match, 2)} />
          <Metric label="Progressive event runs / match" value={num(team.progressive_chains_per_match, 1)} />
          <Metric label="Research xT / match" value={num(team.research_xt_created_per_match, 3)} />
        </div>
        <details className="outlook-method">
          <summary>Methods, attribution, and limits</summary>
          <p><strong>Progressive pass:</strong> {data.methods.progressive_pass}.</p>
          <p><strong>Event-run proxy:</strong> {data.methods.chain_proxy}.</p>
          <p><strong>Research xT:</strong> {data.methods.research_xt}. This is not observed xG.</p>
          <p className="small dim">{data.provenance.attribution} {data.provenance.modifications}</p>
        </details>
      </div>
    </details>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="analytics-kpi">
      <span className="small muted">{label}</span><strong className="num">{value}</strong>
    </div>
  );
}

export function ResearchTeamAnalytics({ competitionId }: { competitionId: string }) {
  const state = useAsync(() => fetchResearchTeamAnalytics(competitionId), [competitionId]);
  if (state.status === "loading") return <BlockSkeleton lines={2} />;
  if (state.status === "error" || !state.data) return null;
  return <ResearchTeamAnalyticsBody data={state.data} />;
}
