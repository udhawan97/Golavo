import type { FormEntry, MatchAnalysis, NotebookFact, CommentatorsNotebook } from "../lib/contract";
import { FACT_DISPLAY, FACT_SCOPE_TEXT } from "../lib/contract";
import { yearSpan } from "../lib/format";
import { topInsights } from "../lib/insights";
import { RateDial, SourcePopover } from "./CommentatorsNotebook";
import { buildElsewhere, factKey, groupFacts, type FactRow, type FactSide, type GroupedFacts } from "../lib/factPairs";
import { FormationPitch } from "./FormationPitch";
import { AlertIcon } from "./icons";
import { TeamStyleProfile } from "./TeamStyleProfile";
import { EmptyState } from "./states";
import { formStreakSentence, formVenue, goalDifferenceTrend, signedGoalDifference } from "../lib/matchProgramme";

interface FormationEnrichment {
  home?: string | null;
  away?: string | null;
  source_label: string;
}

interface MatchNotesProps {
  notebook: CommentatorsNotebook | null;
  analysis: MatchAnalysis | null;
  omitKeys?: ReadonlySet<string>;
  formation?: FormationEnrichment | null;
  expert?: boolean;
}

function displayValue(fact: NotebookFact): string {
  if (fact.base_rate !== null) return `${Math.round(fact.base_rate * 100)}%`;
  return fact.numbers[0]?.display ?? "—";
}

function FactSource({ fact }: { fact: NotebookFact }) {
  const span = yearSpan(fact.date_range);
  return (
    <div className="mn-fact__proof small">
      <span><b>{fact.sample_n.toLocaleString()}</b> {fact.sample_n === 1 ? "match" : "matches"}</span>
      <span>minimum {fact.min_sample}</span>
      {span && <span>{span}</span>}
      <span>{FACT_SCOPE_TEXT[fact.scope]}</span>
      <span>{fact.freshness.stale ? "stale" : `fresh to ${fact.freshness.last_event_utc.slice(0, 10)}`}</span>
      <span>Source <SourcePopover ids={fact.source_ids} snapshots={[]} /></span>
    </div>
  );
}

function FactCard({ fact, index }: { fact: NotebookFact; index?: number }) {
  const display = FACT_DISPLAY[fact.id] ?? { title: "Match record", explainer: "A source-backed fact from the available history." };
  return (
    <article className="mn-fact">
      {index !== undefined && <span className="mn-fact__number num" aria-hidden>{String(index).padStart(2, "0")}</span>}
      <span className="upper muted">{fact.subject}</span>
      <div className="mn-fact__headline"><strong className="num">{displayValue(fact)}</strong><h3>{display.title}</h3></div>
      <p>{display.explainer}</p>
      <details><summary>Full stat &amp; source</summary><p>{fact.text}</p><FactSource fact={fact} /></details>
    </article>
  );
}

/** One side of a comparison row. An absent side never renders a bare dash:
 * "displayed in another section" and "no fact qualified" are different claims,
 * and only the second one means the record does not exist. */
function CompareCell({ side, tone, rail, expert }: {
  side: FactSide;
  tone: "home" | "away";
  rail: boolean;
  expert?: boolean;
}) {
  const className = `mn-compare__cell mn-compare__cell--${tone}`;
  if (!side.fact) {
    const absence = side.absence ?? { kind: "unqualified" as const };
    return (
      <td className={`${className} mn-compare__cell--absent`}>
        {absence.kind === "unqualified" ? (
          <span className="mn-compare__absent">No qualifying sample</span>
        ) : absence.anchor ? (
          <a className="mn-compare__absent" href={absence.anchor}>Shown in {absence.section}</a>
        ) : (
          <span className="mn-compare__absent">Featured elsewhere in {absence.section}</span>
        )}
      </td>
    );
  }
  const fact = side.fact;
  return (
    <td className={className}>
      <span className="mn-compare__value num">{displayValue(fact)}</span>
      {rail && fact.base_rate !== null && (
        <span className="mn-compare__rail" aria-hidden>
          <span className="mn-compare__fill" style={{ width: `${Math.round(fact.base_rate * 100)}%` }} />
        </span>
      )}
      <details className="mn-compare__detail">
        <summary>Full stat</summary>
        <p>{fact.text}</p>
        {!expert && <FactSource fact={fact} />}
      </details>
      {expert && <FactSource fact={fact} />}
    </td>
  );
}

