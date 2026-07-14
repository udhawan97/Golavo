import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { startupCopyFor } from "../lib/startup";
import { StartupSplash } from "./StartupSplash";

describe("StartupSplash", () => {
  it("uses the selected matchday headline and a glanceable three-stage rail", () => {
    const html = renderToStaticMarkup(createElement(StartupSplash, {
      theme: "dark",
      stage: "extracting",
    }));

    expect(html).toContain("Setting the pitch");
    expect(html).toContain('aria-label="Startup stages"');
    expect(html).toContain('aria-current="step"');
    expect(html).toContain("Engine");
    expect(html).toContain("Match data");
    expect(html).toContain("Ready");
    expect(html).toContain("One-time setup");
  });

  it("keeps desktop stage detail concise and truthful", () => {
    expect(startupCopyFor("extracting", true, null).detail).toBe("Unpacking the local engine");
    expect(startupCopyFor("index", true, 75_432).detail).toBe(
      "Seating 75,432 matches in the library",
    );
    expect(startupCopyFor("extracting", false, null).detail).toBe(
      "Connecting to the local server",
    );
  });
});
