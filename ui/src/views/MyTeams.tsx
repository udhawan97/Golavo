import { useEffect, useMemo, useRef, useState } from "react";
import { fetchSeasonOutlook } from "../lib/api";
import type { PickView, SeasonOutlook } from "../lib/contract";
import { LEAGUES } from "../lib/leagues";
import {
  favoriteTeamsTransferJson,
  FAVORITE_TEAMS_TRANSFER_MAX_BYTES,
  loadFavoriteTeams,
  parseFavoriteTeamsTransfer,
  saveFavoriteTeams,
} from "../lib/favorite-teams";
import type { FavoriteTeam, FavoriteTeamIdentity } from "../lib/favorite-teams";
import { pctWhole } from "../lib/format";
import {
  clubImportance,
  projectionCoverageCaveat,
  RUN_IN_LENGTH,
  topStake,
} from "../components/SeasonOutlook";
import { FollowButton } from "../components/FollowButton";
import { TeamProjectionChange } from "../components/TeamProjectionChange";
import { useFollows } from "../lib/follow-context";
import { usePicks } from "../lib/picks";
import { teamDossierHref } from "../lib/team-route";

const AVAILABLE = LEAGUES.filter((league) => league.seasonOutlook && league.competitionId);

interface ImportRejection extends FavoriteTeamIdentity {
  reason: string;
}

interface ImportPreview {
  fileName: string;
  accepted: FavoriteTeam[];
  rejected: ImportRejection[];
}