function CompareTable({ rows, home, away, expert, caption }: {
  rows: FactRow[];
  home: string;
  away: string;
  expert?: boolean;
  caption: string;
}) {
  if (rows.length === 0) return null;
  return (
    <table className="mn-compare__table">
      <caption className="visually-hidden">{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Stat</th>
          <th scope="col" className="mn-compare__team mn-compare__team--home">{home}</th>
          <th scope="col" className="mn-compare__team mn-compare__team--away">{away}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <th scope="row" className="mn-compare__stat">
              <span>{row.title}</span>
              {!expert && <p className="mn-compare__explainer">{row.explainer}</p>}
            </th>
            <CompareCell side={row.home} tone="home" rail={row.rail} expert={expert} />
            <CompareCell side={row.away} tone="away" rail={row.rail} expert={expert} />
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** The competition band, the paired comparison, and the rows only one side
 * qualifies for. Exported for direct testing. */
export function StatForStat({ grouped, home, away, expert }: {
  grouped: GroupedFacts;
  home: string;
  away: string;
  expert?: boolean;
}) {
  const { tournament, paired, solo, other } = grouped;
  if (!tournament.length && !paired.length && !solo.length && !other.length) return null;
  return (
    <section className="mn-section mn-compare" aria-labelledby="mn-stats-title">
      <div className="mn-section__head"><span className="upper">Deeper cut</span><h3 id="mn-stats-title">Stat for stat</h3></div>

      {tournament.length > 0 && (
        <div className="mn-compare__stage">
          <span className="upper">The tournament</span>
          <ul>
            {tournament.map((fact) => {
              const display = FACT_DISPLAY[fact.id] ?? { title: "Match record", explainer: "A source-backed fact from the available history." };
              return (
                <li key={factKey(fact)}>
                  <strong className="num">{displayValue(fact)}</strong>
                  <b>{display.title}</b>
                  <span>{display.explainer}</span>
                  <details className="mn-compare__detail">
                    <summary>Full stat &amp; source</summary>
                    <p>{fact.text}</p>
                    <FactSource fact={fact} />
                  </details>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <CompareTable
        rows={paired}
        home={home}
        away={away}
        expert={expert}
        caption={`${home} against ${away}, on the stats both teams qualify for.`}
      />

      {solo.length > 0 && (
        <div className="mn-compare__solo">
          <span className="upper">Only one side qualifies</span>
          <CompareTable
            rows={solo}
            home={home}
            away={away}
            expert={expert}
            caption={`Stats where only one of ${home} or ${away} has a qualifying record.`}
          />
        </div>
      )}

      {other.length > 0 && (
        <div className="mn-feature-grid mn-compare__other">
          {other.map((fact) => <FactCard fact={fact} key={factKey(fact)} />)}
        </div>
      )}
    </section>
  );
}

export function FormSparkline({ team, entries }: { team: string; entries: FormEntry[] }) {
  const values = goalDifferenceTrend(entries);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const spread = Math.max(1, max - min);
  const points = values.map((value, index) => {
    const x = values.length === 1 ? 30 : 2 + index * (56 / (values.length - 1));
    const y = 16 - ((value - min) / spread) * 12;
    return `${x},${y}`;
  }).join(" ");
  const equivalent = values.map(signedGoalDifference).join(", ");
  return (
    <div className="mn-form__trend">
      <svg className="form-sparkline__svg" viewBox="0 0 60 20" aria-hidden focusable="false">
        <line x1="2" x2="58" y1={16 - ((0 - min) / spread) * 12} y2={16 - ((0 - min) / spread) * 12} />
        <polyline points={points} />
      </svg>
      <span className="small dim">Goal difference · oldest to newest</span>
      <span className="visually-hidden">{team} goal-difference trend, oldest to newest: {equivalent}.</span>
    </div>
  );
}

function FormTimeline({ team, entries }: { team: string; entries: FormEntry[] }) {
  if (entries.length === 0) return <div className="mn-form"><b>{team}</b><span className="small dim">No prior results in this data.</span></div>;
  const streak = formStreakSentence(entries);
  return (
    <div className="mn-form">
      <b>{team}</b>
      <div className="mn-form__track" aria-label={`${team} last ${entries.length} results`}>
        {entries.map((entry, index) => {
          const venue = formVenue(entry);
          const venueMark = venue === "home" ? "H" : venue === "away" ? "A" : "N";
          const label = `${entry.result} ${entry.gf}–${entry.ga} against ${entry.opponent}, ${venue}`;
          return (
          <button type="button" className="mn-form__result" key={`${entry.date}-${index}`} aria-label={label} data-opponent={entry.opponent}>
            <span className={`mn-form__dot mn-form__dot--${entry.result.toLowerCase()}`}>{entry.result}</span>
            <span className="mn-form__score"><span className="num">{entry.gf}–{entry.ga}</span><span className="mn-form__venue" title={venue}>{venueMark}</span></span>
          </button>
          );
        })}
      </div>
      <FormSparkline team={team} entries={entries} />
      {streak && <p className="mn-form__streak">{streak}</p>}
    </div>
  );
}

const TIMING_BANDS = ["0–15", "15–30", "30–45", "45–60", "60–75", "75–90", "90+"];

function GoalTimingSpotlight({ timing, penalties, expert }: {
  timing: NotebookFact[];
  penalties: NotebookFact[];
  expert?: boolean;
}) {
  if (timing.length === 0) return null;
  return (
    <section className="mn-section mn-timing" aria-labelledby="mn-timing-title">
      <div className="mn-section__head"><span className="upper">Scoring clock</span><h3 id="mn-timing-title">When they score</h3></div>
      <div className="mn-timing__grid">
        {timing.map((fact) => {
          const phase = fact.values.phase === "opening" ? "opening" : fact.values.phase === "closing" ? "closing" : null;
          const penalty = penalties.find((item) => item.subject === fact.subject);
          return (
            <article className="mn-timing__team" key={factKey(fact)}>
              <header><strong>{fact.subject}</strong>{penalty && <span className="chip chip--neutral"><span className="num">{displayValue(penalty)}</span> penalty share</span>}</header>
              <figure>
                <svg viewBox="0 0 350 48" role="img" aria-label={`${fact.subject}: ${fact.text}`}>
                  {TIMING_BANDS.map((band, index) => {
                    const highlighted = phase === "opening" ? index === 0 : phase === "closing" ? index >= 5 : false;
                    return <rect key={band} x={index * 50 + 2} y={highlighted ? 5 : 13} width="46" height={highlighted ? 28 : 20} rx="3" className={highlighted ? "is-highlighted" : undefined} />;
                  })}
                </svg>
                <div className="mn-timing__labels" aria-hidden>{TIMING_BANDS.map((band) => <span className="num" key={band}>{band}</span>)}</div>
                <figcaption>{fact.text}</figcaption>
              </figure>
              {expert && <FactSource fact={fact} />}
            </article>
          );
        })}
      </div>
      <p className="small dim">Highlighted bands locate the guarded opening or closing phase reported by the engine; unhighlighted bands do not imply zero goals.</p>
    </section>
  );
}

function H2HBand({ fact }: { fact: NotebookFact }) {
  const wins = Number(fact.values.home_wins ?? 0);
  const draws = Number(fact.values.draws ?? 0);
  const losses = Number(fact.values.home_losses ?? 0);
  const total = Math.max(1, wins + draws + losses);
  return (
    <div className="mn-h2h">
      <div className="mn-h2h__bar" role="img" aria-label={`${wins} home wins, ${draws} draws, ${losses} away wins`}>
        <span className="mn-h2h__home" style={{ width: `${wins / total * 100}%` }} />
        <span className="mn-h2h__draw" style={{ width: `${draws / total * 100}%` }} />
        <span className="mn-h2h__away" style={{ width: `${losses / total * 100}%` }} />
      </div>
      <div className="mn-h2h__legend"><span>{wins} {wins === 1 ? "win" : "wins"}</span><span>{draws} {draws === 1 ? "draw" : "draws"}</span><span>{losses} {losses === 1 ? "loss" : "losses"}</span></div>
      <p>{fact.text}</p><FactSource fact={fact} />
    </div>
  );
}

/** One preparation path feeds every chapter extraction. The fact ranking,
 * quarantine, source proof, and display values stay exactly where they lived. */
function prepareNotes({
  notebook,
  analysis,
  omitKeys = new Set(),
  formation = null,
}: MatchNotesProps) {
  const visible = (notebook?.facts ?? []).filter((fact) => !omitKeys.has(factKey(fact)));
  const timing = visible.filter((fact) => fact.id === "goal_timing_profile");
  const timingSubjects = new Set(timing.map((fact) => fact.subject));
  const penalties = visible.filter((fact) => fact.id === "penalty_goal_share" && timingSubjects.has(fact.subject));
  const featuredKeys = new Set([...timing, ...penalties].map(factKey));
  const rankable = visible.filter((fact) => !featuredKeys.has(factKey(fact)));
  const visibleNotebook = notebook ? { ...notebook, facts: rankable } : null;
  const headlines = topInsights(visibleNotebook);
  const headlineKeys = new Set(headlines.map(factKey));
  const deep = rankable.filter((fact) => !headlineKeys.has(factKey(fact)));
  const editorial = deep.filter((fact) => fact.label !== "coincidence");
  const hero = editorial[0] ?? null;
  const scorers = editorial.filter((fact) => fact.id === "in_form_scorer" || fact.id === "top_scorer");
  const h2h = editorial.find((fact) => fact.id === "head_to_head_record") ?? null;
  const reserved = new Set([hero, h2h, ...scorers].filter(Boolean).map((fact) => factKey(fact!)));
  const cards = editorial.filter((fact) => !reserved.has(factKey(fact)));
  const coincidences = visible.filter((fact) => fact.label === "coincidence");
  const home = analysis?.match.home_team ?? notebook?.match.home_team ?? "Home";
  const away = analysis?.match.away_team ?? notebook?.match.away_team ?? "Away";
  // omitKeys is passed through rather than discarded: a fact another cockpit
  // panel consumed still exists, so a blank comparison side can say "featured
  // elsewhere" instead of implying the guardrails suppressed it.
  const grouped = groupFacts({
    cards,
    home,
    away,
    elsewhere: buildElsewhere({ headlines, hero, scorers, h2h, timing, penalties, omitted: omitKeys }),
  });
  return {
    notebook,
    analysis,
    formation,
    headlines,
    hero,
    scorers,
    h2h,
    cards,
    grouped,
    coincidences,
    timing,
    penalties,
    home,
    away,
    form: analysis?.team_form,
  };
}

/** Chapter 01 extraction: the existing last-five strip, with no duplicated
 * ranking or fetch ownership. */
export function MatchFormBook(props: MatchNotesProps) {
  const view = prepareNotes(props);
  if (!view.form) {
    return <EmptyState title="No recent form available">The model snapshot does not include a last-five sequence for this fixture.</EmptyState>;
  }
  return (
    <div className="mn programme-notes">
      <section className="mn-section" aria-label="Recent results">
        <div className="mn-form-grid">
          <FormTimeline team={view.home} entries={view.form[view.home] ?? []} />
          <FormTimeline team={view.away} entries={view.form[view.away] ?? []} />
        </div>
        <p className="small dim">Last five completed matches · pre-kickoff only.</p>
      </section>
    </div>
  );
}

/** Chapter 02 extraction: the same result-fitted profile and Expert reveal. */
export function MatchStyleBook(props: MatchNotesProps) {
  if (!props.analysis?.team_style) {
    return <EmptyState title="No style profile available">The goal model did not produce a fitted style profile for this fixture.</EmptyState>;
  }
  return (
    <div className="mn programme-notes mn-style">
      <TeamStyleProfile analysis={props.analysis} expert={props.expert} />
    </div>
  );
}

/** First movement of Chapter 03: head-to-head precedes the competition and
 * second-half stories that MatchDetail composes immediately after it. */
export function MatchHeadToHead(props: MatchNotesProps) {
  const { h2h } = prepareNotes(props);
  if (!h2h) return null;
  return (
    <div className="mn programme-notes">
      <section className="mn-section" aria-labelledby="mn-h2h-title">
        <div className="mn-section__head"><span className="upper">Head to head</span><h3 id="mn-h2h-title">When they’ve met</h3></div>
        <H2HBand fact={h2h} />
      </section>
    </div>
  );
}

/** The remainder of Chapter 03. Coincidences deliberately remain last among
 * the editorial records and outside the model/AI evidence path. */
export function MatchHistoryRecords(props: MatchNotesProps) {
  const view = prepareNotes(props);
  const hasBody = view.headlines.length > 0 || view.hero || view.cards.length || view.scorers.length || view.formation || view.timing.length > 0;
  return (
    <div className="mn programme-notes">
      <div className="mn-records-head small dim">
        <span>Deterministic · source-backed</span>
        <span>As of {view.notebook?.as_of_utc.slice(0, 10) ?? view.analysis?.information_cutoff_utc.slice(0, 10) ?? "—"}</span>
      </div>

      {!hasBody && view.coincidences.length === 0 ? <EmptyState title="No further match records">No deterministic facts cleared the sample and freshness guards. Nothing is invented to fill the page.</EmptyState> : null}

      {view.headlines.length > 0 && (
        <section className="mn-section mn-briefing" aria-labelledby="mn-briefing-title">
          <div className="mn-section__head"><span className="upper">Quick briefing</span><h3 id="mn-briefing-title">Three things to know</h3></div>
          <div className="mn-feature-grid">{view.headlines.map((fact, index) => <FactCard fact={fact} index={index + 1} key={factKey(fact)} />)}</div>
        </section>
      )}

      {view.hero && (
        <article className="mn-cover">
          <div><span className="upper">Cover story · {view.hero.subject}</span><div className="mn-cover__value num">{displayValue(view.hero)}</div></div>
          {view.hero.base_rate !== null && <RateDial value={view.hero.base_rate} />}
          <div className="mn-cover__copy"><h3 id="mn-cover-title">{FACT_DISPLAY[view.hero.id]?.title ?? "The headline number"}</h3><p>{view.hero.text}</p><FactSource fact={view.hero} /></div>
        </article>
      )}

      {view.scorers.length > 0 && <section className="mn-section" aria-labelledby="mn-scorers-title"><div className="mn-section__head"><span className="upper">Players</span><h3 id="mn-scorers-title">Scorer spotlight</h3></div><div className="mn-feature-grid">{view.scorers.map((fact, index) => <FactCard fact={fact} index={index + 1} key={factKey(fact)} />)}</div></section>}

      <GoalTimingSpotlight timing={view.timing} penalties={view.penalties} expert={props.expert} />

      {view.formation && (view.formation.home || view.formation.away) && <section className="mn-section" aria-labelledby="mn-formation-title"><div className="mn-section__head"><span className="upper">Optional enrichment</span><h3 id="mn-formation-title">Typical formation</h3></div><span className="chip chip--neutral">typical, from recent lineups — not today’s team sheet</span><div className="mn-formations">{view.formation.home && <FormationPitch formation={view.formation.home} team={view.home} />}{view.formation.away && <FormationPitch formation={view.formation.away} team={view.away} />}</div><p className="small dim">Source: {view.formation.source_label}. Display-only; never used by a model or pick.</p></section>}

      <StatForStat grouped={view.grouped} home={view.home} away={view.away} expert={props.expert} />

      {view.coincidences.length > 0 && <aside className="mn-pub" aria-labelledby="mn-pub-title"><div className="mn-pub__head"><AlertIcon /><div><span className="upper">Quarantined coincidence</span><h3 id="mn-pub-title">For the pub</h3></div></div><p className="small">For the pub, not the forecast — capped at {view.notebook?.coincidence_cap ?? view.coincidences.length}, never shown to the AI.</p>{view.coincidences.map((fact, index) => <FactCard fact={fact} index={index + 1} key={factKey(fact)} />)}</aside>}

    </div>
  );
}

/** One programme-wide provenance footer. The content is the existing notebook
 * footer recast as a colophon, not a second source summary. */
export function MatchNotesColophon({ notebook }: { notebook: CommentatorsNotebook | null }) {
  if (!notebook) return null;
  return (
    <footer className="programme-colophon" aria-label="Matchday programme colophon">
      <div className="programme-colophon__masthead">
        <span className="upper">Colophon</span>
        <strong>Deterministic · source-backed</strong>
      </div>
      <dl>
        <div><dt>Rule set</dt><dd className="num">{notebook.registry_version}</dd></div>
        <div><dt>As of</dt><dd className="num">{notebook.as_of_utc.slice(0, 10)}</dd></div>
        <div><dt>Fact checks</dt><dd><span className="num">{notebook.family_size}</span> fixed</dd></div>
        <div><dt>Suppressed</dt><dd><span className="num">{notebook.suppressed.length}</span> by guards</dd></div>
        <div className="programme-colophon__sources"><dt>Source IDs</dt><dd className="num">{notebook.source_ids.join(", ") || "none"}</dd></div>
      </dl>
    </footer>
  );
}

/** Backward-compatible composition for any non-cockpit consumer. */
export function MatchNotes(props: MatchNotesProps) {
  const view = prepareNotes(props);
  return (
    <section className="stack" aria-label="Match notes" style={{ ["--gap" as string]: "1rem" }}>
      <MatchFormBook {...props} />
      <MatchStyleBook {...props} />
      {view.h2h && <MatchHeadToHead {...props} />}
      <MatchHistoryRecords {...props} />
      <MatchNotesColophon notebook={props.notebook} />
    </section>
  );
}
