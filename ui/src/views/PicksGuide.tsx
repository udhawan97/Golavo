import type { ReactNode } from "react";
import { Drawer } from "../components/disclosure";
import {
  CalendarIcon,
  ChevronRight,
  LockIcon,
  ScaleIcon,
  TrophyIcon,
  VersusIcon,
} from "../components/icons";
import { LockedPickState, ScoredPickState } from "../components/PickPanel";
import { StatTile } from "../components/primitives";
import { PICK_SCHEMA_VERSION, type PickView } from "../lib/contract";

const EXAMPLE: PickView = {
  schema_version: PICK_SCHEMA_VERSION,
  status: "scored",
  preview: true,
  record: {
    schema_version: PICK_SCHEMA_VERSION,
    pick_id: "pk_madeup0123456789abcd",
    status: "locked",
    match: {
      match_id: "made-up-example",
      kickoff_utc: "2030-06-08T18:00:00Z",
      kickoff_time_known: true,
      home_team: "Northbridge",
      away_team: "Southport",
      home_norm: "northbridge",
      away_norm: "southport",
      competition: "Made-up Cup",
    },
    user_pick: { home_goals: 2, away_goals: 1, outcome: "home" },
    rivals: [
      { family: "dixon_coles", capability: "score", score_pick: { home_goals: 1, away_goals: 0 }, outcome_pick: "home" },
      { family: "poisson_independent", capability: "score", score_pick: { home_goals: 1, away_goals: 1 }, outcome_pick: "draw" },
      { family: "bivariate_poisson", capability: "score", score_pick: { home_goals: 1, away_goals: 1 }, outcome_pick: "draw" },
      { family: "elo_ordlogit", capability: "outcome_only", score_pick: null, outcome_pick: "draw" },
      { family: "climatological", capability: "outcome_only", score_pick: null, outcome_pick: "away" },
    ],
    analysis_fingerprint: {
      index_fingerprint: "made-up-index",
      analysis_schema_version: "0.2.0",
      information_cutoff_utc: "2030-06-08T17:59:59Z",
    },
    created_at_utc: "2030-06-08T10:00:00Z",
    updated_at_utc: "2030-06-08T18:00:00Z",
    lock_at_utc: "2030-06-08T18:00:00Z",
    locked_at_utc: "2030-06-08T18:00:00Z",
    payload_sha256: "8f36a9d28be71d6c579bbd0d0e3a5ac3f0eb70a2a327721f739392f1a64107da",
  },
  result: { home_goals: 2, away_goals: 1, outcome: "home" },
  scoring: {
    user: { exact: 3, outcome: 1, bonus: 1, total: 5 },
    rivals: [
      { family: "dixon_coles", exact: 0, outcome: 1, total: 1 },
      { family: "poisson_independent", exact: 0, outcome: 0, total: 0 },
      { family: "bivariate_poisson", exact: 0, outcome: 0, total: 0 },
      { family: "elo_ordlogit", exact: 0, outcome: 0, total: 0 },
      { family: "climatological", exact: 0, outcome: 0, total: 0 },
    ],
    beat_ai: true,
    best_rival_total: 1,
  },
};

const STEPS: Array<{ icon: ReactNode; title: string; body: ReactNode }> = [
  { icon: <ScaleIcon />, title: "1 · Pick a score", body: "Choose the score you believe on any upcoming match. There is no entry fee, stake, or account." },
  { icon: <CalendarIcon />, title: "2 · Change freely until kickoff", body: "Edit or remove your call as often as you like while the match is open." },
  { icon: <LockIcon />, title: "3 · It locks at kickoff", body: "Golavo freezes the score and writes a SHA-256 fingerprint. Change one byte and the proof no longer matches." },
  { icon: <TrophyIcon />, title: "4 · Points arrive after full time", body: "The final result decides the score: exact score, right outcome, and a bonus only when your call beats every available rival." },
  { icon: <VersusIcon />, title: "5 · Race the models", body: <>Your season compares you with five deterministic rivals on exactly the matches you play. <a href="#/season">Open My Season ›</a></> },
];

export function PicksGuide() {
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.5rem" }}>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/">Matchday</a><ChevronRight size={14} /><span aria-current="page">How picks work</span>
      </nav>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>How picks work</h1>
        <p className="measure dim" style={{ margin: 0 }}>Make the score call you believe, lock it before kickoff, then see how you did against five transparent model rivals.</p>
      </header>

      <ol className="guide-steps">
        {STEPS.map((step) => (
          <li className="guide-step" key={step.title}>
            <div className="guide-step__icon" aria-hidden>{step.icon}</div>
            <div className="guide-step__body"><h2 className="guide-step__title">{step.title}</h2><p className="small" style={{ margin: ".2rem 0 0" }}>{step.body}</p></div>
          </li>
        ))}
      </ol>

      <section className="guide-example stack" aria-labelledby="pick-example-title">
        <div className="guide-example__head"><h2 id="pick-example-title" className="rail__title">One call, from lock to points</h2><span className="chip chip--voided">Made-up example — never counted</span></div>
        <div className="pick-guide-example">
          <div className="pick-ticket pick-ticket--locked"><div className="pick-ticket__kicker">YOUR CALL · AT KICKOFF</div><LockedPickState pick={EXAMPLE} preview /></div>
          <div className="pick-ticket pick-ticket--scored"><div className="pick-ticket__kicker">YOUR CALL · AFTER FULL TIME</div><ScoredPickState pick={EXAMPLE} /></div>
        </div>
      </section>

      <section aria-labelledby="points-title" className="stack" style={{ ["--gap" as string]: ".75rem" }}>
        <h2 id="points-title" className="rail__title">The points</h2>
        <div className="stat-grid"><StatTile value="+3" label="Exact score" tone="gold" /><StatTile value="+1" label="Right winner or draw" /><StatTile value="+1" label="Beat every model" /></div>
        <p className="small dim" style={{ margin: 0 }}>Exact and outcome points stack. The model bonus is strict: ties do not earn it, and unavailable rivals are ignored.</p>
      </section>

      <section className="stack" style={{ ["--gap" as string]: ".5rem" }} aria-label="Common questions">
        <h2 className="rail__title">Common questions</h2>
        <Drawer title="Is this gambling?"><p className="small">No — no money, no odds, no account. It is a private score-picking game against deterministic models.</p></Drawer>
        <Drawer title="Can the rivals see my pick?"><p className="small">No. Their calls come from the match analysis, not from you. Golavo hides them until you save yours to avoid anchoring your choice.</p></Drawer>
        <Drawer title="What if I skip a match?"><p className="small">Nothing happens. You and the models are scored only on matches you choose to play.</p></Drawer>
        <Drawer title="Why is there a fingerprint?"><p className="small">It proves the locked record has not changed. The same canonical pick bytes always produce the same SHA-256 fingerprint.</p></Drawer>
      </section>
    </div>
  );
}
