import { beforeEach, describe, expect, it, vi } from "vitest";
import { dataRefreshPolicy } from "./fixtures";

function storage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => Array.from(values.keys())[index] ?? null,
    removeItem: (key) => { values.delete(key); },
    setItem: (key, value) => { values.set(key, value); },
  };
}

beforeEach(() => {
  vi.stubGlobal("localStorage", storage());
});

describe("approved-source refresh consent migration", () => {
  it("defaults to off", () => {
    expect(dataRefreshPolicy()).toBe("off");
  });

  it("narrows the old enabled toggle to check-only", () => {
    localStorage.setItem("golavo-fixtures-autorefresh", "on");
    expect(dataRefreshPolicy()).toBe("check_only");
    expect(localStorage.getItem("golavo-data-refresh-policy-v2")).toBe("check_only");
    expect(localStorage.getItem("golavo-fixtures-autorefresh")).toBeNull();
  });

  it("never widens an existing explicit policy", () => {
    localStorage.setItem("golavo-data-refresh-policy-v2", "auto_refresh");
    localStorage.setItem("golavo-fixtures-autorefresh", "off");
    expect(dataRefreshPolicy()).toBe("auto_refresh");
  });
});
