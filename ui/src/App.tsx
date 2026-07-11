import { useEffect } from "react";
import { Layout } from "./components/Layout";
import { useHashRoute, useTheme } from "./lib/hooks";
import { EmptyState } from "./components/states";
import { MatchdayList } from "./views/MatchdayList";
import { ForecastDetail } from "./views/ForecastDetail";
import { EvaluationSummary } from "./views/EvaluationSummary";
import { PredictionLedger } from "./views/PredictionLedger";

export default function App() {
  const [path] = useHashRoute();
  const [theme, toggleTheme] = useTheme();

  // Calm scroll reset on navigation (respects reduced-motion via CSS).
  useEffect(() => { window.scrollTo({ top: 0 }); }, [path]);

  return (
    <Layout path={path} theme={theme} onToggleTheme={toggleTheme}>
      <Route path={path} />
    </Layout>
  );
}

function Route({ path }: { path: string }) {
  if (path === "/" || path === "") return <MatchdayList />;

  const forecast = path.match(/^\/forecast\/(.+)$/);
  if (forecast) return <ForecastDetail id={decodeURIComponent(forecast[1])} />;

  if (path === "/eval") return <EvaluationSummary />;

  if (path === "/ledger") return <PredictionLedger />;

  return (
    <EmptyState title="Page not found">
      That route doesn’t exist. <a href="#/">Back to matchday ›</a>
    </EmptyState>
  );
}
