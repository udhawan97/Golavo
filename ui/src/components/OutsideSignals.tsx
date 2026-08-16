import { useEffect, useState } from "react";
import { handleExternalLinkClick } from "../lib/external-links";
import {
  fetchOutsideSignals,
  fetchSportmonksStatus,
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
}: {
  matchId: string;
  home: string;
  away: string;
}) {
  const [settings, setSettings] = useState<SportmonksStatus | null>(null);
  const [signals, setSignals] = useState<OutsideSignalsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; status: number } | null>(null);

  useEffect(() => {
    let live = true;
    setSignals(null);
    setError(null);
    void fetchSportmonksStatus().then(
      (value) => { if (live) setSettings(value); },
      () => { if (live) setSettings(null); },
    );
    return () => { live = false; };
  }, [matchId]);

  if (!settings?.enabled) return null;

  const fetchNow = async () => {
    setLoading(true);
    setError(null);
    try {
      setSignals(await fetchOutsideSignals(matchId));
    } catch (reason) {
      const value = reason instanceof SportmonksApiError
        ? { message: reason.message, status: reason.status }
        : { message: reason instanceof Error ? reason.message : String(reason), status: 0 };
      if (value.status === 401 || value.status === 403 || value.status === 429) {
        setSignals(null);
      }
      setError(value);
    } finally {
      setLoading(false);
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
          Sportmonks’ probabilities and bookmaker prices sit beside this programme. They never
          enter Golavo’s models, verdict, seal, score, calibration, AI read, or exports.
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
              {loading ? "Fetching from Sportmonks…" : "Fetch outside signals"}
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
            </div>

            <div className="outside-signals__provenance small dim">
              <span>
                Exact provider fixture {signals.identity.provider_fixture_id} · fetched{" "}
                {new Date(signals.provenance.fetched_at_utc).toLocaleString()} · raw response not stored
              </span>
              <button type="button" className="btn btn--ghost" disabled={loading} onClick={() => void fetchNow()}>
                {loading ? "Refreshing…" : "Refresh"}
              </button>
            </div>
          </>
        )}

        {error && !repairRequired && !rateLimited && (
          <p className="small dim" role="alert">Outside signals unavailable: {error.message}</p>
        )}
        <p className="small dim outside-signals__note">
          Informational only. Prices and provider models can be incomplete, delayed, or wrong. No
          bookmaker links, affiliate tracking, staking advice, or bet placement. Source:{" "}
          <a href={settings.provider.docs_url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>Sportmonks API v3</a>
          {" · "}<a href={settings.provider.terms_url} target="_blank" rel="noreferrer" onClick={handleExternalLinkClick}>terms</a>.
        </p>
      </div>
    </section>
  );
}
