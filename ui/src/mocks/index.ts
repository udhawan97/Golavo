/** Bundled mock fixtures. Loaded lazily via import.meta.glob so they land in a
 *  separate chunk and never weigh down the initial bundle. These are the
 *  fallback data source when VITE_GOLAVO_API is unset (the default). */
import type { ForecastArtifact, EvalSummary } from "../lib/contract";

const forecastModules = import.meta.glob<ForecastArtifact>("./forecasts/*.json", {
  import: "default",
});

/** All mock artifacts, sorted newest-first by seal time. */
export async function loadMockForecasts(): Promise<ForecastArtifact[]> {
  const loaded = await Promise.all(Object.values(forecastModules).map((imp) => imp()));
  return loaded.sort((a, b) =>
    b.forecast.sealed_at_utc.localeCompare(a.forecast.sealed_at_utc),
  );
}

export async function loadMockForecast(id: string): Promise<ForecastArtifact | null> {
  const all = await loadMockForecasts();
  return all.find((a) => a.artifact_id === id) ?? null;
}

export async function loadMockEval(): Promise<EvalSummary> {
  const mod = await import("./eval-summary.json");
  return mod.default as unknown as EvalSummary;
}
