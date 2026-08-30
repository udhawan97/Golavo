import { useEffect, useMemo, useRef, useState } from "react";
import { fetchRecentMatches } from "../lib/api";
import type { RecentMatchesResponse } from "../lib/contract";
import { LEAGUES } from "../lib/leagues";
import {
  fetchSportmonksStatus,
  fetchTeamTransfers,
  SPORTMONKS_RESET_EVENT,
  SportmonksApiError,
} from "../lib/sportmonks";
import type { SportmonksStatus, TransferDeskResponse } from "../lib/sportmonks";
import { handleExternalLinkClick } from "../lib/external-links";
import { BookIcon, ChevronRight, ShieldCheckIcon } from "../components/icons";
import { BlockSkeleton, ErrorState } from "../components/states";

const TOP_FIVE = LEAGUES.filter((league) => league.seasonOutlook && league.competition);
const TOP_FIVE_NAMES = new Set(TOP_FIVE.map((league) => league.competition as string));

export interface TransferClubOption {
  key: string;
  team: string;
  competition: string;
  matchId: string;
  side: "home" | "away";
}

export function buildTransferClubOptions(value: RecentMatchesResponse): TransferClubOption[] {
  const options = new Map<string, TransferClubOption>();
  const rows = [...value.upcoming, ...value.recent];
  for (const match of rows) {
    if (match.source_kind !== "club" || !TOP_FIVE_NAMES.has(match.competition)) continue;
    for (const [side, team] of [["home", match.home_team], ["away", match.away_team]] as const) {
      const key = `${match.competition}::${team}`;
      if (!options.has(key)) {
        options.set(key, { key, team, competition: match.competition, matchId: match.match_id, side });
      }
    }
  }
  const order = new Map(TOP_FIVE.map((league, index) => [league.competition as string, index]));
  return [...options.values()].sort((a, b) => (
    (order.get(a.competition) ?? 99) - (order.get(b.competition) ?? 99)
    || a.team.localeCompare(b.team)
  ));
}

