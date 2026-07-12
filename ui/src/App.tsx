import { Suspense, lazy, useEffect } from "react";
import { Layout } from "./components/Layout";
import { useHashRoute, useReadingPrefs } from "./lib/hooks";
import type { ReadingPrefs } from "./lib/hooks";
import { BlockSkeleton, EmptyState, Loading } from "./components/states";
// The Games home is the default landing, so it stays in the main bundle. Every
// other view is split out and loaded on first navigation — the initial download
// carries only what a fresh "open on football" launch needs.
import { GamesHome } from "./views/GamesHome";
const LeaguesHub = lazy(() => import("./views/Leagues").then((m) => ({ default: m.LeaguesHub })));
const LeagueView = lazy(() => import("./views/Leagues").then((m) => ({ default: m.LeagueView })));
const ModelLabHub = lazy(() => import("./views/ModelLab").then((m) => ({ default: m.ModelLabHub })));
const Methodologies = lazy(() => import("./views/ModelLab").then((m) => ({ default: m.Methodologies })));
const MatchdayList = lazy(() => import("./views/MatchdayList").then((m) => ({ default: m.MatchdayList })));
const MatchSearch = lazy(() => import("./views/MatchSearch").then((m) => ({ default: m.MatchSearch })));
const MatchDetail = lazy(() => import("./views/MatchDetail").then((m) => ({ default: m.MatchDetail })));
const ForecastDetail = lazy(() => import("./views/ForecastDetail").then((m) => ({ default: m.ForecastDetail })));
const EvaluationSummary = lazy(() => import("./views/EvaluationSummary").then((m) => ({ default: m.EvaluationSummary })));
const PredictionLedger = lazy(() => import("./views/PredictionLedger").then((m) => ({ default: m.PredictionLedger })));
const Settings = lazy(() => import("./views/Settings").then((m) => ({ default: m.Settings })));
import { UpdaterContext } from "./lib/updater-context";
import { useUpdaterController } from "./lib/updater";
import { UpdateConsentCard, UpdateSheet, UpdatedToast } from "./components/updates";
import { useBackendReady, useForecastSource } from "./lib/startup";
import { StartupSplash } from "./components/StartupSplash";
import { ErrorBoundary } from "./components/ErrorBoundary";

export default function App() {
  const [path] = useHashRoute();
  const [prefs, setPrefs] = useReadingPrefs();
  // The splash paints before the app shell; warm reads as a dark surface there.
  const splashTheme = prefs.theme === "light" ? "light" : "dark";
  const { ready: backendReady, stalled, retry } = useBackendReady();
  const forecastSource = useForecastSource(backendReady);
  // One controller for the whole app: header pill, sheet, settings, toast.
  const updater = useUpdaterController();

  // Calm scroll reset on navigation (respects reduced-motion via CSS).
  useEffect(() => { window.scrollTo({ top: 0 }); }, [path]);

  // Hold the app behind a splash until the (slow-to-extract) engine is up, so a
  // long first launch never looks like a broken window.
  if (!backendReady) return <StartupSplash theme={splashTheme} stalled={stalled} onRetry={retry} />;

  return (
    <UpdaterContext.Provider value={updater}>
      <Layout
        path={path}
        prefs={prefs}
        onChangePrefs={setPrefs}
        forecastSource={forecastSource}
      >
        <ErrorBoundary resetKey={path}>
          <Suspense
            fallback={
              <>
                <Loading label="Loading view" />
                <BlockSkeleton />
              </>
            }
          >
            <Route path={path} prefs={prefs} onChangePrefs={setPrefs} />
          </Suspense>
        </ErrorBoundary>
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

/** Decode a route segment without letting a malformed escape (e.g. `#/match/%`)
 *  throw a URIError during render — an unguarded throw here would unmount the
 *  whole app. Returns the raw segment on failure; a bad id then falls through to
 *  the view's own not-found state. */
function safeDecode(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

function Route({
  path,
  prefs,
  onChangePrefs,
}: {
  path: string;
  prefs: ReadingPrefs;
  onChangePrefs: (patch: Partial<ReadingPrefs>) => void;
}) {
  if (path === "/" || path === "" || path === "/games") return <GamesHome />;

  if (path === "/matches") return <MatchSearch />;

  const match = path.match(/^\/match\/(.+)$/);
  if (match) return <MatchDetail id={safeDecode(match[1])} />;

  const forecast = path.match(/^\/forecast\/(.+)$/);
  if (forecast) return <ForecastDetail id={safeDecode(forecast[1])} />;

  if (path === "/leagues") return <LeaguesHub />;
  const league = path.match(/^\/league\/(.+)$/);
  if (league) return <LeagueView slug={safeDecode(league[1])} />;

  // Model Lab — the relocated audit surface.
  if (path === "/lab") return <ModelLabHub />;
  if (path === "/lab/track-record") return <PredictionLedger />;
  if (path === "/lab/backtests") return <EvaluationSummary />;
  if (path === "/lab/methods") return <Methodologies />;
  if (path === "/lab/forecasts") return <MatchdayList />;

  // Legacy routes kept alive for old links/exports.
  if (path === "/eval") return <Redirect to="/lab/backtests" />;
  if (path === "/ledger") return <Redirect to="/lab/track-record" />;

  if (path === "/settings") return <Settings prefs={prefs} onChangePrefs={onChangePrefs} />;

  return (
    <EmptyState title="Page not found" variant="notfound">
      That route doesn’t exist. <a href="#/">Back to games ›</a>{" "}
      <a href="#/matches">Search matches ›</a>
    </EmptyState>
  );
}
