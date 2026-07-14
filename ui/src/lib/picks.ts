import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  MatchAnalysis,
  MatchRow,
  ModelFamily,
  PickPoints,
  PickResponse,
  PickScoring,
  PicksSummary,
  PickView,
  RivalPick,
  UserPick,
} from "./contract";
import { deletePick, fetchPick, fetchPicks, savePick } from "./api";
import type { AsyncState } from "./hooks";

export const RIVAL_LABELS: Record<ModelFamily, string> = {
  dixon_coles: "Goal Machine · picks an exact score",
  poisson_independent: "Plain Goals · picks an exact score",
  bivariate_poisson: "Twin Goals · picks an exact score",
  elo_ordlogit: "Form Ranker · calls the winner only",
  climatological: "History Buff · calls the winner only",
};

export type LockPhase = "open" | "locked" | "scored" | "void";

export function lockStateFor(
  value: PickView | UserPick | MatchRow,
  now: number | Date = Date.now(),
): { phase: LockPhase; msToLock: number; dayOnly: boolean } {
  const timestamp = now instanceof Date ? now.getTime() : now;
  const view = "record" in value ? value : null;
  const record = view?.record ?? ("user_pick" in value ? value : null);
  const kickoff = record?.lock_at_utc ?? (value as MatchRow).kickoff_utc;
  const dayOnly = record
    ? record.match.kickoff_time_known === false || record.match.kickoff_utc.endsWith("T00:00:00Z")
    : kickoff.endsWith("T00:00:00Z");
  const msToLock = Date.parse(kickoff) - timestamp;
  if (view?.status === "scored") return { phase: "scored", msToLock, dayOnly };
  if (view?.status === "void") return { phase: "void", msToLock, dayOnly };
  if (view?.status === "locked" || record?.status === "locked" || msToLock <= 0)
    return { phase: "locked", msToLock, dayOnly };
  return { phase: "open", msToLock, dayOnly };
}

