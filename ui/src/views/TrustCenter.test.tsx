// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { archivePreviewReport, TrustCenter } from "./TrustCenter";
import {
  fetchCheckpointStatus,
  fetchRefreshReceipts,
  previewPersonalArchive,
  restorePersonalArchive,
  verifyProofFile,
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
  schema_version: "0.2.0" as const,
  verified: true as const,
  file_count: 2,
  total_bytes: 2048,
  new_files: ["ledger/fa_new.json"],
  identical_files: [],
  conflicts: ["ledger/picks/drafts/match.json"],
  requires_replace_confirmation: true,
  restore_preview_token: "preview-token",
  excluded_categories: ["credentials"],
  checkpoint_recovery: {
    available: true, recovery_drill_verified: true, checkpoint_count: 2,
    head: "a".repeat(64), head_schema_version: "0.2.0",
    checkpoint_schema_versions: ["0.1.0", "0.2.0"], legacy_checkpoint_count: 1,
    missing_artifacts: [], uncheckpointed_artifacts: [],
  },
  restore_blocked_reason: null,
};
const proofResult = {
  verified: true as const,
  root_artifact_id: "fa_root",
  artifact_count: 1,
  source_count: 1,
  embedded_source_count: 1,
  descriptor_only_source_count: 0,
  source_checks: [{
    source_id: "openfootball",
    sha256: "a".repeat(64),
    status: "embedded-manifest-hash-valid" as const,
  }],
  bundle_sha256: "b".repeat(64),
  checks: {},
  limits: ["Local bytes only."],
};

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(fetchCheckpointStatus).mockResolvedValue({
    schema_version: "0.2.0", verified: true, checkpoint_count: 0, head: null,
    head_schema_version: null, checkpoint_schema_versions: [], legacy_checkpoint_count: 0,
    migration_required: false, missing_artifacts: [], uncheckpointed_artifacts: [], limits: [],
  });
  vi.mocked(fetchRefreshReceipts).mockResolvedValue({ items: [], application_gap: null });
  vi.mocked(verifyProofFile).mockResolvedValue(proofResult);
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

async function selectProof(file: File) {
  const input = container.querySelectorAll<HTMLInputElement>('input[type="file"]')[0];
  Object.defineProperty(input, "files", { configurable: true, value: [file] });
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
}

async function selectArchive(file = new File(["archive"], "ledger.zip", { type: "application/zip" })) {
  const input = container.querySelectorAll<HTMLInputElement>('input[type="file"]')[1];
  Object.defineProperty(input, "files", { configurable: true, value: [file] });
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  return file;
}

describe("TrustCenter archive restore", () => {
  it("builds a non-authoritative comparison report without its restore token", () => {
    const report = archivePreviewReport(preview);
    expect(report.classifications.new_files).toEqual(["ledger/fa_new.json"]);
    expect(JSON.stringify(report)).not.toContain("preview-token");
    expect(report.limitation).toContain("not external authentication");
  });

  it("lists conflicts, refuses an unconfirmed replacement, then restores explicitly", async () => {
    const generationEvents = vi.fn();
    window.addEventListener("golavo-data-generation-changed", generationEvents);
    await renderCenter();
    const archiveInput = container.querySelectorAll<HTMLInputElement>('input[type="file"]')[1];
    archiveInput.focus();
    expect(document.activeElement).toBe(archiveInput);
    const file = await selectArchive();
    expect(container.textContent).toContain("ledger/picks/drafts/match.json");
    expect(container.textContent).toContain("ledger/fa_new.json");
    expect(container.textContent).toContain("Recovery drill passed for 2 linked checkpoint(s)");
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
    expect(restorePersonalArchive).toHaveBeenCalledWith(file, true, "preview-token");
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
    expect(container.textContent).not.toContain("Create checkpoint now");
  });

  it("shows a failed post-restore checkpoint drill and withholds the restore action", async () => {
    vi.mocked(previewPersonalArchive).mockResolvedValueOnce({
      ...preview,
      restore_blocked_reason: "restore would leave the local checkpoint chain invalid",
    });
    await renderCenter();
    await selectArchive();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      "checkpoint chain invalid",
    );
    expect([...container.querySelectorAll("button")].some(
      (button) => button.textContent === "Restore verified files",
    )).toBe(false);
  });

  it("binds restore to the newest file and ignores a superseded preview", async () => {
    let resolveFirst: ((value: typeof preview) => void) | null = null;
    let resolveSecond: ((value: typeof preview) => void) | null = null;
    vi.mocked(previewPersonalArchive)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve; }));
    await renderCenter();
    const first = new File(["first"], "first.zip", { type: "application/zip" });
    const second = new File(["second"], "second.zip", { type: "application/zip" });
    await selectArchive(first);
    await selectArchive(second);
    const secondPreview = {
      ...preview,
      new_files: ["ledger/second.json"],
      conflicts: [],
      requires_replace_confirmation: false,
      restore_preview_token: "second-token",
    };
    await act(async () => resolveSecond?.(secondPreview));
    await act(async () => resolveFirst?.({
      ...preview,
      new_files: ["ledger/first.json"],
      restore_preview_token: "first-token",
    }));

    expect(container.textContent).toContain("ledger/second.json");
    expect(container.textContent).not.toContain("ledger/first.json");
    const restore = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Restore verified files",
    )!;
    await act(async () => restore.click());
    expect(restorePersonalArchive).toHaveBeenCalledWith(second, false, "second-token");
  });

  it("binds proof results to the newest selected filename", async () => {
    let resolveFirst: ((value: typeof proofResult) => void) | null = null;
    let resolveSecond: ((value: typeof proofResult) => void) | null = null;
    vi.mocked(verifyProofFile)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve; }));
    await renderCenter();
    await selectProof(new File(["first"], "first.proof.json"));
    await selectProof(new File(["second"], "second.proof.json"));
    await act(async () => resolveSecond?.({ ...proofResult, artifact_count: 2 }));
    await act(async () => resolveFirst?.(proofResult));

    expect(container.textContent).toContain("second.proof.json");
    expect(container.textContent).toContain("2 artifacts");
    expect(container.textContent).not.toContain("first.proof.json");
  });

  it("guards an in-flight restore from duplicate submission and archive replacement", async () => {
    const first = new File(["first"], "first.zip", { type: "application/zip" });
    const second = new File(["second"], "second.zip", { type: "application/zip" });
    const noConflict = {
      ...preview,
      conflicts: [],
      requires_replace_confirmation: false,
      restore_preview_token: "first-token",
    };
    vi.mocked(previewPersonalArchive).mockResolvedValueOnce(noConflict);
    let resolveRestore: ((value: typeof preview & { restored: true; replaced_conflicts: true }) => void) | null = null;
    vi.mocked(restorePersonalArchive).mockImplementationOnce(() => new Promise((resolve) => {
      resolveRestore = resolve as typeof resolveRestore;
    }));
    await renderCenter();
    await selectArchive(first);
    const restore = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Restore verified files",
    )!;
    act(() => { restore.click(); restore.click(); });
    expect(restorePersonalArchive).toHaveBeenCalledTimes(1);
    expect(container.querySelectorAll<HTMLInputElement>('input[type="file"]')[1].disabled).toBe(true);
    await selectArchive(second);
    expect(previewPersonalArchive).toHaveBeenCalledTimes(1);
    await act(async () => resolveRestore?.({
      ...noConflict,
      restored: true,
      replaced_conflicts: true,
    }));
    expect(restorePersonalArchive).toHaveBeenCalledWith(first, false, "first-token");
  });
});
