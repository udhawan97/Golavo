import { Suspense, lazy, useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import { useHashRoute, useReadingPrefs } from "./lib/hooks";
import type { ReadingPrefs } from "./lib/hooks";
import { BlockSkeleton, EmptyState, Loading } from "./components/states";
// The Matchday home is the default landing, so it stays in the main bundle. Every
// other view is split out and loaded on first navigation — the initial download
// carries only what a fresh "open on football" launch needs.
import { MatchdayHome } from "./views/Matchday";
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
const SealingGuide = lazy(() => import("./views/SealingGuide").then((m) => ({ default: m.SealingGuide })));
import { UpdaterContext } from "./lib/updater-context";
import { useUpdaterController } from "./lib/updater";
import { UpdateConsentCard, UpdateSheet, UpdatedToast } from "./components/updates";
import { useBackendReady, useForecastSource } from "./lib/startup";
import { StartupSplash } from "./components/StartupSplash";
import { startWarmupPolling, useWarmupStatus } from "./lib/warmup";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { TourOverlay } from "./components/TourOverlay";
import { HOME_TOUR, seedExistingUser, useTour } from "./lib/tour";

/** Longest we hold the splash on stage 2 (index warm) before releasing to the
 *  home's own warming card. A wedged index can never strand the user: search and
 *  cockpit already have honest 503 states. */
const INDEX_STAGE_CAP_MS = 45_000;

export default function App() {
  const [path] = useHashRoute();
  const [prefs, setPrefs] = useReadingPrefs();
  // The splash paints before the app shell; warm reads as a dark surface there.
  const splashTheme = prefs.theme === "light" ? "light" : "dark";
  const { ready: backendReady, reassure, failed, elapsedMs, retry } = useBackendReady();
  const forecastSource = useForecastSource(backendReady);
  const warmup = useWarmupStatus();
  const [skippedWarmup, setSkippedWarmup] = useState(false);
  // One controller for the whole app: header pill, sheet, settings, toast.
  const updater = useUpdaterController();

  // First-launch orientation. Seed returning users as "done" once so an update
  // never replays the newcomer tour. The home tour yields to the update-consent
  // card and only fires once a real match card exists (see useTour).
  useEffect(() => { seedExistingUser(); }, []);
  const onHome = path === "/" || path === "" || path === "/games";
  const homeTour = useTour(HOME_TOUR, onHome && backendReady && !updater.consentNeeded);

  // Once /health answers, start the shared status poll (drives the stage-2 splash,
  // the home warming card, and the activity center from one place).
  useEffect(() => {
    if (backendReady) startWarmupPolling();
  }, [backendReady]);

  // Auto-release stage 2 after a cap so a stuck index warm never holds the app.
  useEffect(() => {
    if (!backendReady || warmup.phase !== "warming") return;
    const id = window.setTimeout(() => setSkippedWarmup(true), INDEX_STAGE_CAP_MS);
    return () => window.clearTimeout(id);
  }, [backendReady, warmup.phase]);

  // Calm scroll reset on navigation (respects reduced-motion via CSS).
  useEffect(() => { window.scrollTo({ top: 0 }); }, [path]);

  // Hold the app behind a splash until the (slow-to-extract) engine is up, so a
  // long first launch never looks like a broken window. Stage 1 = the sidecar
  // self-extracting (no /health); stage 2 = /health up but the match index still
  // loading. Stage 2 is escapable (skip button + cap) so the user is never held
  // hostage — the home continues the same messaging in a smaller card.
  const holdForIndex = backendReady && warmup.phase === "warming" && !skippedWarmup;
  const showStartupFailure = failed && !backendReady;
  if (!backendReady || holdForIndex) {
    return (
      <StartupSplash
        theme={splashTheme}
        stage={backendReady ? "index" : "extracting"}
        rows={warmup.rows}
        reassure={reassure}
        failed={showStartupFailure}
        elapsedMs={elapsedMs}
        onRetry={retry}
        onSkip={backendReady && !showStartupFailure ? () => setSkippedWarmup(true) : undefined}
      />
    );
  }

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
      <TourOverlay ctrl={homeTour} />
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
  if (path === "/" || path === "" || path === "/games") return <MatchdayHome />;

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

  if (path === "/guide/sealing") return <SealingGuide />;

  return (
    <EmptyState title="Page not found" variant="notfound">
      That route doesn’t exist. <a href="#/">Back to Matchday ›</a>{" "}
      <a href="#/matches">Search matches ›</a>
    </EmptyState>
  );
}
