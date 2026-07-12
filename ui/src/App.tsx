import { useEffect } from "react";
import { Layout } from "./components/Layout";
import { useHashRoute, useTheme } from "./lib/hooks";
import { EmptyState } from "./components/states";
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
  const [theme, toggleTheme] = useTheme();
  const backendReady = useBackendReady();
  const forecastSource = useForecastSource(backendReady);
  // One controller for the whole app: header pill, sheet, settings, toast.
  const updater = useUpdaterController();

  // Calm scroll reset on navigation (respects reduced-motion via CSS).
  useEffect(() => { window.scrollTo({ top: 0 }); }, [path]);

  // Hold the app behind a splash until the (slow-to-extract) engine is up, so a
  // long first launch never looks like a broken window.
  if (!backendReady) return <StartupSplash theme={theme} />;

  return (
    <UpdaterContext.Provider value={updater}>
      <Layout
        path={path}
        theme={theme}
        onToggleTheme={toggleTheme}
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

function Route({ path }: { path: string }) {
  if (path === "/" || path === "") return <MatchdayList />;

  if (path === "/matches") return <MatchSearch />;

  const match = path.match(/^\/match\/(.+)$/);
  if (match) return <MatchDetail id={decodeURIComponent(match[1])} />;

  const forecast = path.match(/^\/forecast\/(.+)$/);
  if (forecast) return <ForecastDetail id={decodeURIComponent(forecast[1])} />;

  if (path === "/eval") return <EvaluationSummary />;

  if (path === "/ledger") return <PredictionLedger />;

  if (path === "/settings") return <Settings />;

  return (
    <EmptyState title="Page not found">
      That route doesn’t exist. <a href="#/">Back to matchday ›</a>{" "}
      <a href="#/matches">Search matches ›</a>
    </EmptyState>
  );
}
