import type {
  MatchRow,
  PickResponse,
  PicksListResponse,
  PicksSummary,
  PickView,
  RivalPick,
  UserPick,
} from "../lib/contract";
import { PICK_SCHEMA_VERSION } from "../lib/contract";
import rivalsFixture from "./rival-picks.json";

export const MOCK_RIVALS = rivalsFixture as RivalPick[];

const STORE_KEY = "golavo-picks-v1";

export class MockPickError extends Error {
  constructor(
    readonly status: number,
    readonly reasonCode: string,
    message: string,
  ) {
    super(message);
  }
}

function readStore(): Record<string, UserPick> {
  try {
    const value = JSON.parse(localStorage.getItem(STORE_KEY) ?? "{}") as unknown;
    return value && typeof value === "object" ? (value as Record<string, UserPick>) : {};
  } catch {
    return {};
  }
}

function writeStore(store: Record<string, UserPick>): void {
  localStorage.setItem(STORE_KEY, JSON.stringify(store));
}

function ordered(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(ordered);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, item]) => [key, ordered(item)]),
    );
  }
  return value;
}

async function sha256(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(ordered(value)));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function matches(): Promise<MatchRow[]> {
  const mod = await import("./matches.json");
  return (mod.default as { matches: MatchRow[] }).matches;
}

function outcome(home: number, away: number): "home" | "draw" | "away" {
  return home > away ? "home" : home < away ? "away" : "draw";
}

async function lock(record: UserPick): Promise<UserPick> {
  if (record.status === "locked") return record;
  const locked: UserPick = {
    ...record,
    status: "locked",
    lock_at_utc: record.lock_at_utc,
    locked_at_utc: record.lock_at_utc,
    updated_at_utc: record.lock_at_utc,
  };
  const stable = { ...locked, pick_id: undefined, payload_sha256: undefined };
  const idHash = await sha256(stable);
  locked.pick_id = `pk_${idHash.slice(0, 20)}`;
  locked.payload_sha256 = await sha256({ ...locked, payload_sha256: undefined });
  return locked;
}

function score(record: UserPick, result: { home_goals: number; away_goals: number }) {
  const actual = outcome(result.home_goals, result.away_goals);
  const points = (scorePick: { home_goals: number; away_goals: number } | null, call: string | null) => {
    const exact = Number(
      scorePick?.home_goals === result.home_goals && scorePick?.away_goals === result.away_goals,
    ) * 3;
    const outcomePoints = Number(call === actual);
    return { exact, outcome: outcomePoints, total: exact + outcomePoints };
  };
  const userBase = points(record.user_pick, record.user_pick.outcome);
  const rivals = record.rivals.map((rival) => ({
    family: rival.family,
    ...points(rival.score_pick, rival.outcome_pick),
  }));
  const active = record.rivals
    .map((rival, index) => (rival.capability === "abstained" ? null : rivals[index].total))
    .filter((value): value is number => value !== null);
  const best = Math.max(0, ...active);
  const beat = active.length > 0 && userBase.total > best;
  return {
    user: { ...userBase, bonus: Number(beat), total: userBase.total + Number(beat) },
    rivals,
    beat_ai: beat,
    best_rival_total: best,
  };
}

async function toView(record: UserPick): Promise<PickView> {
  const all = await matches();
  const match = all.find((row) => row.match_id === record.match.match_id);
  let current = record;
  if (record.status === "draft" && Date.now() >= Date.parse(record.lock_at_utc)) {
    current = await lock(record);
    const store = readStore();
    store[record.match.match_id] = current;
    writeStore(store);
  }
  if (!match && current.status === "locked") {
    return { schema_version: PICK_SCHEMA_VERSION, status: "void", record: current, result: null, scoring: null, preview: true };
  }
  if (match?.is_complete && current.status === "locked") {
    const result = {
      home_goals: match.home_score as number,
      away_goals: match.away_score as number,
      outcome: outcome(match.home_score as number, match.away_score as number),
    };
    return {
      schema_version: PICK_SCHEMA_VERSION,
      status: "scored",
      record: current,
      result,
      scoring: score(current, result),
      preview: true,
    };
  }
  return {
    schema_version: PICK_SCHEMA_VERSION,
    status: current.status,
    record: current,
    result: null,
    scoring: null,
    preview: true,
  };
}

function response(matchId: string, pick: PickView | null, match: MatchRow): PickResponse {
  const lockAt = pick?.record.lock_at_utc ?? match.kickoff_utc;
  return {
    schema_version: PICK_SCHEMA_VERSION,
    match_id: matchId,
    pick,
    editable: !match.is_complete && Date.now() < Date.parse(lockAt) && (!pick || pick.status === "draft"),
    lock_at_utc: lockAt,
    now_utc: new Date(Date.now()).toISOString(),
  };
}

export async function mockFetchPick(matchId: string): Promise<PickResponse | null> {
  const match = (await matches()).find((row) => row.match_id === matchId);
  if (!match) return null;
  const record = readStore()[matchId];
  return response(matchId, record ? await toView(record) : null, match);
}

