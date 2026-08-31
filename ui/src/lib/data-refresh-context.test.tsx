// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearApiCache,
  fetchDataRefreshStatus,
  rollbackDataRefresh,
  startDataRefresh,
} from "./api";
import {
  type DataRefreshController,
  useDataGenerationRevision,
  useDataRefreshController,
} from "./data-refresh-context";

vi.mock("./api", () => ({
  cancelDataRefresh: vi.fn(),
  clearApiCache: vi.fn(),
  fetchDataRefreshJob: vi.fn(),
  fetchDataRefreshStatus: vi.fn(),
  fetchFollows: vi.fn(),
  rollbackDataRefresh: vi.fn(),
  startDataRefresh: vi.fn(),
}));

let container: HTMLDivElement;
let root: Root;
let controller: DataRefreshController | null;

function Harness() {
  controller = useDataRefreshController(true);
  const revision = useDataGenerationRevision();
  return <output>{revision}</output>;
}

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  controller = null;
  vi.mocked(fetchDataRefreshStatus).mockResolvedValue(null as never);
  vi.mocked(rollbackDataRefresh).mockResolvedValue(undefined as never);
  vi.mocked(startDataRefresh).mockResolvedValue({
    job_id: "refresh-1",
    state: "done",
    result: { activated: true },
  } as never);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.clearAllMocks();
});

describe("data generation changes", () => {
  it("announces one rollback generation after the rollback API completes", async () => {
    await act(async () => root.render(<Harness />));

    await act(async () => controller?.rollback());

    expect(rollbackDataRefresh).toHaveBeenCalledOnce();
    // rollbackDataRefresh owns its cache clear; the controller must not advance
    // the cache epoch a second time before announcing the completed rollback.
    expect(clearApiCache).not.toHaveBeenCalled();
    expect(container.textContent).toBe("1");
  });

  it("clears cached reads and announces one activated refresh generation", async () => {
    await act(async () => root.render(<Harness />));

    await act(async () => controller?.refreshNow());

    expect(startDataRefresh).toHaveBeenCalledOnce();
    expect(clearApiCache).toHaveBeenCalledOnce();
    expect(container.textContent).toBe("1");
  });
});
