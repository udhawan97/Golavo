// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import artifactJson from "../mocks/forecasts/fa_831ed103a95e335e676c.json";
import type { ForecastArtifact } from "../lib/contract";
import { ForecastDetail } from "./ForecastDetail";
import { fetchCalibration, fetchForecast, fetchForecasts } from "../lib/api";

vi.mock("../lib/api", () => ({
  downloadForecastProof: vi.fn(),
  fetchCalibration: vi.fn(),
  fetchForecast: vi.fn(),
  fetchForecasts: vi.fn(),
}));
vi.mock("../lib/hooks", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/hooks")>()),
  useForecastMode: () => ["casual", vi.fn()],
}));
vi.mock("../components/CommentatorsNotebook", () => ({
  CommentatorsNotebook: () => null,
}));
vi.mock("../components/ai/AiDeepRead", () => ({ AiDeepRead: () => null }));
vi.mock("../components/ScoredPanel", () => ({ ScoredPanel: () => null }));
vi.mock("../components/LocalTrackRecordContext", () => ({
  LocalTrackRecordContext: () => <section>Track record ready</section>,
}));

const artifact = artifactJson as unknown as ForecastArtifact;
let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(fetchForecast).mockResolvedValue(artifact);
  vi.mocked(fetchForecasts).mockResolvedValue([artifact]);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.clearAllMocks();
});

async function renderDetail() {
  await act(async () => root.render(<ForecastDetail id={artifact.artifact_id} />));
}

describe("ForecastDetail supplemental calibration", () => {
  it("renders the forecast while the independent calibration request is still slow", async () => {
    vi.mocked(fetchCalibration).mockImplementation(() => new Promise(() => undefined));

    await renderDetail();

    expect(container.textContent).toContain(artifact.match.home_team);
    expect(container.textContent).not.toContain("Loading forecast");
    expect(container.textContent).toContain("Loading this independent local history");
  });

  it("shows an explicit supplemental failure without hiding the forecast", async () => {
    vi.mocked(fetchCalibration).mockRejectedValue(new Error("calibration unavailable"));

    await renderDetail();

    expect(container.textContent).toContain(artifact.match.home_team);
    expect(container.textContent).toContain("Local sealed-record context is unavailable");
    expect(container.textContent).toContain("calibration unavailable");
    expect(container.textContent).toContain("forecast above is unaffected");
  });
});
