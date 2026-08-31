import { useEffect, useRef, useState } from "react";
import { handleExternalLinkClick } from "../lib/external-links";
import {
  fetchOutsideSignals,
  fetchSportmonksStatus,
  SPORTMONKS_RESET_EVENT,
  SportmonksApiError,
} from "../lib/sportmonks";
import type { OutsideSignals as OutsideSignalsResponse, SportmonksStatus } from "../lib/sportmonks";

type AvailablePlayerLens = Extract<OutsideSignalsResponse["player_lens"], { status: "available" }>;
type PlayerLensPlayer = AvailablePlayerLens["players"][number];
type PlayerMetric = PlayerLensPlayer["metrics"][number];

function percent(value: number): string {
  return `${value.toFixed(1)}%`;
}

function unavailableMessage(value: { status: string; message?: string }): string {
  return value.status === "disabled" ? "Disabled in Settings." : value.message ?? "Unavailable.";
}

export function OutsideSignals({
  matchId,
  home,
  away,
  complete = false,
}: {
  matchId: string;
  home: string;
  away: string;
  complete?: boolean;
}) {
  const [settings, setSettings] = useState<SportmonksStatus | null>(null);
  const [signalsState, setSignalsState] = useState<{
    value: OutsideSignalsResponse;
    generation: number;
  } | null>(null);
  const signals = signalsState?.value ?? null;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; status: number } | null>(null);
  const activeMatchId = useRef(matchId);
  const requestGeneration = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  activeMatchId.current = matchId;

  useEffect(() => {
    let live = true;
    activeRequest.current?.abort();
    activeRequest.current = null;
    requestGeneration.current += 1;
    setSignalsState(null);
    setError(null);
    setLoading(false);
    void fetchSportmonksStatus().then(
      (value) => { if (live) setSettings(value); },
      () => { if (live) setSettings(null); },
    );
    return () => {
      live = false;
      activeRequest.current?.abort();
      activeRequest.current = null;
    };
  }, [matchId]);

  useEffect(() => {
    const reset = () => {
      requestGeneration.current += 1;
      activeRequest.current?.abort();
      activeRequest.current = null;
      setSignalsState(null);
      setError(null);
      setLoading(false);
      setSettings(null);
    };
    window.addEventListener(SPORTMONKS_RESET_EVENT, reset);
    return () => window.removeEventListener(SPORTMONKS_RESET_EVENT, reset);
  }, []);

  const matchCapabilities = settings?.capabilities
    ? settings.capabilities.filter((capability) => (
        capability === "external_prediction"
        || capability === "external_odds"
        || capability === "player_lens"
      ))
    : settings?.enabled ? ["legacy_match_capability"] : [];
  if (!settings?.enabled || !matchCapabilities?.length) return null;
  const hasPlayerLens = matchCapabilities.includes("player_lens");
  const hasOutsideSignals = matchCapabilities.some((capability) => (
    capability === "external_prediction"
    || capability === "external_odds"
    || capability === "legacy_match_capability"
  ));
  const fetchLabel = complete
    ? hasPlayerLens && hasOutsideSignals
      ? "Fetch final player stats & outside signals"
      : hasPlayerLens
        ? "Fetch final player stats"
        : "Fetch outside signals"
    : hasPlayerLens && hasOutsideSignals
      ? "Fetch outside signals & player data"
      : hasPlayerLens
        ? "Fetch player data"
        : "Fetch outside signals";
  const refreshLabel = complete
    ? hasPlayerLens && hasOutsideSignals
      ? "Refresh final player stats & outside signals"
      : hasPlayerLens
        ? "Refresh final player stats"
        : "Refresh outside signals"
    : hasPlayerLens && hasOutsideSignals
      ? "Refresh outside signals & player data"
      : hasPlayerLens
        ? "Refresh player data"
        : "Refresh outside signals";

  const fetchNow = async () => {
    const requestedMatchId = matchId;
    const generation = ++requestGeneration.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const isCurrent = () => (
      activeMatchId.current === requestedMatchId
      && requestGeneration.current === generation
    );
    setLoading(true);
    setError(null);
    try {
      const value = await fetchOutsideSignals(requestedMatchId, controller.signal);
      if (isCurrent()) {
        setSignalsState((current) => ({
          value,
          generation: (current?.generation ?? 0) + 1,
        }));
      }
    } catch (reason) {
      if (controller.signal.aborted) return;
      const value = reason instanceof SportmonksApiError
        ? { message: reason.message, status: reason.status }
        : { message: reason instanceof Error ? reason.message : String(reason), status: 0 };
      if (!isCurrent()) return;
      // A failed foreground refresh cannot leave the prior revision presented
      // as current provider evidence. Keep no stale fallback in memory.
      setSignalsState(null);
      setError(value);
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
      if (isCurrent()) setLoading(false);
    }
  };
  const repairRequired = error?.status === 401 || error?.status === 403;
  const rateLimited = error?.status === 429;

  return (
    <section className="outside-signals panel" aria-labelledby="outside-signals-title">
      <div className="panel__head outside-signals__head">
        <div>
          <span className="upper">Third-party context</span>
          <h2 id="outside-signals-title">Outside signals</h2>
        </div>
        <span className="chip chip--neutral">Not a Golavo forecast</span>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: "1rem" }}>
        <p className="outside-signals__boundary">
          Sportmonks’ probabilities, lineups, player match statistics, and bookmaker prices sit
          beside this programme. They never enter Golavo’s models, verdict, seal, score,
          calibration, AI read, or exports.
        </p>

        {repairRequired ? (
          <p className="dim" role="alert">
            Sportmonks rejected the token or subscription access. Review the credential and plan
            in <a href="#/settings">Settings</a> before trying again.
          </p>
        ) : rateLimited ? (
          <p className="dim" role="alert">
            Sportmonks’s rate limit was reached. Golavo stopped requests for this panel; try again
            later by reopening the match.
          </p>
        ) : !settings.credential.configured ? (
          <p className="dim">
            Add your Sportmonks token in <a href="#/settings">Settings</a> to fetch outside signals.
          </p>
        ) : !signals ? (
          <div className="outside-signals__fetch">
            <button type="button" className="btn btn--primary" disabled={loading} onClick={() => void fetchNow()}>
              {loading
                ? "Fetching from Sportmonks…"
                : fetchLabel}
            </button>
            <span className="small dim">This click sends {home}, {away}, and the fixture date to Sportmonks.</span>
          </div>
        ) : (
          <>
            <div className="outside-signals__grid">
              <article className="outside-signal-card" aria-labelledby="sportmonks-prediction">
                <span className="upper">Provider prediction</span>
                <h3 id="sportmonks-prediction">Full-time result</h3>
                {signals.prediction.status === "available" ? (
                  <dl className="outside-signal-values">
                    <div><dt>{home}</dt><dd className="num">{percent(signals.prediction.percent.home)}</dd></div>
                    <div><dt>Draw</dt><dd className="num">{percent(signals.prediction.percent.draw)}</dd></div>
                    <div><dt>{away}</dt><dd className="num">{percent(signals.prediction.percent.away)}</dd></div>
                  </dl>
                ) : (
                  <p className="small dim">{unavailableMessage(signals.prediction)}</p>
                )}
              </article>

              <article className="outside-signal-card" aria-labelledby="sportmonks-odds">
                <span className="upper">Provider odds</span>
                <h3 id="sportmonks-odds">Match winner · decimal</h3>
                {signals.odds.status === "available" ? (
                  <div className="outside-odds-scroll">
                    <table className="outside-odds-table">
                      <thead><tr><th>Bookmaker</th><th>{home}</th><th>Draw</th><th>{away}</th><th>Provider update</th></tr></thead>
                      <tbody>
                        {signals.odds.bookmakers.map((book) => (
                          <tr key={book.bookmaker_id}>
                            <th scope="row">{book.bookmaker_name}</th>
                            <td className="num">{book.decimal.home.toFixed(2)}</td>
                            <td className="num">{book.decimal.draw.toFixed(2)}</td>
                            <td className="num">{book.decimal.away.toFixed(2)}</td>
                            <td>{book.updated_at_utc ?? "Unavailable"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="small dim">{unavailableMessage(signals.odds)}</p>
                )}
              </article>

              <PlayerLens
                key={`${signals.identity.provider_fixture_id}:${signalsState?.generation ?? 0}`}
                value={signals.player_lens}
                home={home}
                away={away}
                identity={signals.identity}
                fetchedAtUtc={signals.provenance.fetched_at_utc}
              />
            </div>

            <div className="outside-signals__provenance small dim">
              <span>
                Exact provider fixture {signals.identity.provider_fixture_id} · fetched{" "}
                {new Date(signals.provenance.fetched_at_utc).toLocaleString()} · raw response not stored
              </span>
              {signals.identity.provider_league_id !== null && <span>{signals.identity.provider_league ?? "League"} <code>{signals.identity.provider_league_id}</code></span>}
              {signals.identity.provider_season_id !== null && <span>{signals.identity.provider_season ?? "Season"} <code>{signals.identity.provider_season_id}</code></span>}
              <button type="button" className="btn btn--ghost" disabled={loading} onClick={() => void fetchNow()}>
                {loading ? "Refreshing…" : refreshLabel}
              </button>
            </div>
          </>
        )}

        {error && !repairRequired && !rateLimited && (
          <p className="small dim" role="alert">Outside signals unavailable: {error.message}</p>
        )}
        <p className="small dim outside-signals__note">
          Informational only. Prices and provider models can be incomplete, delayed, or wrong. No
          bookmaker links, affiliate tracking, staking advice, or bet placement. A single match is
          not a multi-match player-form series. Source:{" "}
          <a href={settings.provider.docs_url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>Sportmonks API v3</a>
          {" · "}<a href={settings.provider.terms_url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>terms</a>.
        </p>
      </div>
    </section>
  );
}

function PlayerLens({
  value,
  home,
  away,
  identity,
  fetchedAtUtc,
}: {
  value: OutsideSignalsResponse["player_lens"];
  home: string;
  away: string;
  identity: OutsideSignalsResponse["identity"];
  fetchedAtUtc: string;
}) {
  if (value.status !== "available") return <article className="outside-signal-card outside-signal-card--wide" aria-labelledby="sportmonks-player-lens"><span className="upper">Provider player data</span><h3 id="sportmonks-player-lens">Player Lens</h3><p className="small dim">{unavailableMessage(value)}</p></article>;
  return (
    <AvailablePlayerLens
      value={value}
      home={home}
      away={away}
      identity={identity}
      fetchedAtUtc={fetchedAtUtc}
    />
  );
}

function AvailablePlayerLens({
  value,
  home,
  away,
  identity,
  fetchedAtUtc,
}: {
  value: AvailablePlayerLens;
  home: string;
  away: string;
  identity: OutsideSignalsResponse["identity"];
  fetchedAtUtc: string;
}) {
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const selectedPlayerButtonRef = useRef<HTMLButtonElement | null>(null);
  const focusAfterCloseRef = useRef<HTMLButtonElement | null>(null);
  const selectedPlayer = value.players.find((player) => player.player_id === selectedPlayerId) ?? null;
  const state = value.lineup_state === "confirmed"
    ? "Confirmed lineup"
    : value.lineup_state === "predicted"
      ? "Provider-predicted lineup"
      : "Lineup confirmation unavailable";
  const teamEntries = [
    { localName: home, providerName: identity.provider_home_team, teamId: identity.provider_home_team_id },
    { localName: away, providerName: identity.provider_away_team, teamId: identity.provider_away_team_id },
  ];
  const selectedTeam = selectedPlayer
    ? teamEntries.find(({ teamId }) => teamId === selectedPlayer.team_id)?.providerName ?? null
    : null;

  useEffect(() => {
    if (selectedPlayerId !== null || !focusAfterCloseRef.current) return;
    focusAfterCloseRef.current.focus();
    focusAfterCloseRef.current = null;
  }, [selectedPlayerId]);

  const closeDossier = () => {
    focusAfterCloseRef.current = selectedPlayerButtonRef.current;
    setSelectedPlayerId(null);
  };

  return <article className="outside-signal-card outside-signal-card--wide player-lens" aria-labelledby="sportmonks-player-lens">
    <div className="player-lens__intro">
      <div>
        <span className="upper">Provider player data</span>
        <h3 id="sportmonks-player-lens">Player Lens</h3>
        <p className="small"><strong>{state}</strong> · {value.coverage.players_with_metrics} of {value.coverage.player_count} players have supplied match statistics.</p>
      </div>
      <p className="player-lens__instruction small dim">Choose a player to open a selected-match dossier. Nothing is fetched or saved when it opens.</p>
    </div>
    <div className="two-col player-lens__teams">{teamEntries.map(({ localName, teamId }) => {
      const teamPlayers = value.players.filter((player) => player.team_id === teamId);
      return <section key={teamId} aria-labelledby={`player-lens-team-${teamId}`}>
      <h4 id={`player-lens-team-${teamId}`}>{localName}</h4>
      {teamPlayers.length === 0 ? <p className="small dim">No identity-safe lineup rows were supplied for this team.</p> : <ol className="plain-list player-lens__roster">{teamPlayers.map((player) => {
        const selected = player.player_id === selectedPlayerId;
        return <li key={player.player_id}>
          <button
            type="button"
            className={`player-lens__player${selected ? " is-selected" : ""}`}
            aria-expanded={selected}
            aria-controls={selected ? `player-match-dossier-${player.player_id}` : undefined}
            ref={selected ? selectedPlayerButtonRef : null}
            onClick={() => setSelectedPlayerId(selected ? null : player.player_id)}
          >
            <span className="player-lens__number num" aria-hidden>{player.jersey_number ?? "—"}</span>
            <span className="player-lens__player-copy">
              <strong>{player.name}</strong>
              <span className="small dim">{player.participation === "starter" ? "Starter" : "Bench"} · {player.metrics.length} supplied stats</span>
            </span>
            <span className="player-lens__open small">{selected ? "Close" : "Open dossier"}</span>
          </button>
        </li>;
      })}</ol>}
    </section>;
    })}</div>
    {selectedPlayer && selectedTeam ? (
      <PlayerMatchDossier
        player={selectedPlayer}
        team={selectedTeam}
        lineupState={value.lineup_state}
        fixtureId={identity.provider_fixture_id}
        fetchedAtUtc={fetchedAtUtc}
        onClose={closeDossier}
      />
    ) : null}
    <p className="small dim player-lens__boundary">Missing means unavailable, never zero. Sportmonks player IDs and metric type IDs are preserved; no cross-league ranking or Golavo inference is made.</p>
  </article>;
}

function PlayerMatchDossier({
  player,
  team,
  lineupState,
  fixtureId,
  fetchedAtUtc,
  onClose,
}: {
  player: PlayerLensPlayer;
  team: string;
  lineupState: AvailablePlayerLens["lineup_state"];
  fixtureId: number;
  fetchedAtUtc: string;
  onClose: () => void;
}) {
  const dossierRef = useRef<HTMLElement | null>(null);
  const groups = groupPlayerMetrics(player.metrics);
  const lineupLabel = lineupState === "confirmed"
    ? "Confirmed lineup"
    : lineupState === "predicted"
      ? "Provider-predicted lineup"
      : "Confirmation unavailable";

  useEffect(() => {
    dossierRef.current?.focus();
  }, [player.player_id]);

  return (
    <section
      ref={dossierRef}
      id={`player-match-dossier-${player.player_id}`}
      className="player-dossier"
      aria-labelledby={`player-match-dossier-title-${player.player_id}`}
      tabIndex={-1}
    >
      <header className="player-dossier__hero">
        <div className="player-dossier__shirt" role="img" aria-label={player.jersey_number === null ? "Jersey number unavailable" : `Jersey number ${player.jersey_number}`}>
          <span aria-hidden>{player.jersey_number ?? "—"}</span>
        </div>
        <div className="player-dossier__title">
          <span className="upper">Selected-match dossier · exact provider identity</span>
          <h4 id={`player-match-dossier-title-${player.player_id}`}>{player.name}</h4>
          <p>{team} · {player.participation === "starter" ? "Starter" : "Bench"}</p>
        </div>
        <button type="button" className="btn btn--ghost player-dossier__close" onClick={onClose}>Close dossier</button>
      </header>

      <dl className="player-dossier__identity" aria-label="Provider identity">
        <IdentityField label="Player ID" value={player.player_id} />
        <IdentityField label="Lineup ID" value={player.lineup_id} />
        <IdentityField label="Team ID" value={player.team_id} />
        <IdentityField label="Fixture ID" value={fixtureId} />
        <IdentityField label="Position ID" value={player.position_id ?? "Unavailable"} />
        <IdentityField label="Lineup state" value={lineupLabel} />
      </dl>

      <div className="player-dossier__evidence">
        <div className="player-dossier__evidence-head">
          <div>
            <span className="upper">Provider-supplied record</span>
            <h5>This fixture only</h5>
          </div>
          <span className="chip chip--neutral">Fetched {new Date(fetchedAtUtc).toLocaleString()}</span>
        </div>
        {groups.length > 0 ? (
          <div className="player-dossier__groups">{groups.map(([group, metrics], groupIndex) => {
            const headingId = `player-${player.player_id}-metric-group-${groupIndex}`;
            return (
              <section key={group} className="player-dossier__group" aria-labelledby={headingId}>
                <h6 id={headingId}>{group}</h6>
                <dl>{metrics.map((metric) => (
                  <div key={metric.type_id}>
                    <dt>{metric.label}<small>Type {metric.type_id}</small></dt>
                    <dd className="num">{formatPlayerMetric(metric.value, metric.unit)}</dd>
                  </div>
                ))}</dl>
              </section>
            );
          })}</div>
        ) : (
          <p className="small dim">No match statistics were supplied for this player. Their absence is not a zero.</p>
        )}
      </div>

      <div className="player-dossier__limits">
        <strong>One match, held in memory</strong>
        <p className="small">This is not a career profile, current-form series, player ranking, or Golavo assessment. The response is not persisted and cannot enter a model, forecast, seal, settlement, score, calibration, AI read, or export.</p>
      </div>
    </section>
  );
}

function IdentityField({ label, value }: { label: string; value: string | number }) {
  return <div><dt>{label}</dt><dd className="mono">{value}</dd></div>;
}

function groupPlayerMetrics(metrics: PlayerMetric[]): Array<[string, PlayerMetric[]]> {
  const groups = new Map<string, PlayerMetric[]>();
  for (const metric of metrics) {
    const group = metric.group ? `${metric.group[0].toUpperCase()}${metric.group.slice(1)}` : "Match summary";
    const current = groups.get(group);
    if (current) current.push(metric);
    else groups.set(group, [metric]);
  }
  return [...groups];
}

function formatPlayerMetric(
  value: number | boolean,
  unit: "count" | "percent" | "minutes" | "boolean" | "provider_score",
): string {
  if (unit === "boolean") return value ? "Yes" : "No";
  if (typeof value !== "number") return "Unavailable";
  if (unit === "percent") return `${value.toFixed(1)}%`;
  if (unit === "minutes") return `${value} min`;
  if (unit === "provider_score") return `${value} provider score`;
  return `${value} count`;
}
