import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ProgrammePullNumber } from "./ProgrammePullNumber";

describe("ProgrammePullNumber", () => {
  it("renders nothing without a qualifying engine value", () => {
    expect(renderToStaticMarkup(<ProgrammePullNumber pull={null} />)).toBe("");
  });

  it("keeps the editorial number in reading order with a complete accessible label", () => {
    const html = renderToStaticMarkup(
      <ProgrammePullNumber
        pull={{
          label: "Most likely score",
          value: "2–1",
          takeaway: "12.3% for this exact scoreline in the goal model.",
          ariaLabel: "Verdict highlight: 2–1. 12.3% for this exact scoreline in the goal model.",
        }}
      />,
    );
    expect(html).toContain('aria-label="Verdict highlight: 2–1. 12.3% for this exact scoreline in the goal model."');
    expect(html).toContain('class="programme-pull__value num mono"');
    expect(html.indexOf("2–1")).toBeLessThan(html.indexOf("12.3%"));
  });
});
