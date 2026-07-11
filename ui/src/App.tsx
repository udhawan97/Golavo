import { useEffect } from "react";
import { Layout } from "./components/Layout";
import { useHashRoute, useTheme } from "./lib/hooks";
import { EmptyState } from "./components/states";
import { MatchdayList } from "./views/MatchdayList";
import { ForecastDetail } from "./views/ForecastDetail";
import { EvaluationSummary } from "./views/EvaluationSummary";
import { PredictionLedger } from "./views/PredictionLedger";
import { Settings } from "./views/Settings";
import { UpdaterContext } from "./lib/updater-context";
import { useUpdaterController } from "./lib/updater";
import { UpdateConsentCard, UpdateSheet, UpdatedToast } from "./components/updates";

export default function App() {
  const [path] = useHashRoute();
  const [theme, toggleTheme] = useTheme();
  // One controller for the whole app: header pill, sheet, settings, toast.
  const updater = useUpdaterController();

  // Calm scroll reset on navigation (respects reduced-motion via CSS).
  useEffect(() => { window.scrollTo({ top: 0 }); }, [path]);

  return (
    <UpdaterContext.Provider value={updater}>
      <Layout path={path} theme={theme} onToggleTheme={toggleTheme}>
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

  const forecast = path.match(/^\/forecast\/(.+)$/);
  if (forecast) return <ForecastDetail id={decodeURIComponent(forecast[1])} />;

  if (path === "/eval") return <EvaluationSummary />;

  if (path === "/ledger") return <PredictionLedger />;

  if (path === "/settings") return <Settings />;

  return (
    <EmptyState title="Page not found">
      That route doesn’t exist. <a href="#/">Back to matchday ›</a>
    </EmptyState>
  );
}
