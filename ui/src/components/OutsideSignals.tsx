import { useEffect, useRef, useState } from "react";
import { handleExternalLinkClick } from "../lib/external-links";
import {
  fetchOutsideSignals,
  fetchSportmonksStatus,
  SPORTMONKS_RESET_EVENT,
  SportmonksApiError,
} from "../lib/sportmonks";
import type { OutsideSignals as OutsideSignalsResponse, SportmonksStatus } from "../lib/sportmonks";

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
  const [signals, setSignals] = useState<OutsideSignalsResponse | null>(null);
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
    setSignals(null);
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
      setSignals(null);
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
      if (isCurrent()) setSignals(value);
    } catch (reason) {
      if (controller.signal.aborted) return;
      const value = reason instanceof SportmonksApiError
        ? { message: reason.message, status: reason.status }
        : { message: reason instanceof Error ? reason.message : String(reason), status: 0 };
      if (!isCurrent()) return;
      if (value.status === 401 || value.status === 403 || value.status === 429) {
        setSignals(null);
      }
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
                value={signals.player_lens}
                home={home}
                away={away}
                homeTeamId={signals.identity.provider_home_team_id}
                awayTeamId={signals.identity.provider_away_team_id}
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
  homeTeamId,
  awayTeamId,
}: {
  value: OutsideSignalsResponse["player_lens"];
  home: string;
  away: string;
  homeTeamId: number;
  awayTeamId: number;
}) {
  if (value.status !== "available") return <article className="outside-signal-card outside-signal-card--wide" aria-labelledby="sportmonks-player-lens"><span className="upper">Provider player data</span><h3 id="sportmonks-player-lens">Player Lens</h3><p className="small dim">{unavailableMessage(value)}</p></article>;
  const state = value.lineup_state === "confirmed"
    ? "Confirmed lineup"
    : value.lineup_state === "predicted"
      ? "Provider-predicted lineup"
      : "Lineup confirmation unavailable";
  return <article className="outside-signal-card outside-signal-card--wide" aria-labelledby="sportmonks-player-lens">
    <span className="upper">Provider player data</span>
    <h3 id="sportmonks-player-lens">Player Lens</h3>
    <p className="small"><strong>{state}</strong> · {value.coverage.players_with_metrics} of {value.coverage.player_count} players have supplied match statistics.</p>
    <div className="two-col">{[[home, homeTeamId], [away, awayTeamId]].map(([team, teamId]) => {
      const teamPlayers = value.players.filter((player) => player.team_id === teamId);
      return <div key={teamId}>
      <h4>{team}</h4>
      {teamPlayers.length === 0 ? <p className="small dim">No identity-safe lineup rows were supplied for this team.</p> : <ol className="plain-list">{teamPlayers.map((player) => <li key={player.player_id}>
        <details>
          <summary><strong>{player.jersey_number === null ? "" : `${player.jersey_number} · `}{player.name}</strong> <span className="small dim">{player.participation === "starter" ? "starter" : "bench"} · {player.metrics.length} stats</span></summary>
          {player.metrics.length > 0 ? <dl className="outside-signal-values">{player.metrics.map((metric) => <div key={metric.type_id}><dt>{metric.label}</dt><dd className="num">{formatPlayerMetric(metric.value, metric.unit)}</dd></div>)}</dl> : <p className="small dim">No player statistics supplied for this fixture.</p>}
        </details>
      </li>)}</ol>}
    </div>;
    })}</div>
    <p className="small dim">Missing means unavailable, never zero. Sportmonks player IDs and metric type IDs are preserved; no cross-league ranking or Golavo inference is made.</p>
  </article>;
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
