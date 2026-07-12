import { useEffect } from "react";
import { Layout } from "./components/Layout";
import { useHashRoute, useReadingPrefs } from "./lib/hooks";
import { EmptyState } from "./components/states";
import { GamesHome } from "./views/GamesHome";
import { LeaguesHub, LeagueView } from "./views/Leagues";
import { ModelLabHub, Methodologies } from "./views/ModelLab";
import { MatchdayList } from "./views/MatchdayList";
import { MatchSearch } from "./views/MatchSearch";
import { MatchDetail } from "./views/MatchDetail";
import { ForecastDetail } from "./views/ForecastDetail";
import { EvaluationSummary } from "./views/EvaluationSummary";
import { PredictionLedger } from "./views/PredictionLedger";
import { Settings } from "./views/Settings";
import { UpdaterContext } from "./lib/updater-context";
import { useUpdaterController } from "./lib/updater";
import { UpdateConsentCard, UpdateSheet, UpdatedToast } from "./components/updates";
import { useBackendReady, useForecastSource } from "./lib/startup";
import { StartupSplash } from "./components/StartupSplash";

export default function App() {
  const [path] = useHashRoute();
  const [prefs, setPrefs] = useReadingPrefs();
  // The splash paints before the app shell; warm reads as a dark surface there.
  const splashTheme = prefs.theme === "light" ? "light" : "dark";
  const backendReady = useBackendReady();
  const forecastSource = useForecastSource(backendReady);
  // One controller for the whole app: header pill, sheet, settings, toast.
  const updater = useUpdaterController();

  // Calm scroll reset on navigation (respects reduced-motion via CSS).
  useEffect(() => { window.scrollTo({ top: 0 }); }, [path]);

  // Hold the app behind a splash until the (slow-to-extract) engine is up, so a
  // long first launch never looks like a broken window.
  if (!backendReady) return <StartupSplash theme={splashTheme} />;

  return (
    <UpdaterContext.Provider value={updater}>
      <Layout
        path={path}
        prefs={prefs}
        onChangePrefs={setPrefs}
        forecastSource={forecastSource}
      >
        <Route path={path} />
      </Layout>
      <UpdateSheet />
      <UpdateConsentCard />
      <UpdatedToast />
    </UpdaterContext.Provider>
  );
}

/** Hash-route redirect: replaces the current entry so Back doesn't loop. Used to
 *  keep old deep links (#/ledger, #/eval) working after the Model Lab move. */
function Redirect({ to }: { to: string }) {
  useEffect(() => {
    window.location.replace(`#${to}`);
  }, [to]);
  return null;
}

function Route({ path }: { path: string }) {
  if (path === "/" || path === "") return <GamesHome />;

  if (path === "/matches") return <MatchSearch />;

  const match = path.match(/^\/match\/(.+)$/);
  if (match) return <MatchDetail id={decodeURIComponent(match[1])} />;

  const forecast = path.match(/^\/forecast\/(.+)$/);
  if (forecast) return <ForecastDetail id={decodeURIComponent(forecast[1])} />;

  if (path === "/leagues") return <LeaguesHub />;
  const league = path.match(/^\/league\/(.+)$/);
  if (league) return <LeagueView slug={decodeURIComponent(league[1])} />;

  // Model Lab — the relocated audit surface.
  if (path === "/lab") return <ModelLabHub />;
  if (path === "/lab/track-record") return <PredictionLedger />;
  if (path === "/lab/backtests") return <EvaluationSummary />;
  if (path === "/lab/methods") return <Methodologies />;
  if (path === "/lab/forecasts") return <MatchdayList />;

  // Legacy routes kept alive for old links/exports.
  if (path === "/eval") return <Redirect to="/lab/backtests" />;
  if (path === "/ledger") return <Redirect to="/lab/track-record" />;

  if (path === "/settings") return <Settings />;

  return (
    <EmptyState title="Page not found">
      That route doesn’t exist. <a href="#/">Back to games ›</a>{" "}
      <a href="#/matches">Search matches ›</a>
    </EmptyState>
  );
}
