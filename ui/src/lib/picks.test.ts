import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { MatchAnalysis, ScoredRivalFamily, PicksSummary, PickView, UserPick } from "./contract";
import {
  cumulativeSeries,
  deriveLiveRivals,
  formatLockCountdown,
  lockStateFor,
  RIVALS,
  rivalLabel,
  scorePick,
  seasonTable,
  streaks,
} from "./picks";
import { mockDeletePick, mockFetchPick, mockSavePick } from "../mocks/picks";

beforeAll(() => {
  const values = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      clear: () => values.clear(),
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    },
  });
});

function record(): UserPick {
  return {
    schema_version: "0.1.0",
    pick_id: "pk_0123456789abcdef0123",
    status: "locked",
    match: {
      match_id: "m_1",
      kickoff_utc: "2026-08-01T12:00:00Z",
      kickoff_time_known: true,
      home_team: "A",
      away_team: "B",
      home_norm: "a",
      away_norm: "b",
      competition: "Test",
    },
    user_pick: { home_goals: 2, away_goals: 1, outcome: "home" },
    rivals: [
      { family: "dixon_coles", capability: "score", score_pick: { home_goals: 2, away_goals: 1 }, outcome_pick: "home" },
      { family: "elo_ordlogit", capability: "outcome_only", score_pick: null, outcome_pick: "home" },
      { family: "climatological", capability: "abstained", score_pick: null, outcome_pick: null },
    ],
    analysis_fingerprint: { index_fingerprint: "i", analysis_schema_version: "a", information_cutoff_utc: "2026-08-01T11:59:59Z" },
    created_at_utc: "2026-08-01T10:00:00Z",
    updated_at_utc: "2026-08-01T12:00:00Z",
    lock_at_utc: "2026-08-01T12:00:00Z",
    locked_at_utc: "2026-08-01T12:00:00Z",
    payload_sha256: "0".repeat(64),
  };
}

function view(id: string, kickoff: string, outcomePoints: number): PickView {
  const item = record();
  item.match.match_id = id;
  item.match.kickoff_utc = kickoff;
  return {
    schema_version: "0.1.0",
    status: "scored",
    record: item,
    result: { home_goals: 3, away_goals: 1, outcome: "home" },
    scoring: {
      user: { exact: 0, outcome: outcomePoints, bonus: 0, total: outcomePoints },
      rivals: [{ family: "elo_ordlogit", exact: 0, outcome: 1, total: 1 }],
      beat_ai: false,
      best_rival_total: 1,
    },
  };
}

describe("pick scoring", () => {
  it("scores exact, winner, strict bonus, outcome-only, and abstention", () => {
    const tied = scorePick(record(), { home_goals: 2, away_goals: 1 });
    expect(tied.user).toEqual({ exact: 3, outcome: 1, bonus: 0, total: 4 });
    expect(tied.rivals[1].total).toBe(1);

    const call = record();
    call.rivals[0] = { family: "dixon_coles", capability: "score", score_pick: { home_goals: 0, away_goals: 1 }, outcome_pick: "away" };
    call.rivals[1].outcome_pick = "away";
    const win = scorePick(call, { home_goals: 4, away_goals: 0 });
    expect(win.user).toEqual({ exact: 0, outcome: 1, bonus: 1, total: 2 });
  });
});

describe("lock copy", () => {
  it("distinguishes timed and day-only kickoffs at the boundary", () => {
    const timed = record();
    timed.status = "draft";
    timed.match.kickoff_time_known = true;
    expect(lockStateFor(timed, Date.parse("2026-08-01T11:59:59Z")).phase).toBe("open");
    expect(lockStateFor(timed, Date.parse("2026-08-01T12:00:00Z")).phase).toBe("locked");
    timed.match.kickoff_time_known = false;
    expect(lockStateFor(timed, Date.parse("2026-08-01T11:00:00Z")).dayOnly).toBe(true);
  });

  it("formats countdown boundaries", () => {
    expect(formatLockCountdown(0, false)).toBe("Locked");
    expect(formatLockCountdown(59_000, false)).toBe("Locks in 1 min");
    expect(formatLockCountdown(2 * 3_600_000 + 14 * 60_000, false)).toBe("Locks in 2h 14m");
    expect(formatLockCountdown(3 * 86_400_000, false)).toBe("Locks in 3 days");
    expect(formatLockCountdown(3_600_000, true)).toBe("Locks when match day starts");
  });
});

