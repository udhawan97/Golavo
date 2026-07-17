import { describe, expect, it } from "vitest";
import { narrativeJobWasLost, refreshMatchWeather, WeatherRefreshError } from "./api";

describe("narrative job polling", () => {
  it("tolerates a brief hand-off race before the first successful poll", () => {
    expect(narrativeJobWasLost(false, 1)).toBe(false);
    expect(narrativeJobWasLost(false, 2)).toBe(false);
    expect(narrativeJobWasLost(false, 3)).toBe(true);
  });

  it("stops immediately when a previously visible job disappears", () => {
    expect(narrativeJobWasLost(true, 1)).toBe(true);
  });
});

describe("weather refresh consent", () => {
  it("never fetches without a connected backend (the click is the consent)", async () => {
    // In the mock-data build there is no engine, so no network call is attempted.
    await expect(refreshMatchWeather("m_x")).rejects.toBeInstanceOf(WeatherRefreshError);
    await expect(refreshMatchWeather("m_x")).rejects.toMatchObject({ reasonCode: "preview_only" });
  });
});
