import { useEffect, useMemo, useRef, useState } from "react";
import { fetchFollows, fetchSeasonOutlook } from "../lib/api";
import type { PickView, SeasonOutlook } from "../lib/contract";
import { LEAGUES } from "../lib/leagues";
import { loadFavoriteTeams, saveFavoriteTeams } from "../lib/favorite-teams";
import type { FavoriteTeam } from "../lib/favorite-teams";
import { pctWhole } from "../lib/format";
import { clubImportance, RUN_IN_LENGTH, topStake } from "../components/SeasonOutlook";
import { usePicks } from "../lib/picks";

const AVAILABLE = LEAGUES.filter((league) => league.seasonOutlook && league.competitionId);

export function MyTeams() {
  const [favorites, setFavorites] = useState(loadFavoriteTeams);
  const [competitionId, setCompetitionId] = useState(AVAILABLE[0]?.competitionId ?? "");
  const [outlooks, setOutlooks] = useState<Record<string, SeasonOutlook>>({});
  const [error, setError] = useState<string | null>(null);
  const [followed, setFollowed] = useState<Set<string>>(new Set());
  const picks = usePicks();
  const loading = useRef(new Set<string>());
  const selected = AVAILABLE.find((league) => league.competitionId === competitionId);

  useEffect(() => {
    const ids = new Set([competitionId, ...favorites.map((item) => item.competitionId)]);
    ids.forEach((id) => {
      if (!id || outlooks[id] || loading.current.has(id)) return;
      loading.current.add(id);
      void fetchSeasonOutlook(id).then(
        (value) => { loading.current.delete(id); setOutlooks((current) => ({ ...current, [id]: value })); },
        (reason) => { loading.current.delete(id); setError(reason instanceof Error ? reason.message : "Season outlook unavailable"); },
      );
    });
  }, [competitionId, favorites, outlooks]);

  useEffect(() => {
    const loadAllFollows = async () => {
      const ids = new Set<string>();
      let offset = 0;
      while (true) {
        const value = await fetchFollows("active", 0, 200, offset);
        value.items.forEach((item) => ids.add(item.canonical_match_id));
        offset += value.items.length;
        if (value.items.length === 0 || offset >= value.total) return ids;
      }
    };
    void loadAllFollows().then(
      (value) => setFollowed(value),
      (reason) => setError(reason instanceof Error ? reason.message : "Followed matches unavailable"),
    );
  }, []);

  const teams = useMemo(() => outlooks[competitionId]?.current_table.map((row) => row.team) ?? [], [competitionId, outlooks]);
  const add = (team: string) => {
    if (!selected || !selected.competitionId || favorites.some((item) => item.competitionId === selected.competitionId && item.team === team)) return;
    const next = [...favorites, { competitionId: selected.competitionId, leagueSlug: selected.slug, leagueName: selected.name, team }];
    saveFavoriteTeams(next); setFavorites(next);
  };
  const remove = (favorite: FavoriteTeam) => {
    const next = favorites.filter((item) => !(item.competitionId === favorite.competitionId && item.team === favorite.team));
    saveFavoriteTeams(next); setFavorites(next);
  };

  return <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
    <header><p className="eyebrow">Club room</p><h1>My Teams</h1><p className="dim">A local-only shortlist keyed by exact competition and team identity. It never changes a forecast or enables network access.</p></header>
    <section className="panel"><div className="panel__head"><h2>Add a club</h2></div><div className="panel__body controls">
      <label>League <select value={competitionId} onChange={(event) => setCompetitionId(event.target.value)}>{AVAILABLE.map((league) => <option key={league.competitionId} value={league.competitionId}>{league.name}</option>)}</select></label>
      <label>Team <select defaultValue="" key={competitionId} onChange={(event) => { if (event.target.value) add(event.target.value); event.target.value = ""; }}><option value="">Select…</option>{teams.map((team) => <option key={team} value={team}>{team}</option>)}</select></label>
    </div></section>
    {error && <p role="alert">{error}</p>}
    <section className="stack"><h2>Club room</h2>{favorites.length === 0 ? <div className="card card--pad"><p className="dim">Choose a club above to build your room.</p></div> : favorites.map((favorite) => <TeamCard key={`${favorite.competitionId}:${favorite.team}`} favorite={favorite} outlook={outlooks[favorite.competitionId]} followed={followed} picks={picks.byMatch} onRemove={() => remove(favorite)} />)}</section>
  </div>;
}

function TeamCard({ favorite, outlook, followed, picks, onRemove }: { favorite: FavoriteTeam; outlook?: SeasonOutlook; followed: Set<string>; picks: Map<string, PickView>; onRemove: () => void }) {
  const voice = outlook?.voices.find((item) => item.role === "voice");
  const projection = voice?.teams.find((item) => item.team === favorite.team);
  const standing = outlook?.current_table.find((item) => item.team === favorite.team);
  const fixtures = outlook?.remaining_fixtures.filter((item) => item.home_team === favorite.team || item.away_team === favorite.team).slice(0, RUN_IN_LENGTH) ?? [];
  const available = outlook?.status === "available";
  const missing = available && (!standing || !projection);
  const unavailable = outlook && !available;
  return <article className="card card--pad stack"><div className="controls" style={{ justifyContent: "space-between" }}><div><h3>{favorite.team}</h3><a className="small" href={`#/league/${favorite.leagueSlug}`}>{favorite.leagueName} ›</a></div><button type="button" className="btn btn--ghost" onClick={onRemove}>Remove</button></div>{!outlook && <p className="small dim">Loading local season outlook…</p>}{unavailable && <div className="callout callout--info"><div><div className="callout__title">Season outlook unavailable</div><p className="small">{outlook.reason ?? "Golavo cannot certify the local season outlook yet."} Your exact saved club identity was preserved.</p></div></div>}{missing && <div className="callout callout--info"><div><div className="callout__title">Exact team identity not present</div><p className="small">The active season no longer contains this exact club name. Golavo will not guess through a rename, promotion, or relegation; remove it and select the current identity.</p></div></div>}{available && standing && projection && <><div className="controls"><span><strong>{standing.points}</strong> pts</span><span>Projected {typeof projection.expected_points === "number" ? projection.expected_points.toFixed(1) : "—"} pts</span><span>Title {pctWhole(projection.title)}</span><span>Top four {pctWhole(projection.top_four)}</span><span>Relegation {pctWhole(projection.relegation)}</span></div><div><strong>The run-in</strong>{fixtures.length ? <ul>{fixtures.map((fixture) => { const importance = clubImportance(fixture, favorite.team); const stake = importance ? topStake(importance) : null; const pick = picks.get(fixture.match_id); return <li key={fixture.match_id}><a href={`#/match/${encodeURIComponent(fixture.match_id)}`}>{fixture.home_team} vs {fixture.away_team}</a>{importance?.score != null && stake ? <span className="small"> · {Math.round(importance.score * 100)}pp {stake.replace("_", " ")} swing</span> : <span className="small dim"> · stakes held back</span>}<span className="small"> · {followed.has(fixture.match_id) ? "Followed" : "Open to follow"} · {pick ? `Pick ${pick.record.user_pick.home_goals}–${pick.record.user_pick.away_goals}` : "Open to pick"}</span></li>; })}</ul> : <p className="small dim">No remaining fixtures in the active outlook.</p>}</div><p className="small dim">Descriptive simulation from {voice?.label}; never a sealed forecast, comparative evidence, or advice.</p></>}</article>;
}