export function Transfers() {
  const [directory, setDirectory] = useState<RecentMatchesResponse | null>(null);
  const [directoryError, setDirectoryError] = useState<Error | null>(null);
  const [provider, setProvider] = useState<SportmonksStatus | null>(null);
  const [providerError, setProviderError] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState("");
  const [result, setResult] = useState<TransferDeskResponse | null>(null);
  const [fetchError, setFetchError] = useState<{ message: string; status: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const activeRequest = useRef<AbortController | null>(null);
  const generation = useRef(0);

  const loadLocalState = () => {
    setDirectory(null);
    setDirectoryError(null);
    void fetchRecentMatches(100).then(setDirectory, (reason: unknown) => {
      setDirectoryError(reason instanceof Error ? reason : new Error(String(reason)));
    });
  };

  useEffect(() => {
    let live = true;
    loadLocalState();
    void fetchSportmonksStatus().then(
      (value) => { if (live) setProvider(value); },
      (reason: unknown) => {
        if (live) setProviderError(reason instanceof Error ? reason.message : String(reason));
      },
    );
    return () => {
      live = false;
      activeRequest.current?.abort();
    };
  }, []);

  useEffect(() => {
    generation.current += 1;
    activeRequest.current?.abort();
    activeRequest.current = null;
    setResult(null);
    setFetchError(null);
    setLoading(false);
  }, [selectedKey]);

  useEffect(() => {
    const reset = () => {
      generation.current += 1;
      activeRequest.current?.abort();
      activeRequest.current = null;
      setProvider(null);
      setResult(null);
      setFetchError(null);
      setLoading(false);
    };
    window.addEventListener(SPORTMONKS_RESET_EVENT, reset);
    return () => window.removeEventListener(SPORTMONKS_RESET_EVENT, reset);
  }, []);

  const options = useMemo(
    () => directory ? buildTransferClubOptions(directory) : [],
    [directory],
  );
  const selected = options.find((option) => option.key === selectedKey) ?? null;
  const providerReady = provider?.enabled
    && provider.credential.configured
    && provider.capabilities.includes("transfer_desk")
    && provider.terms_acceptance_version === provider.provider.terms_acceptance_version;

  const fetchTransfers = async () => {
    if (!selected || !providerReady) return;
    const requestGeneration = ++generation.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    setFetchError(null);
    setResult(null);
    try {
      const value = await fetchTeamTransfers(selected.matchId, selected.side, controller.signal);
      if (!controller.signal.aborted && generation.current === requestGeneration) setResult(value);
    } catch (reason) {
      if (controller.signal.aborted || generation.current !== requestGeneration) return;
      setFetchError(reason instanceof SportmonksApiError
        ? { message: reason.message, status: reason.status }
        : { message: reason instanceof Error ? reason.message : String(reason), status: 0 });
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
      if (generation.current === requestGeneration) setLoading(false);
    }
  };

  return (
    <div className="transfer-desk stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/leagues">Leagues</a><ChevronRight size={14} />
        <span aria-current="page">Transfer Desk</span>
      </nav>

      <header className="transfer-hero">
        <div>
          <span className="upper">Provider-backed club ledger</span>
          <h1>Transfer Desk</h1>
          <p>
            Inspect arrivals and departures against one exact club identity. Provider records stay
            separate from Golavo’s models, AI evidence, forecasts, scores, and exports.
          </p>
        </div>
        <div className="transfer-hero__mark" aria-hidden><BookIcon size={28} /></div>
      </header>

      <section className="transfer-control panel" aria-labelledby="transfer-control-title">
        <div className="panel__head">
          <div><span className="upper">Foreground capture</span><h2 id="transfer-control-title">Choose a top-five club</h2></div>
          <span className="chip chip--neutral">No background refresh</span>
        </div>
        <div className="panel__body stack" style={{ ["--gap" as string]: ".85rem" }}>
          {directoryError ? (
            <ErrorState title="Club directory unavailable" error={directoryError} onRetry={loadLocalState} />
          ) : !directory ? <BlockSkeleton lines={3} /> : (
            <>
              <label className="transfer-club-picker">
                <span>Club</span>
                <select value={selectedKey} onChange={(event) => setSelectedKey(event.target.value)}>
                  <option value="">Select a club…</option>
                  {TOP_FIVE.map((league) => {
                    const group = options.filter((option) => option.competition === league.competition);
                    return group.length > 0 ? (
                      <optgroup key={league.slug} label={league.name}>
                        {group.map((option) => <option key={option.key} value={option.key}>{option.team}</option>)}
                      </optgroup>
                    ) : null;
                  })}
                </select>
              </label>
              <ProviderGate provider={provider} error={providerError} />
              <div className="transfer-fetch-row">
                <button
                  type="button"
                  className="btn btn--primary"
                  disabled={!selected || !providerReady || loading}
                  onClick={() => void fetchTransfers()}
                >
                  {loading ? "Fetching bounded transfer window…" : result ? "Refresh transfer window" : "Fetch transfer window"}
                </button>
                <span className="small dim">
                  One click resolves an exact fixture/team identity, then reads at most 4 × 50
                  provider rows from the preceding 365 days.
                </span>
              </div>
            </>
          )}
          {fetchError && (
            <p className="transfer-error" role="alert">
              Transfer Desk unavailable: {fetchError.message}
              {fetchError.status === 401 || fetchError.status === 403 ? <> · <a href="#/settings">Review token and plan</a></> : null}
            </p>
          )}
        </div>
      </section>

      {result && <TransferResult value={result} />}

      <aside className="transfer-boundary" aria-label="Transfer evidence boundary">
        <ShieldCheckIcon size={20} />
        <p>
          <b>Evidence boundary.</b> The provider amount is nullable free text and its currency is
          unspecified. Installments, add-ons, sell-ons, agent fees, training rewards, and conditional
          consideration are not supplied by this feed, so Golavo marks them unavailable rather than
          estimating them. Rumours and scraped sources are excluded.
        </p>
      </aside>
    </div>
  );
}

function ProviderGate({ provider, error }: { provider: SportmonksStatus | null; error: string | null }) {
  if (error) return <p className="small dim">The Transfer Desk requires the installed Golavo app. {error}</p>;
  if (!provider) return <p className="small dim">Checking the local provider connector…</p>;
  if (!provider.connector_supported) return <p className="small dim">This build does not include the Sportmonks connector.</p>;
  if (!provider.enabled) return <p className="small dim">Sportmonks is off. <a href="#/settings">Review and enable it in Settings</a>.</p>;
  if (!provider.capabilities.includes("transfer_desk")) return <p className="small dim">Transfer Desk is off. <a href="#/settings">Enable that capability in Settings</a>.</p>;
  if (!provider.credential.configured) return <p className="small dim">Add your Sportmonks token in <a href="#/settings">Settings</a>.</p>;
  if (provider.terms_acceptance_version !== provider.provider.terms_acceptance_version) return <p className="small dim">The provider disclosure changed. <a href="#/settings">Review the current terms in Settings</a>.</p>;
  return <p className="small transfer-ready"><ShieldCheckIcon size={15} /> Connector ready. No provider request has been made yet.</p>;
}

function TransferResult({ value }: { value: TransferDeskResponse }) {
  const arrivals = value.transfers.filter((row) => row.direction === "arrival");
  const departures = value.transfers.filter((row) => row.direction === "departure");
  return (
    <section className="transfer-results stack" style={{ ["--gap" as string]: "1rem" }} aria-labelledby="transfer-results-title">
      <div className="transfer-results__head">
        <div>
          <span className="upper">Exact provider team <code>{value.identity.provider_team_id}</code></span>
          <h2 id="transfer-results-title">{value.identity.golavo_team}</h2>
        </div>
        <span className={`chip ${value.status === "partial" ? "chip--neutral" : "chip--success"}`}>
          {value.status === "partial" ? "Partial window" : "Bounded read complete"}
        </span>
      </div>
      <p className="transfer-partial" role="status">
        {value.status === "partial"
          ? "The 4-page safety bound was reached before the one-year window closed. These rows are a partial provider view, not a complete club ledger."
          : "The bounded provider read ended within its page and date limits. Subscription and source coverage can still be incomplete; this is not a complete club ledger."}
      </p>
      {value.transfers.length === 0 ? (
        <p className="card card--pad dim">No identity-safe provider transfer rows were returned inside this window.</p>
      ) : (
        <div className="transfer-lanes">
          <TransferLane title="Arrivals" rows={arrivals} />
          <TransferLane title="Departures" rows={departures} />
        </div>
      )}
      <div className="transfer-provenance small dim">
        <span>
          {value.coverage.window_start} → {value.coverage.window_end} · {value.coverage.pages_fetched}/{value.coverage.page_limit} pages · fetched {new Date(value.provenance.fetched_at_utc).toLocaleString()}
        </span>
        <span>Fixture <code>{value.identity.provider_fixture_id}</code> · raw responses not stored · no model/AI/export use</span>
        <a href={value.provider.docs_url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>Sportmonks API docs</a>
      </div>
    </section>
  );
}

function TransferLane({ title, rows }: { title: string; rows: TransferDeskResponse["transfers"] }) {
  const id = `transfer-${title.toLowerCase()}`;
  return (
    <section className="transfer-lane" aria-labelledby={id}>
      <div className="transfer-lane__head"><h3 id={id}>{title}</h3><span className="num">{rows.length}</span></div>
      {rows.length === 0 ? <p className="small dim">No supplied rows in this direction.</p> : rows.map((row) => (
        <article className="transfer-record" key={row.transfer_id}>
          <div className="transfer-record__top">
            <div><span className="upper">{row.date} · {row.completed ? "completed" : "not marked complete"}</span><h4>{row.player.name}</h4></div>
            <span className="chip chip--neutral">{row.type.name}</span>
          </div>
          <p className="transfer-route"><span>{row.from_team.name}</span><ChevronRight size={14} /><strong>{row.to_team.name}</strong></p>
          <dl className="transfer-record__facts">
            <div><dt>Position</dt><dd>{row.position?.name ?? "Unavailable"}</dd></div>
            <div><dt>{row.amount_label}</dt><dd className="num">{row.provider_reported_amount ?? "Unavailable"}</dd></div>
          </dl>
          <details className="transfer-payment">
            <summary>Payment structure · not reported</summary>
            <dl>
              {[
                "Currency", "Installments", "Add-ons", "Sell-on terms", "Agent / intermediary fees",
                "Training rewards", "Conditional consideration",
              ].map((label) => <div key={label}><dt>{label}</dt><dd>Not reported</dd></div>)}
            </dl>
          </details>
          <p className="transfer-record__ids small dim">
            Transfer <code>{row.transfer_id}</code> · player <code>{row.player.id}</code> · type <code>{row.type.id}</code> · teams <code>{row.from_team.id}</code> → <code>{row.to_team.id}</code>
          </p>
        </article>
      ))}
    </section>
  );
}