function downloadJson(name: string, value: string): void {
  const url = URL.createObjectURL(new Blob([value], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function MyTeams() {
  const [favorites, setFavorites] = useState(loadFavoriteTeams);
  const [competitionId, setCompetitionId] = useState(AVAILABLE[0]?.competitionId ?? "");
  const [outlooks, setOutlooks] = useState<Record<string, SeasonOutlook>>({});
  const [error, setError] = useState<string | null>(null);
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
  const [replaceImport, setReplaceImport] = useState(false);
  const picks = usePicks();
  const follows = useFollows();
  const loading = useRef(new Set<string>());
  const importRequestGeneration = useRef(0);
  const selected = AVAILABLE.find((league) => league.competitionId === competitionId);

  useEffect(() => {
    const ids = new Set([competitionId, ...favorites.map((item) => item.competitionId)]);
    ids.forEach((id) => {
      if (!id || outlooks[id] || loading.current.has(id)) return;
      loading.current.add(id);
      void fetchSeasonOutlook(id).then(
        (value) => {
          loading.current.delete(id);
          setOutlooks((current) => ({ ...current, [id]: value }));
        },
        (reason) => {
          loading.current.delete(id);
          setError(reason instanceof Error ? reason.message : "Season outlook unavailable");
        },
      );
    });
  }, [competitionId, favorites, outlooks]);

  const teams = useMemo(
    () => outlooks[competitionId]?.current_table.map((row) => row.team) ?? [],
    [competitionId, outlooks],
  );

  const add = (team: string) => {
    if (!selected?.competitionId
      || favorites.some((item) => item.competitionId === selected.competitionId && item.team === team)) return;
    const next = [...favorites, {
      competitionId: selected.competitionId,
      leagueSlug: selected.slug,
      leagueName: selected.name,
      team,
    }];
    saveFavoriteTeams(next);
    setFavorites(next);
  };

  const remove = (favorite: FavoriteTeam) => {
    const next = favorites.filter(
      (item) => !(item.competitionId === favorite.competitionId && item.team === favorite.team),
    );
    saveFavoriteTeams(next);
    setFavorites(next);
  };

  const inspectImport = async (file: File) => {
    const generation = ++importRequestGeneration.current;
    setError(null);
    setImportPreview(null);
    setReplaceImport(false);
    try {
      if (file.size > FAVORITE_TEAMS_TRANSFER_MAX_BYTES) {
        throw new Error("My Teams file is larger than 64 KiB");
      }
      const transfer = parseFavoriteTeamsTransfer(await file.text());
      const competitionIds = [...new Set(transfer.favorites.map((item) => item.competitionId))];
      const fetched = await Promise.all(competitionIds.map(async (id) => {
        if (outlooks[id]) return [id, outlooks[id]] as const;
        if (!AVAILABLE.some((league) => league.competitionId === id)) return [id, null] as const;
        try { return [id, await fetchSeasonOutlook(id)] as const; }
        catch { return [id, null] as const; }
      }));
      const checkedOutlooks = Object.fromEntries(fetched);
      const accepted: FavoriteTeam[] = [];
      const rejected: ImportRejection[] = [];
      for (const identity of transfer.favorites) {
        const league = AVAILABLE.find((item) => item.competitionId === identity.competitionId);
        const outlook = checkedOutlooks[identity.competitionId];
        if (!league) {
          rejected.push({ ...identity, reason: "Competition is not in the current season-outlook catalog." });
        } else if (!outlook || outlook.status !== "available") {
          rejected.push({ ...identity, reason: "The current local outlook cannot verify this club." });
        } else if (!outlook.current_table.some((row) => row.team === identity.team)) {
          rejected.push({ ...identity, reason: "Exact team identity is absent from the current table." });
        } else {
          accepted.push({
            ...identity,
            leagueSlug: league.slug,
            leagueName: league.name,
          });
        }
      }
      if (importRequestGeneration.current !== generation) return;
      setOutlooks((current) => ({
        ...current,
        ...Object.fromEntries(fetched.filter((entry): entry is readonly [string, SeasonOutlook] => entry[1] !== null)),
      }));
      setImportPreview({ fileName: file.name, accepted, rejected });
    } catch (reason) {
      if (importRequestGeneration.current === generation) {
        setError(reason instanceof Error ? reason.message : "My Teams import could not be inspected");
      }
    }
  };

  const applyImport = () => {
    if (!importPreview) return;
    const next = replaceImport
      ? importPreview.accepted
      : [...favorites, ...importPreview.accepted.filter((incoming) => !favorites.some(
        (current) => current.competitionId === incoming.competitionId && current.team === incoming.team,
      ))];
    saveFavoriteTeams(next);
    setFavorites(next);
    setImportPreview(null);
    setReplaceImport(false);
  };

  return <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
    <header>
      <p className="eyebrow">Club room</p>
      <h1>My Teams</h1>
      <p className="dim">A local-only shortlist keyed by exact competition and team identity. It never changes a forecast or enables network access.</p>
    </header>
    <section className="panel">
      <div className="panel__head"><h2>Add a club</h2></div>
      <div className="panel__body controls">
        <label>League <select className="select" value={competitionId} onChange={(event) => setCompetitionId(event.target.value)}>{AVAILABLE.map((league) => <option key={league.competitionId} value={league.competitionId}>{league.name}</option>)}</select></label>
        <label>Team <select className="select" defaultValue="" key={competitionId} onChange={(event) => { if (event.target.value) add(event.target.value); event.target.value = ""; }}><option value="">Select…</option>{teams.map((team) => <option key={team} value={team}>{team}</option>)}</select></label>
      </div>
    </section>
    <section className="panel">
      <div className="panel__head"><h2>Move My Teams</h2></div>
      <div className="panel__body stack">
        <p className="small dim">The portable file contains only exact competition and team identities. An import is previewed against this installation’s current local outlooks before anything is saved.</p>
        <div className="controls">
          <button className="btn btn--ghost" type="button" onClick={() => {
            try { downloadJson("golavo-my-teams.json", favoriteTeamsTransferJson(favorites)); }
            catch (reason) { setError(reason instanceof Error ? reason.message : "My Teams export failed"); }
          }}>Export My Teams</button>
          <label className="btn btn--ghost file-picker">Preview import<input className="visually-hidden" type="file" accept="application/json,.json" onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void inspectImport(file);
            event.target.value = "";
          }} /></label>
        </div>
        {importPreview && <div className="callout callout--info"><div className="stack">
          <div className="callout__title">Import preview · {importPreview.fileName}</div>
          <p className="small">Accepted: {importPreview.accepted.length} · Rejected: {importPreview.rejected.length}. No favorites have changed.</p>
          {importPreview.accepted.length > 0 && <div><strong className="small">Verified clubs</strong><ul>{importPreview.accepted.map((item) => <li key={`${item.competitionId}:${item.team}`}>{item.team} · {item.leagueName}</li>)}</ul></div>}
          {importPreview.rejected.length > 0 && <div><strong className="small">Rejected identities</strong><ul>{importPreview.rejected.map((item) => <li key={`${item.competitionId}:${item.team}`}>{item.team} · <span className="dim">{item.reason}</span></li>)}</ul></div>}
          <label className="small"><input type="checkbox" checked={replaceImport} onChange={(event) => setReplaceImport(event.target.checked)} /> Replace the current shortlist instead of merging verified clubs</label>
          <div className="controls"><button className="btn btn--primary" type="button" onClick={applyImport}>Apply verified clubs</button><button className="btn btn--ghost" type="button" onClick={() => { setImportPreview(null); setReplaceImport(false); }}>Cancel</button></div>
        </div></div>}
      </div>
    </section>
    {(error || follows.error) && <p role="alert">{error ?? follows.error?.message}</p>}
    <section className="stack">
      <h2>Club room</h2>
      {favorites.length === 0
        ? <div className="card card--pad"><p className="dim">Choose a club above to build your room.</p></div>
        : favorites.map((favorite) => <TeamCard key={`${favorite.competitionId}:${favorite.team}`} favorite={favorite} outlook={outlooks[favorite.competitionId]} picks={picks.byMatch} onRemove={() => remove(favorite)} />)}
    </section>
  </div>;
}

function TeamCard({ favorite, outlook, picks, onRemove }: {
  favorite: FavoriteTeam;
  outlook?: SeasonOutlook;
  picks: Map<string, PickView>;
  onRemove: () => void;
}) {
  const voice = outlook?.voices.find((item) => item.role === "voice");
  const projection = voice?.teams.find((item) => item.team === favorite.team);
  const standing = outlook?.current_table.find((item) => item.team === favorite.team);
  const fixtures = outlook?.remaining_fixtures
    .filter((item) => item.home_team === favorite.team || item.away_team === favorite.team)
    .slice(0, RUN_IN_LENGTH) ?? [];
  const available = outlook?.status === "available";
  const missing = available && (!standing || !projection);
  const unavailable = outlook && !available;
  return <article className="card card--pad stack">
    <div className="controls" style={{ justifyContent: "space-between" }}><div><h3><a href={teamDossierHref(favorite.competitionId, favorite.team)}>{favorite.team}</a></h3><a className="small" href={`#/league/${favorite.leagueSlug}`}>{favorite.leagueName} ›</a></div><button type="button" className="btn btn--ghost" onClick={onRemove}>Remove</button></div>
    {!outlook && <p className="small dim">Loading local season outlook…</p>}
    {unavailable && <div className="callout callout--info"><div><div className="callout__title">Season outlook unavailable</div><p className="small">{outlook.reason ?? "Golavo cannot certify the local season outlook yet."} Your exact saved club identity was preserved.</p></div></div>}
    {missing && <div className="callout callout--info"><div><div className="callout__title">Exact team identity not present</div><p className="small">The active season no longer contains this exact club name. Golavo will not guess through a rename, promotion, or relegation; remove it and select the current identity.</p></div></div>}
    {available && standing && projection && voice && <>
      <div className="controls"><span><strong>{standing.points}</strong> pts · {standing.position}{standing.position === 1 ? "st" : standing.position === 2 ? "nd" : standing.position === 3 ? "rd" : "th"}</span><span>Projected {typeof projection.expected_points === "number" ? projection.expected_points.toFixed(1) : "—"} pts</span><span>Title {pctWhole(projection.title)}</span><span>Top four {pctWhole(projection.top_four)}</span><span>Relegation {pctWhole(projection.relegation)}</span></div>
      <TeamProjectionChange outlook={outlook} voice={voice} projection={projection} />
      {projectionCoverageCaveat(projection) && <p className="small dim">{projectionCoverageCaveat(projection)}</p>}
      <div><strong>The run-in</strong>{fixtures.length ? <ul>{fixtures.map((fixture) => {
        const importance = clubImportance(fixture, favorite.team);
        const stake = importance ? topStake(importance) : null;
        const pick = picks.get(fixture.match_id);
        return <li key={fixture.match_id}><a href={`#/match/${encodeURIComponent(fixture.match_id)}`}>{fixture.home_team} vs {fixture.away_team}</a>{importance?.score != null && stake ? <span className="small"> · {Math.round(importance.score * 100)}pp {stake.replace("_", " ")} swing</span> : <span className="small dim"> · stakes held back</span>}<span className="small"> · {pick ? `Pick ${pick.record.user_pick.home_goals}–${pick.record.user_pick.away_goals}` : "Open to pick"}</span><FollowButton matchId={fixture.match_id} compact /></li>;
      })}</ul> : <p className="small dim">No remaining fixtures in the active outlook.</p>}</div>
      <p className="small dim">Descriptive simulation from {voice.label}; never a sealed forecast, comparative evidence, or advice. As of {outlook.as_of_utc}. Sources: {outlook.provenance.source_ids.join(", ") || "unavailable"}.</p>
    </>}
  </article>;
}
