import { useMemo, useState } from "react";
import { DATA_SOURCE, fetchPicksSummary } from "../lib/api";
import type { PickView, PicksSummary } from "../lib/contract";
import { useDataGenerationRevision } from "../lib/data-refresh-context";
import { cumulativeSeries, seasonTable, streaks, usePicks } from "../lib/picks";
import { useAsync } from "../lib/hooks";
import { PointsChart } from "../components/PointsChart";
import { PitchIcon, ShieldCheckIcon, TrophyIcon } from "../components/icons";
import { StatTile, TrustStrip } from "../components/primitives";
import { BlockSkeleton, EmptyState, ErrorState } from "../components/states";
import { utcDate } from "../lib/format";

type WindowFilter = "all" | "month" | "week";

export function MySeason() {
  const generationRevision = useDataGenerationRevision();
  const summaryState = useAsync(() => fetchPicksSummary(), [generationRevision]);
  const picks = usePicks();
  const [window, setWindow] = useState<WindowFilter>("all");
  const [competition, setCompetition] = useState("all");
  // Memoised because the `: []` branch would otherwise mint a fresh array every
  // render, changing the dep of every memo below it.
  const views = useMemo(
    () => (picks.state.status === "ready" ? picks.state.data : []),
    [picks.state],
  );
  const competitions = [...new Set(views.map((view) => view.record.match.competition).filter(Boolean))].sort();
  const filtered = useMemo(() => {
    const cutoff = window === "week" ? Date.now() - 7 * 86_400_000 : window === "month" ? Date.now() - 30 * 86_400_000 : 0;
    return views.filter((view) =>
      Date.parse(view.record.match.kickoff_utc) >= cutoff &&
      (competition === "all" || view.record.match.competition === competition),
    );
  }, [competition, views, window]);

  if (summaryState.status === "loading" || picks.state.status === "loading") return <BlockSkeleton lines={7} />;
  if (summaryState.status === "error") return <ErrorState error={summaryState.error} />;
  if (picks.state.status === "error") return <ErrorState error={picks.state.error} />;
  const summary = filtered.length === views.length ? summaryState.data : summaryFor(filtered);
  const preview = DATA_SOURCE === "mock" || views.some((view) => view.preview);

  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <header className="season-head">
        <div><div className="eyebrow"><PitchIcon /> MY SEASON</div><h1>You vs the models</h1><p className="dim">You against five deterministic model families — scored only on the matches you call.</p></div>
        <TrophyIcon size={34} />
      </header>
      {preview && <div className="callout callout--info">Practice mode — picks are stored on this device and never count.</div>}
      <TrustStrip items={[
        { icon: <ShieldCheckIcon />, label: "Picks lock at kickoff" },
        { label: "Points come from final results only" },
        { label: "The models play by the same rules" },
      ]} />
      <div className="season-filters">
        <div className="mv-filter-chips" role="group" aria-label="Season window">
          {([['all', 'All'], ['month', 'Last month'], ['week', 'Last week']] as const).map(([value, label]) => <button key={value} type="button" className={`mv-filter-chip${window === value ? " is-active" : ""}`} aria-pressed={window === value} onClick={() => setWindow(value)}>{label}</button>)}
        </div>
        <label className="small muted">Competition <select value={competition} onChange={(event) => setCompetition(event.target.value)}><option value="all">All competitions</option>{competitions.map((name) => <option key={name!} value={name!}>{name}</option>)}</select></label>
      </div>
      {filtered.length === 0 ? (
        <EmptyState title="No picks yet">
          Pick a score on any upcoming match and the race begins. <a href="#/">Find an upcoming match ›</a>
        </EmptyState>
      ) : (
        <>
          <section className="stat-grid" aria-label="Your season totals">
            <StatTile value={summary.user.total} label="Points" tone="gold" />
            <StatTile value={summary.user.exact / 3} label="Exact scores" />
            <StatTile value={summary.user.outcome} label="Winners called" />
            <StatTile value={summary.user.bonus} label="Bonuses" />
            <StatTile value={summary.streak.current} label="Streak" hint={`Best ${summary.streak.best}`} />
          </section>
          <Leaderboard summary={summary} />
          {summary.series.length > 0 && (
            <section className="panel">
              <div className="panel__head"><h2>Points race</h2></div>
              <div className="panel__body"><PointsChart series={summary.series} /></div>
            </section>
          )}
          <History views={filtered} />
        </>
      )}
    </div>
  );
}