it("derives live rivals without turning probabilities into exact scores", () => {
  const analysis = {
    models: [
      { family: "dixon_coles", abstained: false, probs: { home: 0.5, draw: 0.3, away: 0.2 }, score_matrix: { most_likely: { home: 1, away: 0 } } },
      { family: "elo_ordlogit", abstained: false, probs: { home: 0.4, draw: 0.4, away: 0.2 }, score_matrix: null },
    ],
  } as unknown as MatchAnalysis;
  expect(deriveLiveRivals(analysis)).toEqual([
    { family: "dixon_coles", capability: "score", score_pick: { home_goals: 1, away_goals: 0 }, outcome_pick: "home" },
    { family: "elo_ordlogit", capability: "outcome_only", score_pick: null, outcome_pick: "home" },
  ]);
});

it("orders cumulative series and excludes voids from streaks", () => {
  const a = view("a", "2026-08-01T12:00:00Z", 1);
  const b = view("b", "2026-08-02T12:00:00Z", 1);
  const c = view("c", "2026-08-03T12:00:00Z", 0);
  const voided = { ...view("void", "2026-08-02T18:00:00Z", 0), status: "void" as const, scoring: null, result: null };
  expect(cumulativeSeries([c, b, a]).map((point) => point.match_id)).toEqual(["a", "b", "c"]);
  expect(streaks([a, voided, b, c])).toEqual({ current: 0, best: 2 });
});

function emptySummary(): PicksSummary {
  return {
    schema_version: "0.1.0",
    season: null,
    counts: { draft: 0, locked: 0, scored: 0, void: 0 },
    user: { exact: 0, outcome: 0, bonus: 0, total: 0 },
    rivals: [],
    series: [],
    accuracy: { exact: 0, winner: 0 },
    streak: { current: 0, best: 0 },
    goal_diff_mae: 0,
  };
}

it("keeps all five rivals visible before any match is scored", () => {
  const table = seasonTable(emptySummary());
  expect(table.map((row) => row.label)).toEqual([
    "You",
    "Goal Machine",
    "Plain Goals",
    "Twin Goals",
    "Form Ranker",
    "History Buff",
  ]);
});

it("reports score capability per row so the exact column never guesses by name", () => {
  const table = seasonTable(emptySummary());
  expect(Object.fromEntries(table.map((row) => [row.id, row.capability]))).toEqual({
    user: "score",
    dixon_coles: "score",
    poisson_independent: "score",
    bivariate_poisson: "score",
    elo_ordlogit: "outcome_only",
    climatological: "outcome_only",
  });
});

it("keeps the rival blurb in step with the declared capability", () => {
  for (const family of Object.keys(RIVALS) as ScoredRivalFamily[]) {
    const scores = RIVALS[family].capability === "score";
    expect(rivalLabel(family)).toBe(
      `${RIVALS[family].name} · ${scores ? "picks an exact score" : "calls the winner only"}`,
    );
  }
});

describe("practice store", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-14T12:00:00Z"));
  });

  it("round-trips save, edit, lock, and remove", async () => {
    const id = "m_synthetic_01";
    expect((await mockFetchPick(id))?.pick).toBeNull();
    expect((await mockSavePick(id, 1, 0)).pick?.record.user_pick.home_goals).toBe(1);
    expect((await mockSavePick(id, 2, 1)).pick?.record.user_pick.home_goals).toBe(2);
    expect((await mockDeletePick(id))?.pick).toBeNull();
    await mockSavePick(id, 2, 1);
    vi.setSystemTime(new Date("2030-01-11T18:00:00Z"));
    const locked = await mockFetchPick(id);
    expect(locked?.pick?.status).toBe("locked");
    expect(locked?.pick?.record.payload_sha256).toMatch(/^[a-f0-9]{64}$/);
  });
});
