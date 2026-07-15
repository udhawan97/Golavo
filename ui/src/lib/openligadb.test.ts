import { describe, expect, it } from "vitest";
import { fetchOpenLigaDBStatus } from "./openligadb";

describe("OpenLigaDB overlay contract", () => {
  it("stays disabled and display-only when no installed sidecar is connected", async () => {
    const status = await fetchOpenLigaDBStatus();
    expect(status.overlay_supported).toBe(false);
    expect(status.enabled).toBe(false);
    expect(status.display_only).toBe(true);
    expect(status.license.id).toBe("ODbL-1.0");
    expect(status.usage).toEqual({
      display: true,
      model_training: false,
      forecast_sealing: false,
      forecast_settlement: false,
      calibration: false,
      exports: false,
    });
  });
});
