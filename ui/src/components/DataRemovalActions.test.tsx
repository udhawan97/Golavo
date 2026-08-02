// @vitest-environment jsdom
import { act, useState, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  EvidenceRemovalAction,
  FollowHistoryRemovalAction,
  ProposalRemovalAction,
} from "./DataRemovalActions";

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

function button(name: string): HTMLButtonElement {
  const match = [...container.querySelectorAll("button")].find(
    (candidate) => candidate.textContent === name || candidate.getAttribute("aria-label") === name,
  );
  if (!match) throw new Error(`Missing button: ${name}`);
  return match;
}

const cases: Array<{
  name: string;
  trigger: string;
  confirm: string;
  cancel: string;
  render: (onConfirm: () => Promise<void>) => ReactElement;
}> = [
  {
    name: "follow history",
    trigger: "Remove follow history",
    confirm: "Confirm remove follow history",
    cancel: "Cancel removing follow history",
    render: (onConfirm) => <FollowHistoryRemovalAction onConfirm={onConfirm} />,
  },
  {
    name: "all proposals",
    trigger: "Remove all proposals",
    confirm: "Confirm remove all proposals",
    cancel: "Cancel removing all proposals",
    render: (onConfirm) => <ProposalRemovalAction onConfirm={onConfirm} />,
  },
  {
    name: "individual evidence",
    trigger: "Remove evidence",
    confirm: "Confirm remove evidence",
    cancel: "Cancel removing evidence from example.org",
    render: (onConfirm) => (
      <EvidenceRemovalAction hostname="example.org" disabled={false} onConfirm={onConfirm} />
    ),
  },
];

describe.each(cases)("$name removal integration", (removal) => {
  it("keeps Cancel safe and invokes only its separately named destructive action", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    act(() => root.render(removal.render(onConfirm)));

    act(() => button(removal.trigger).click());
    expect(document.activeElement).toBe(button(removal.cancel));
    act(() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(button(removal.trigger));

    act(() => button(removal.trigger).click());
    act(() => button(removal.cancel).click());
    expect(onConfirm).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(button(removal.trigger));

    act(() => button(removal.trigger).click());
    await act(async () => button(removal.confirm).click());
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});

it("blocks an armed sibling while another evidence removal is busy", async () => {
  let finishFirst!: () => void;
  const removeFirst = vi.fn(() => new Promise<void>((resolve) => { finishFirst = resolve; }));
  const removeSecond = vi.fn().mockResolvedValue(undefined);

  function EvidencePair() {
    const [busy, setBusy] = useState(false);
    const run = async (remove: () => Promise<void>) => {
      setBusy(true);
      try {
        await remove();
      } finally {
        setBusy(false);
      }
    };

    return (
      <>
        <EvidenceRemovalAction
          hostname="first.example"
          disabled={busy}
          onConfirm={() => run(removeFirst)}
        />
        <EvidenceRemovalAction
          hostname="second.example"
          disabled={busy}
          onConfirm={() => run(removeSecond)}
        />
      </>
    );
  }

  act(() => root.render(<EvidencePair />));
  const triggers = [...container.querySelectorAll<HTMLButtonElement>("button")];
  act(() => triggers[0]?.click());
  act(() => button("Remove evidence").click());

  const firstGroup = container.querySelector<HTMLElement>(
    '[role="group"][aria-label="Remove local evidence from first.example"]',
  );
  const secondGroup = container.querySelector<HTMLElement>(
    '[role="group"][aria-label="Remove local evidence from second.example"]',
  );
  const firstConfirm = firstGroup?.querySelector<HTMLButtonElement>(".btn--danger");
  const secondConfirm = secondGroup?.querySelector<HTMLButtonElement>(".btn--danger");

  act(() => firstConfirm?.click());
  expect(removeFirst).toHaveBeenCalledOnce();
  expect(secondConfirm?.disabled).toBe(true);
  act(() => secondConfirm?.click());
  expect(removeSecond).not.toHaveBeenCalled();

  await act(async () => finishFirst());
});