function Leaderboard({ summary }: { summary: PicksSummary }) {
  return (
    <section className="panel">
      <div className="panel__head"><h2>Standings</h2></div>
      <div className="table-wrap">
        <table className="grid">
          <thead><tr><th>Rival</th><th>Points</th><th>Exact</th><th>Winners</th><th>Bonus</th></tr></thead>
          <tbody>{seasonTable(summary).map((row) => (
            <tr key={row.id} className={row.user ? "season-you" : ""}>
              <th scope="row">{row.label}</th><td className="num">{row.total}</td>
              <td className="num">{row.id === "elo_ordlogit" || row.id === "climatological" ? "—" : row.exact / 3}</td>
              <td className="num">{row.outcome}</td><td className="num">{row.user ? row.bonus : "—"}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p className="small dim" style={{ padding: "0 1rem" }}>† Winner-only rivals do not make exact-score calls.</p>
    </section>
  );
}

function History({ views }: { views: PickView[] }) {
  const ordered = [...views].sort((a, b) =>
    b.record.match.kickoff_utc.localeCompare(a.record.match.kickoff_utc),
  );
  return (
    <section className="panel">
      <div className="panel__head"><h2>Pick history</h2></div>
      <div className="table-wrap">
        <table className="grid">
          <thead><tr><th>Match</th><th>Date</th><th>Your call</th><th>Final</th><th>Points</th></tr></thead>
          <tbody>{ordered.map((view) => (
            <tr key={view.record.pick_id ?? view.record.match.match_id}>
              <th scope="row"><details><summary>{view.record.match.home_team} v {view.record.match.away_team}</summary><div className="history-rivals">{view.scoring?.rivals.map((row) => <span key={row.family}>{row.family.replaceAll("_", " ")} +{row.total}</span>) ?? "Waiting for full time"}</div></details></th>
              <td>{utcDate(view.record.match.kickoff_utc)}</td>
              <td className="num">{view.record.user_pick.home_goals}–{view.record.user_pick.away_goals}</td>
              <td className="num">{view.result ? `${view.result.home_goals}–${view.result.away_goals}` : "—"}</td>
              <td className="num">{view.scoring ? view.scoring.user.total : "—"}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

function summaryFor(views: PickView[]): PicksSummary {
  const scored = views.filter((view) => view.status === "scored" && view.scoring && view.result);
  const user = { total: 0, exact: 0, outcome: 0, bonus: 0 };
  const rivalMap = new Map<string, PicksSummary["rivals"][number]>();
  for (const view of scored) {
    for (const key of ["total", "exact", "outcome", "bonus"] as const) user[key] += view.scoring!.user[key];
    for (const row of view.scoring!.rivals) { const total = rivalMap.get(row.family) ?? { family: row.family, total: 0, exact: 0, outcome: 0 }; total.total += row.total; total.exact += row.exact; total.outcome += row.outcome; rivalMap.set(row.family, total); }
  }
  return { schema_version: "0.1.0", season: null, counts: { draft: views.filter((v) => v.status === "draft").length, locked: views.filter((v) => v.status === "locked").length, scored: scored.length, void: views.filter((v) => v.status === "void").length }, user, rivals: [...rivalMap.values()], series: cumulativeSeries(views), accuracy: { exact: scored.length ? scored.filter((v) => v.scoring!.user.exact > 0).length / scored.length : 0, winner: scored.length ? scored.filter((v) => v.scoring!.user.outcome > 0).length / scored.length : 0 }, streak: streaks(views), goal_diff_mae: 0 };
}