export function formatLockCountdown(ms: number, dayOnly: boolean): string {
  if (ms <= 0) return "Locked";
  if (dayOnly) return "Locks when match day starts";
  const minutes = Math.ceil(ms / 60_000);
  if (minutes < 60) return `Locks in ${minutes < 1 ? "<1" : minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (hours < 24) return `Locks in ${hours}h${remainder ? ` ${remainder}m` : ""}`;
  const days = Math.ceil(ms / 86_400_000);
  return `Locks in ${days} day${days === 1 ? "" : "s"}`;
}

function outcome(home: number, away: number): "home" | "draw" | "away" {
  return home > away ? "home" : home < away ? "away" : "draw";
}

function basePoints(
  score: { home_goals: number; away_goals: number } | null,
  call: string | null,
  result: { home_goals: number; away_goals: number },
): PickPoints {
  const exact = Number(
    score?.home_goals === result.home_goals && score?.away_goals === result.away_goals,
  ) * 3;
  const outcomePoints = Number(call === outcome(result.home_goals, result.away_goals));
  return { exact, outcome: outcomePoints, total: exact + outcomePoints };
}

export function scorePick(
  record: UserPick,
  result: { home_goals: number; away_goals: number },
): PickScoring {
  const userBase = basePoints(record.user_pick, record.user_pick.outcome, result);
  const rivals = record.rivals.map((rival) => ({
    family: rival.family,
    ...basePoints(rival.score_pick, rival.outcome_pick, result),
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

export function deriveLiveRivals(analysis: MatchAnalysis | null): RivalPick[] {
  if (!analysis) return [];
  return analysis.models.map((model) => {
    if (model.abstained || !model.probs) {
      return { family: model.family, capability: "abstained", score_pick: null, outcome_pick: null };
    }
    const likely = model.score_matrix?.most_likely;
    if (likely) {
      return {
        family: model.family,
        capability: "score",
        score_pick: { home_goals: likely.home, away_goals: likely.away },
        outcome_pick: outcome(likely.home, likely.away),
      };
    }
    const ranked = (["home", "draw", "away"] as const).reduce((best, next) =>
      model.probs![next] > model.probs![best] ? next : best,
    );
    return { family: model.family, capability: "outcome_only", score_pick: null, outcome_pick: ranked };
  });
}

export function seasonTable(summary: PicksSummary) {
  const rivals = new Map(summary.rivals.map((rival) => [rival.family, rival]));
  return [
    { id: "user", label: "You", total: summary.user.total, exact: summary.user.exact, outcome: summary.user.outcome, bonus: summary.user.bonus, user: true },
    ...(Object.keys(RIVAL_LABELS) as ModelFamily[]).map((family) => ({
      id: family,
      label: RIVAL_LABELS[family].split(" · ")[0],
      family,
      total: rivals.get(family)?.total ?? 0,
      exact: rivals.get(family)?.exact ?? 0,
      outcome: rivals.get(family)?.outcome ?? 0,
      bonus: 0,
      user: false,
    })),
  ].sort((a, b) => Number(b.user) - Number(a.user) || b.total - a.total);
}

export function cumulativeSeries(views: PickView[]) {
  const scored = views
    .filter((view) => view.status === "scored" && view.scoring)
    .sort(
      (a, b) =>
        a.record.match.kickoff_utc.localeCompare(b.record.match.kickoff_utc) ||
        a.record.match.match_id.localeCompare(b.record.match.match_id),
    );
  let user = 0;
  const rivals: Partial<Record<ModelFamily, number>> = {};
  return scored.map((view) => {
    user += view.scoring!.user.total;
    for (const row of view.scoring!.rivals) rivals[row.family] = (rivals[row.family] ?? 0) + row.total;
    return { kickoff_utc: view.record.match.kickoff_utc, match_id: view.record.match.match_id, user_total: user, per_family_totals: { ...rivals } };
  });
}

export function streaks(views: PickView[]): { current: number; best: number } {
  let current = 0;
  let best = 0;
  const scored = views
    .filter((view) => view.status === "scored" && view.scoring)
    .sort((a, b) => a.record.match.kickoff_utc.localeCompare(b.record.match.kickoff_utc));
  for (const view of scored) {
    current = view.scoring!.user.outcome > 0 ? current + 1 : 0;
    best = Math.max(best, current);
  }
  return { current, best };
}

export function useCountdown(value: PickView | UserPick | MatchRow | null) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!value || lockStateFor(value, now).phase !== "open") return;
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, [value, now]);
  return value ? lockStateFor(value, now) : null;
}

export function usePick(matchId: string) {
  const [state, setState] = useState<AsyncState<PickResponse | null>>({ status: "loading" });
  const load = useCallback(async () => {
    setState({ status: "loading" });
    try {
      setState({ status: "ready", data: await fetchPick(matchId) });
    } catch (error) {
      setState({ status: "error", error: error instanceof Error ? error : new Error(String(error)) });
    }
  }, [matchId]);
  useEffect(() => {
    void load();
    const onChange = () => void load();
    window.addEventListener("golavo-picks-changed", onChange);
    return () => window.removeEventListener("golavo-picks-changed", onChange);
  }, [load]);
  const save = useCallback(async (home: number, away: number) => savePick(matchId, home, away), [matchId]);
  const remove = useCallback(async () => deletePick(matchId), [matchId]);
  return { state, refresh: load, save, remove };
}

export function usePicks() {
  const [state, setState] = useState<AsyncState<PickView[]>>({ status: "loading" });
  const load = useCallback(async () => {
    try {
      setState({ status: "ready", data: (await fetchPicks()).items });
    } catch (error) {
      setState({ status: "error", error: error instanceof Error ? error : new Error(String(error)) });
    }
  }, []);
  useEffect(() => {
    void load();
    const onChange = () => void load();
    const onStorage = (event: StorageEvent) => {
      if (event.key === "golavo-picks-v1") void load();
    };
    window.addEventListener("golavo-picks-changed", onChange);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("golavo-picks-changed", onChange);
      window.removeEventListener("storage", onStorage);
    };
  }, [load]);
  const byMatch = useMemo(
    () =>
      new Map(
        state.status === "ready"
          ? state.data.map((view) => [view.record.match.match_id, view] as const)
          : [],
      ),
    [state],
  );
  return { state, byMatch, refresh: load };
}
