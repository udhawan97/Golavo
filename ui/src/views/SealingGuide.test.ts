import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SealingGuide } from "./SealingGuide";

describe("SealingGuide audit terminology", () => {
  it("does not present the legacy horizon tag as elapsed lead time", () => {
    const html = renderToStaticMarkup(createElement(SealingGuide));

    expect(html).toContain("legacy audit label, not elapsed time");
    expect(html).toContain("immutable sealed-at and kickoff timestamps");
    expect(html).not.toContain("is how long before kickoff it was sealed");
  });
});
