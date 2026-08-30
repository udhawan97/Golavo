// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  configureSportmonks,
  deleteSportmonksCredential,
  fetchSportmonksStatus,
  resetSportmonksClientState,
} from "../lib/sportmonks";
import { SportmonksSettings } from "./SportmonksSettings";

vi.mock("../lib/sportmonks", () => ({
  configureSportmonks: vi.fn(),
  deleteSportmonksCredential: vi.fn(),
  fetchSportmonksStatus: vi.fn(),
  resetSportmonksClientState: vi.fn(),
  saveSportmonksCredential: vi.fn(),
}));

const status = {
  schema_version: "0.1.0",
  enabled: true,
  capabilities: ["external_prediction", "external_odds", "player_lens"],
  terms_accepted_at_utc: "2026-08-30T00:00:00Z",
  terms_acceptance_version: "sportmonks-terms-sha256:test",
  connector_supported: true,
  request_policy: "foreground_click_only",
  storage_policy: "derived_response_memory_only",
  provider: {
    source_id: "sportmonks-v3",
    name: "Sportmonks",
    docs_url: "https://docs.sportmonks.com/v3/",
    terms_url: "https://www.sportmonks.com/terms-of-service/",
    privacy_url: "https://www.sportmonks.com/privacy-policy/",
    pricing_url: "https://www.sportmonks.com/football-api/plans-pricing/",
    terms_reviewed_date: "2026-08-30",
    terms_content_sha256: "4".repeat(64),
    terms_acceptance_version: "sportmonks-terms-sha256:test",
  },
  credential: {
    configured: true,
    source: "keychain",
    writable: true,
    environment_variable: "SPORTMONKS_API_TOKEN",
  },
  usage: {
    display: true,
    model_input: false,
    forecast_sealing: false,
    forecast_settlement: false,
    calibration: false,
    scoring: false,
    ai_evidence: false,
    exports: false,
  },
};

let container: HTMLDivElement;
let root: Root;

beforeEach(async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(fetchSportmonksStatus).mockResolvedValue(status as never);
  vi.mocked(configureSportmonks).mockResolvedValue({ ...status, enabled: false } as never);
  vi.mocked(deleteSportmonksCredential).mockResolvedValue({ ...status, enabled: false } as never);
  await act(async () => { root.render(<SportmonksSettings />); });
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

function button(label: string): HTMLButtonElement {
  const value = [...container.querySelectorAll("button")].find(
    (candidate) => candidate.textContent?.trim() === label,
  );
  if (!value) throw new Error(`missing button ${label}`);
  return value;
}

describe("Sportmonks Settings cleanup", () => {
  it("resets live state before disabling the connector", async () => {
    const order: string[] = [];
    vi.mocked(resetSportmonksClientState).mockImplementation(() => { order.push("reset"); });
    vi.mocked(configureSportmonks).mockImplementation(async () => {
      order.push("disable");
      return { ...status, enabled: false } as never;
    });

    await act(async () => { button("Disable").click(); });

    expect(order).toEqual(["reset", "disable"]);
  });

  it("disconnects in reset, disable, Keychain-delete order", async () => {
    const order: string[] = [];
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(resetSportmonksClientState).mockImplementation(() => { order.push("reset"); });
    vi.mocked(configureSportmonks).mockImplementation(async () => {
      order.push("disable");
      return { ...status, enabled: false } as never;
    });
    vi.mocked(deleteSportmonksCredential).mockImplementation(async () => {
      order.push("delete");
      return { ...status, enabled: false } as never;
    });

    await act(async () => { button("Disconnect & remove token").click(); });

    expect(order).toEqual(["reset", "disable", "delete"]);
  });

  it("does not delete the Keychain token when disabling fails", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(configureSportmonks).mockRejectedValue(new Error("disable failed"));

    await act(async () => { button("Disconnect & remove token").click(); });

    expect(resetSportmonksClientState).toHaveBeenCalledOnce();
    expect(deleteSportmonksCredential).not.toHaveBeenCalled();
    expect(container.textContent).toContain("disable failed");
  });
});