export async function mockSavePick(
  matchId: string,
  homeGoals: number,
  awayGoals: number,
): Promise<PickResponse> {
  const match = (await matches()).find((row) => row.match_id === matchId);
  if (!match) throw new MockPickError(404, "match_not_found", "Match not found");
  if (match.is_complete) throw new MockPickError(422, "fixture_complete", "This match is final");
  if (!Number.isInteger(homeGoals) || !Number.isInteger(awayGoals) || homeGoals < 0 || awayGoals < 0 || homeGoals > 20 || awayGoals > 20)
    throw new MockPickError(422, "invalid_score", "Scores must be whole numbers from 0 to 20");
  const store = readStore();
  const existing = store[matchId];
  if (existing?.status === "locked" || Date.now() >= Date.parse(existing?.lock_at_utc ?? match.kickoff_utc))
    throw new MockPickError(409, "pick_locked", "This pick locked at kickoff");
  const now = new Date(Date.now()).toISOString();
  const record: UserPick = {
    schema_version: PICK_SCHEMA_VERSION,
    pick_id: null,
    status: "draft",
    match: existing?.match ?? {
      match_id: matchId,
      kickoff_utc: match.kickoff_utc,
      kickoff_time_known: !(match.source_kind === "international" && match.kickoff_utc.endsWith("T00:00:00Z")),
      home_team: match.home_team,
      away_team: match.away_team,
      home_norm: match.home_team.toLocaleLowerCase(),
      away_norm: match.away_team.toLocaleLowerCase(),
      competition: match.competition,
    },
    user_pick: { home_goals: homeGoals, away_goals: awayGoals, outcome: outcome(homeGoals, awayGoals) },
    rivals: MOCK_RIVALS,
    analysis_fingerprint: {
      index_fingerprint: "practice-mode",
      analysis_schema_version: "practice-mode",
      information_cutoff_utc: new Date(Date.parse(match.kickoff_utc) - 1000).toISOString(),
    },
    created_at_utc: existing?.created_at_utc ?? now,
    updated_at_utc: now,
    lock_at_utc: existing?.lock_at_utc ?? match.kickoff_utc,
    locked_at_utc: null,
    payload_sha256: null,
  };
  store[matchId] = record;
  writeStore(store);
  return response(matchId, await toView(record), match);
}

export async function mockDeletePick(matchId: string): Promise<PickResponse | null> {
  const match = (await matches()).find((row) => row.match_id === matchId);
  if (!match) return null;
  const store = readStore();
  const existing = store[matchId];
  if (existing && (existing.status === "locked" || Date.now() >= Date.parse(existing.lock_at_utc)))
    throw new MockPickError(409, "pick_locked", "This pick locked at kickoff");
  delete store[matchId];
  writeStore(store);
  return response(matchId, null, match);
}

export async function mockFetchPicks(limit = 500, offset = 0): Promise<PicksListResponse> {
  const views = await Promise.all(Object.values(readStore()).map(toView));
  views.sort((a, b) => b.record.match.kickoff_utc.localeCompare(a.record.match.kickoff_utc));
  return {
    schema_version: PICK_SCHEMA_VERSION,
    items: views.slice(offset, offset + limit),
    total: views.length,
    limit,
    offset,
  };
}

export async function mockFetchPicksSummary(season: string | null = null): Promise<PicksSummary> {
  const all = (await mockFetchPicks()).items
    .filter((view) => !season || seasonFor(view.record.match.kickoff_utc) === season)
    .sort((a, b) => a.record.match.kickoff_utc.localeCompare(b.record.match.kickoff_utc));
  const counts = { draft: 0, locked: 0, scored: 0, void: 0 };
  const user = { total: 0, exact: 0, outcome: 0, bonus: 0 };
  const rivals = new Map<string, { family: RivalPick["family"]; total: number; exact: number; outcome: number }>();
  const series: PicksSummary["series"] = [];
  let current = 0;
  let best = 0;
  let exactCalls = 0;
  let winnerCalls = 0;
  let mae = 0;
  for (const view of all) {
    counts[view.status] += 1;
    if (view.status !== "scored" || !view.scoring || !view.result) continue;
    for (const key of ["total", "exact", "outcome", "bonus"] as const)
      user[key] += view.scoring.user[key];
    exactCalls += Number(view.scoring.user.exact > 0);
    winnerCalls += Number(view.scoring.user.outcome > 0);
    current = view.scoring.user.outcome > 0 ? current + 1 : 0;
    best = Math.max(best, current);
    mae += Math.abs(
      (view.record.user_pick.home_goals - view.record.user_pick.away_goals) -
        (view.result.home_goals - view.result.away_goals),
    );
    for (const row of view.scoring.rivals) {
      const total = rivals.get(row.family) ?? { family: row.family, total: 0, exact: 0, outcome: 0 };
      total.total += row.total;
      total.exact += row.exact;
      total.outcome += row.outcome;
      rivals.set(row.family, total);
    }
    series.push({
      kickoff_utc: view.record.match.kickoff_utc,
      match_id: view.record.match.match_id,
      user_total: user.total,
      per_family_totals: Object.fromEntries([...rivals].map(([family, row]) => [family, row.total])),
    });
  }
  const scored = counts.scored;
  return {
    schema_version: PICK_SCHEMA_VERSION,
    season,
    counts,
    user,
    rivals: [...rivals.values()],
    series,
    accuracy: { exact: scored ? exactCalls / scored : 0, winner: scored ? winnerCalls / scored : 0 },
    streak: { current, best },
    goal_diff_mae: scored ? mae / scored : 0,
  };
}

function seasonFor(kickoff: string): string {
  const date = new Date(kickoff);
  const start = date.getUTCMonth() >= 6 ? date.getUTCFullYear() : date.getUTCFullYear() - 1;
  return `${start}-${String(start + 1).slice(-2)}`;
}
