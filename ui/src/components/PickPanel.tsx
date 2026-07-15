import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { MatchAnalysis, MatchRow, PickView } from "../lib/contract";
import { DATA_SOURCE, PickApiError } from "../lib/api";
import {
  deriveLiveRivals,
  formatLockCountdown,
  useCountdown,
  usePick,
} from "../lib/picks";
import { InfoPopover } from "./primitives";
import { LockIcon } from "./icons";
import { RivalPicks } from "./RivalPicks";
import { ScoreStepper } from "./ScoreStepper";
import { BlockSkeleton } from "./states";
import { MOCK_RIVALS } from "../mocks/picks";

const FIRST_PICK_KEY = "golavo-first-pick-welcome";

export function PickPanel({
  match,
  analysis,
  companion,
}: {
  match: MatchRow;
  analysis: MatchAnalysis | null;
  companion?: ReactNode;
}) {
  const controller = usePick(match.match_id);
  const response = controller.state.status === "ready" ? controller.state.data : null;
  const pick = response?.pick ?? null;
  const [home, setHome] = useState(0);
  const [away, setAway] = useState(0);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [welcome, setWelcome] = useState(false);
  const lock = useCountdown(pick ?? match);

  useEffect(() => {
    if (!pick) return;
    setHome(pick.record.user_pick.home_goals);
    setAway(pick.record.user_pick.away_goals);
  }, [pick]);

  useEffect(() => {
    if (pick?.status === "draft" && lock?.phase === "locked") void controller.refresh();
  }, [controller.refresh, lock?.phase, pick?.status]);

  const rivals = useMemo(
    () =>
      pick
        ? pick.record.rivals
        : analysis
          ? deriveLiveRivals(analysis)
          : DATA_SOURCE === "mock"
            ? MOCK_RIVALS
            : [],
    [analysis, pick],
  );

  if (controller.state.status === "loading") return <BlockSkeleton lines={3} />;
  if (controller.state.status === "error") {
    return <div className="callout callout--void" role="alert">Couldn’t load your call. {controller.state.error.message}</div>;
  }

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await controller.save(home, away);
      setEditing(false);
      try {
        if (localStorage.getItem(FIRST_PICK_KEY) !== "1") setWelcome(true);
      } catch {
        setWelcome(true);
      }
    } catch (cause) {
      setError(cause instanceof PickApiError ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await controller.remove();
      setHome(0);
      setAway(0);
      setEditing(false);
    } catch (cause) {
      setError(cause instanceof PickApiError ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };
  const dismissWelcome = () => {
    try { localStorage.setItem(FIRST_PICK_KEY, "1"); } catch { /* non-persistent */ }
    setWelcome(false);
  };

  const open = !match.is_complete && (!pick || pick.status === "draft") && lock?.phase === "open";
  return (
    <div className="pick-stack" data-tour="cockpit-pick">
      <div className={`pick-decision-grid${companion ? " pick-decision-grid--paired" : ""}`}>
        <section className={`pick-ticket pick-ticket--${pick?.status ?? "open"}`} aria-labelledby="pick-title">
          <div className="pick-ticket__kicker">YOUR CALL</div>
          {match.is_complete && !pick ? (
            <Skipped />
          ) : pick?.status === "scored" ? (
            <ScoredPickState pick={pick} />
          ) : pick && lock?.phase === "locked" ? (
            <LockedPickState pick={pick} preview={Boolean(pick.preview)} />
          ) : open && pick && !editing ? (
            <Saved
              pick={pick}
              countdown={formatLockCountdown(lock.msToLock, lock.dayOnly)}
              dayOnly={lock.dayOnly}
              onEdit={() => setEditing(true)}
              onRemove={remove}
              busy={busy}
            />
          ) : open ? (
            <>
              <h2 id="pick-title">What’s your score?</h2>
              <p className="muted measure">Move the numbers to the score you believe. You can change it any time before kickoff.</p>
              <div className="score-steppers">
                <ScoreStepper team={match.home_team} tone="home" value={home} onChange={setHome} />
                <span className="score-steppers__dash" aria-hidden>–</span>
                <ScoreStepper team={match.away_team} tone="away" value={away} onChange={setAway} />
              </div>
              <div className="pick-ticket__actions">
                <button type="button" className="btn btn--primary" onClick={save} disabled={busy}>
                  {busy ? "Saving…" : pick ? "Save changes" : "Save my call"}
                </button>
                {pick && <button type="button" className="btn btn--ghost" onClick={() => setEditing(false)}>Cancel</button>}
              </div>
            </>
          ) : (
            <Skipped />
          )}
          {error && <div className="pick-ticket__error" role="alert">{error}</div>}
          {welcome && (
            <div className="pick-welcome">
              <span>Your first call. No account, no stakes — pick the score you believe and see how you stack up against five AI rivals.</span>
              <button type="button" onClick={dismissWelcome}>Got it</button>
            </div>
          )}
          <footer className="pick-ticket__footer">
            3 points for the exact score · 1 for the right winner (or a draw) · +1 if you beat every model. <a href="#/guide/picks">How picks work ›</a>
            {pick?.preview && <span className="chip chip--neutral">Practice mode — never counted</span>}
          </footer>
        </section>
        {companion && <div className="pick-seal-slot">{companion}</div>}
      </div>
      <RivalPicks rivals={rivals} pick={pick} />
    </div>
  );
}

function Saved({ pick, countdown, dayOnly, onEdit, onRemove, busy }: { pick: PickView; countdown: string; dayOnly: boolean; onEdit: () => void; onRemove: () => void; busy: boolean }) {
  return (
    <>
      <div className="pick-ticket__saved">Saved. Your call: <strong className="num">{pick.record.user_pick.home_goals}–{pick.record.user_pick.away_goals}</strong>.</div>
      <div className="pick-ticket__status">
        <span className="chip chip--neutral"><LockIcon size={14} /> {countdown}</span>
        {dayOnly && <InfoPopover label="Why this pick locks at the start of match day">We only know the day of this match, not the hour, so picks lock when the match day begins (00:00 UTC). Early beats sorry — that’s what keeps every pick honest.</InfoPopover>}
      </div>
      <div className="pick-ticket__actions">
        <button type="button" className="btn btn--primary" onClick={onEdit}>Change pick</button>
        <button type="button" className="btn btn--ghost" onClick={onRemove} disabled={busy}>Remove pick</button>
      </div>
    </>
  );
}

export function LockedPickState({ pick, preview }: { pick: PickView; preview: boolean }) {
  return (
    <>
      <div className="pick-stamp"><LockIcon size={22} /><div><strong>Locked at kickoff — can’t be changed</strong><span>Waiting for full time</span></div></div>
      <div className="pick-locked-score num">{pick.record.user_pick.home_goals}–{pick.record.user_pick.away_goals}</div>
      <div className="pick-fingerprint">
        <code>{pick.record.payload_sha256?.slice(0, 24)}…</code>
        <InfoPopover label="What this fingerprint proves">This fingerprint (a SHA-256 hash) was written the instant your pick locked. If the pick ever changed, the fingerprint wouldn’t match. Proof your call came before the whistle.</InfoPopover>
      </div>
      {preview && <span className="chip chip--neutral">Practice mode — never counted</span>}
    </>
  );
}

export function ScoredPickState({ pick }: { pick: PickView }) {
  const final = pick.result;
  const points = pick.scoring?.user;
  if (!final || !points) return null;
  const title = points.exact
    ? `Final ${final.home_goals}–${final.away_goals} — you called it. +${points.total} points`
    : points.outcome
      ? `Final ${final.home_goals}–${final.away_goals} — right winner, not the score. +${points.total} point${points.total === 1 ? "" : "s"}`
      : `Final ${final.home_goals}–${final.away_goals} — not your night. 0 points.`;
  return (
    <>
      <div className="points-stamp">{title}</div>
      <div className="points-breakdown">
        {points.exact > 0 && <span>Exact score +3</span>}
        {points.outcome > 0 && <span>Right winner +1</span>}
        {points.bonus > 0 && <span>Beat all five models +1</span>}
      </div>
      <a href="#/season">Full season standings ›</a>
    </>
  );
}

function Skipped() {
  return <div><h2 id="pick-title">You didn’t call this one.</h2><p className="muted">Skipping costs nothing — the models only score on matches you play.</p></div>;
}
