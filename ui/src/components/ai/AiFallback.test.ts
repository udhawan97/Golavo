import { describe, expect, it } from "vitest";
import { humanizeError } from "./AiFallback";

describe("humanizeError", () => {
  it("explains that a 422 evidence failure happens before the model call", () => {
    const message = humanizeError(
      new Error("AI narrative → HTTP 422: cites unknown source_id"),
    );

    expect(message).toContain("verified evidence");
    expect(message).toContain("model was not called");
  });
});
