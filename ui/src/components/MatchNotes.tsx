import type { FormEntry, MatchAnalysis, NotebookFact, CommentatorsNotebook } from "../lib/contract";
import { FACT_DISPLAY, FACT_SCOPE_TEXT } from "../lib/contract";
import { yearSpan } from "../lib/format";
import { topInsights } from "../lib/insights";
import { factKey, RateDial, SourcePopover } from "./CommentatorsNotebook";
import { FormationPitch } from "./FormationPitch";
import { AlertIcon } from "./icons";
import { TeamStyleProfile } from "./TeamStyleProfile";
import { EmptyState } from "./states";

interface FormationEnrichment {
  home?: string | null;
  away?: string | null;
  source_label: string;
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

function FactCard({ fact, index }: { fact: NotebookFact; index: number }) {
  const display = FACT_DISPLAY[fact.id] ?? { title: "Match record", explainer: "A source-backed fact from the available history." };
  return (
    <article className="mn-fact">
      <span className="mn-fact__number num" aria-hidden>{String(index).padStart(2, "0")}</span>
      <span className="upper muted">{fact.subject}</span>
      <div className="mn-fact__headline"><strong className="num">{displayValue(fact)}</strong><h3>{display.title}</h3></div>
      <p>{display.explainer}</p>
      <details><summary>Full stat &amp; source</summary><p>{fact.text}</p><FactSource fact={fact} /></details>
    </article>
  );
}

function FormTimeline({ team, entries }: { team: string; entries: FormEntry[] }) {
  if (entries.length === 0) return <div className="mn-form"><b>{team}</b><span className="small dim">No prior results in this data.</span></div>;
  return (
    <div className="mn-form">
      <b>{team}</b>
      <div className="mn-form__track" aria-label={`${team} last ${entries.length} results`}>
        {entries.map((entry, index) => (
          <div className="mn-form__result" key={`${entry.date}-${index}`} title={`${entry.result} ${entry.gf}–${entry.ga} v ${entry.opponent}`}>
            <span className={`mn-form__dot mn-form__dot--${entry.result.toLowerCase()}`}>{entry.result}</span>
            <span className="num">{entry.gf}–{entry.ga}</span>
          </div>
        ))}
      </div>
    </div>
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

export function MatchNotes({
  notebook,
  analysis,
  omitKeys = new Set(),
  formation = null,
  expert = false,
}: {
  notebook: CommentatorsNotebook | null;
  analysis: MatchAnalysis | null;
  omitKeys?: ReadonlySet<string>;
  formation?: FormationEnrichment | null;
  expert?: boolean;
}) {
  const visible = notebook?.facts.filter((fact) => !omitKeys.has(factKey(fact))) ?? [];
  const visibleNotebook = notebook ? { ...notebook, facts: visible } : null;
  const headlineKeys = new Set(topInsights(visibleNotebook).map(factKey));
  const deep = visible.filter((fact) => !headlineKeys.has(factKey(fact)));
  const editorial = deep.filter((fact) => fact.label !== "coincidence");
  const hero = editorial[0] ?? null;
  const scorers = editorial.filter((fact) => fact.id === "in_form_scorer" || fact.id === "top_scorer");
  const h2h = editorial.find((fact) => fact.id === "head_to_head_record") ?? null;
  const reserved = new Set([hero, h2h, ...scorers].filter(Boolean).map((fact) => factKey(fact!)));
  const cards = editorial.filter((fact) => !reserved.has(factKey(fact)));
  const coincidences = visible.filter((fact) => fact.label === "coincidence");
  const home = analysis?.match.home_team ?? notebook?.match.home_team ?? "Home";
  const away = analysis?.match.away_team ?? notebook?.match.away_team ?? "Away";
  const form = analysis?.team_form;
  const hasBody = hero || cards.length || scorers.length || h2h || form || analysis?.team_style || formation;

  return (
    <section className="mn" aria-labelledby="mn-title">
      <header className="mn-masthead">
        <div><span className="upper">Deterministic · source-backed</span><h2 id="mn-title">Match Notes</h2></div>
        <div className="mn-folio small dim"><span>As of {notebook?.as_of_utc.slice(0, 10) ?? analysis?.information_cutoff_utc.slice(0, 10) ?? "—"}</span><span>Rule set {notebook?.registry_version ?? "—"}</span></div>
      </header>
      <p className="mn-deck">The form, records and source-backed details behind this fixture. Descriptive history only — never a forecast, and no AI wrote it.</p>

      {!hasBody ? <EmptyState title="No match notes for this fixture">No deterministic facts cleared the sample and freshness guards. Nothing is invented to fill the page.</EmptyState> : null}

      {hero && (
        <article className="mn-cover">
          <div><span className="upper">Cover story · {hero.subject}</span><div className="mn-cover__value num">{displayValue(hero)}</div></div>
          {hero.base_rate !== null && <RateDial value={hero.base_rate} />}
          <div className="mn-cover__copy"><h3>{FACT_DISPLAY[hero.id]?.title ?? "The headline number"}</h3><p>{hero.text}</p><FactSource fact={hero} /></div>
        </article>
      )}

      {form && (
        <section className="mn-section" aria-labelledby="mn-form-title"><div className="mn-section__head"><span className="upper">01 · Recent results</span><h3 id="mn-form-title">The form book</h3></div><div className="mn-form-grid"><FormTimeline team={home} entries={form[home] ?? []} /><FormTimeline team={away} entries={form[away] ?? []} /></div><p className="small dim">Last five completed matches · pre-kickoff only.</p></section>
      )}

      {analysis?.team_style && <section className="mn-section mn-style" aria-label="How they play"><div className="mn-section__head"><span className="upper">02 · Fitted from results</span><h3>How they play</h3></div><TeamStyleProfile analysis={analysis} expert={expert} /></section>}

      {scorers.length > 0 && <section className="mn-section" aria-labelledby="mn-scorers-title"><div className="mn-section__head"><span className="upper">03 · Players</span><h3 id="mn-scorers-title">Scorer spotlight</h3></div><div className="mn-feature-grid">{scorers.map((fact, index) => <FactCard fact={fact} index={index + 1} key={factKey(fact)} />)}</div></section>}

      {h2h && <section className="mn-section" aria-labelledby="mn-h2h-title"><div className="mn-section__head"><span className="upper">04 · Head to head</span><h3 id="mn-h2h-title">When they’ve met</h3></div><H2HBand fact={h2h} /></section>}

      {formation && (formation.home || formation.away) && <section className="mn-section" aria-labelledby="mn-formation-title"><div className="mn-section__head"><span className="upper">05 · Optional enrichment</span><h3 id="mn-formation-title">Typical formation</h3></div><span className="chip chip--neutral">typical, from recent lineups — not today’s team sheet</span><div className="mn-formations">{formation.home && <FormationPitch formation={formation.home} team={home} />}{formation.away && <FormationPitch formation={formation.away} team={away} />}</div><p className="small dim">Source: {formation.source_label}. Display-only; never used by a model or pick.</p></section>}

      {cards.length > 0 && <section className="mn-section" aria-labelledby="mn-stats-title"><div className="mn-section__head"><span className="upper">06 · Deeper cut</span><h3 id="mn-stats-title">Signature stats &amp; records</h3></div><div className="mn-stats-grid">{cards.map((fact, index) => <FactCard fact={fact} index={index + 1} key={factKey(fact)} />)}</div></section>}

      {coincidences.length > 0 && <aside className="mn-pub" aria-labelledby="mn-pub-title"><div className="mn-pub__head"><AlertIcon /><div><span className="upper">Quarantined coincidence</span><h3 id="mn-pub-title">For the pub</h3></div></div><p className="small">For the pub, not the forecast — capped at {notebook?.coincidence_cap ?? coincidences.length}, never shown to the AI.</p>{coincidences.map((fact, index) => <FactCard fact={fact} index={index + 1} key={factKey(fact)} />)}</aside>}

      {notebook && <footer className="mn-sources small dim"><span>{notebook.family_size} fixed fact-checks · rule set {notebook.registry_version}</span><span>{notebook.suppressed.length} candidate{notebook.suppressed.length === 1 ? "" : "s"} suppressed by sample / staleness / cap guards</span><span>Sources: {notebook.source_ids.join(", ") || "none"}</span></footer>}
    </section>
  );
}
