// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConfirmAction } from "./ConfirmAction";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

function renderAction(onConfirm = vi.fn()) {
  act(() => {
    root.render(
      <ConfirmAction
        triggerLabel="Remove evidence"
        confirmLabel="Confirm remove evidence"
        cancelAriaLabel="Cancel removing evidence"
        groupLabel="Remove local evidence"
        description="This removes the raw local capture."
        onConfirm={onConfirm}
      />,
    );
  });
  return onConfirm;
}

describe("ConfirmAction", () => {
  it("opens as an explicit Cancel/Confirm choice with safe initial focus", () => {
    renderAction();
    act(() => container.querySelector<HTMLButtonElement>("button")?.click());

    const buttons = [...container.querySelectorAll("button")];
    expect(buttons.map((button) => button.textContent)).toEqual(["Cancel", "Confirm remove evidence"]);
    expect(document.activeElement).toBe(buttons[0]);
  });

  it("Escape disarms the action and restores focus to the trigger", () => {
    renderAction();
    act(() => container.querySelector<HTMLButtonElement>("button")?.click());
    act(() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })));

    const trigger = container.querySelector<HTMLButtonElement>("button");
    expect(trigger?.textContent).toBe("Remove evidence");
    expect(document.activeElement).toBe(trigger);
  });

  it("runs the destructive callback only from the separately named confirm button", async () => {
    const onConfirm = renderAction(vi.fn().mockResolvedValue(undefined));
    act(() => container.querySelector<HTMLButtonElement>("button")?.click());
    const confirm = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Confirm remove evidence",
    );
    await act(async () => confirm?.click());

    expect(onConfirm).toHaveBeenCalledOnce();
    expect(container.querySelector("button")?.textContent).toBe("Remove evidence");
  });

  it("cannot imply cancellation after the destructive callback has started", async () => {
    let finish!: () => void;
    const onConfirm = renderAction(vi.fn(() => new Promise<void>((resolve) => { finish = resolve; })));
    act(() => container.querySelector<HTMLButtonElement>("button")?.click());
    const confirm = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Confirm remove evidence",
    );
    act(() => confirm?.click());
    act(() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })));

    expect(onConfirm).toHaveBeenCalledOnce();
    expect(container.querySelector("[aria-busy='true']")).not.toBeNull();
    expect(container.textContent).toContain("Removing…");

    await act(async () => finish());
    expect(container.querySelector("button")?.textContent).toBe("Remove evidence");
  });
});
