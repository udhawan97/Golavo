// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TrustCenter } from "./TrustCenter";
import {
  fetchCheckpointStatus,
  fetchRefreshReceipts,
  previewPersonalArchive,
  restorePersonalArchive,
} from "../lib/api";

vi.mock("../lib/api", () => ({
  createCheckpoint: vi.fn(),
  downloadPersonalArchive: vi.fn(),
  fetchCheckpointStatus: vi.fn(),
  fetchRefreshReceipts: vi.fn(),
  previewPersonalArchive: vi.fn(),
  restorePersonalArchive: vi.fn(),
  verifyProofFile: vi.fn(),
}));

let container: HTMLDivElement;
let root: Root;
const preview = {
  schema_version: "0.1.0" as const,
  verified: true as const,
  file_count: 2,
  total_bytes: 2048,
  conflicts: ["ledger/picks/drafts/match.json"],
  requires_replace_confirmation: true,
  excluded_categories: ["credentials"],
};

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(fetchCheckpointStatus).mockResolvedValue({
    schema_version: "0.1.0", verified: true, checkpoint_count: 0, head: null,
    missing_artifacts: [], uncheckpointed_artifacts: [], limits: [],
  });
  vi.mocked(fetchRefreshReceipts).mockResolvedValue({ items: [], application_gap: null });
  vi.mocked(previewPersonalArchive).mockResolvedValue(preview);
  vi.mocked(restorePersonalArchive).mockResolvedValue({
    ...preview, restored: true, replaced_conflicts: true,
    pre_restore_backup: "pre-restore.zip",
  });
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.clearAllMocks();
});

async function renderCenter() {
  await act(async () => root.render(<TrustCenter />));
}

async function selectArchive() {
  const input = container.querySelectorAll<HTMLInputElement>('input[type="file"]')[1];
  const file = new File(["archive"], "ledger.zip", { type: "application/zip" });
  Object.defineProperty(input, "files", { configurable: true, value: [file] });
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  return file;
}

describe("TrustCenter archive restore", () => {
  it("lists conflicts, refuses an unconfirmed replacement, then restores explicitly", async () => {
    const generationEvents = vi.fn();
    window.addEventListener("golavo-data-generation-changed", generationEvents);
    await renderCenter();
    const file = await selectArchive();
    expect(container.textContent).toContain("ledger/picks/drafts/match.json");
    const restore = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Restore verified files",
    ) as HTMLButtonElement;
    expect(restore.disabled).toBe(true);
    restore.click();
    expect(restorePersonalArchive).not.toHaveBeenCalled();

    const confirm = container.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    await act(async () => confirm.click());
    expect(restore.disabled).toBe(false);
    await act(async () => restore.click());
    expect(restorePersonalArchive).toHaveBeenCalledWith(file, true);
    expect(fetchCheckpointStatus).toHaveBeenCalledTimes(2);
    expect(generationEvents).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("Restore complete");
    expect(container.textContent).toContain("pre-restore.zip");
    window.removeEventListener("golavo-data-generation-changed", generationEvents);
  });

  it("renders preview and restore failures without clearing the verified choice", async () => {
    vi.mocked(previewPersonalArchive).mockRejectedValueOnce(new Error("Checksum mismatch"));
    await renderCenter();
    await selectArchive();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("Checksum mismatch");

    vi.mocked(previewPersonalArchive).mockResolvedValueOnce(preview);
    vi.mocked(restorePersonalArchive).mockRejectedValueOnce(new Error("Recovery refused"));
    await selectArchive();
    const confirm = container.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    await act(async () => confirm.click());
    const restore = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Restore verified files",
    )!;
    await act(async () => restore.click());
    expect(container.querySelector('[role="alert"]')?.textContent).toContain("Recovery refused");
    expect(container.textContent).toContain("ledger/picks/drafts/match.json");
  });

  it("keeps restore success but removes stale checkpoint counts when recheck fails", async () => {
    await renderCenter();
    await selectArchive();
    const confirm = container.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    await act(async () => confirm.click());
    vi.mocked(fetchCheckpointStatus).mockRejectedValueOnce(
      new Error("Restored bytes no longer match the checkpoint"),
    );
    const restore = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Restore verified files",
    )!;

    await act(async () => restore.click());

    expect(container.textContent).toContain("Restore complete");
    expect(container.textContent).toContain("Restored bytes no longer match the checkpoint");
    expect(container.textContent).not.toContain("linked checkpoint(s)");
  });
});
