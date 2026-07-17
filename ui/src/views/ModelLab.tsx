/**
 * Model Lab — the credibility surface, relocated from the top-level nav.
 *
 * Track record (real sealed→scored forecasts), Backtests (held-out folds),
 * Methodologies (what the models are and how honest the plurality is), and the
 * sealed-forecast list all live here. None of this was deleted in the pivot — it
 * moved behind the product, where the audit machinery belongs.
 */
import { ChevronRight } from "../components/icons";

export function ModelLabHub() {
  const links = [
    {
      href: "#/guide/picks",
      title: "How picks work",
      note: "Call a score, lock it at kickoff, and race five transparent model rivals across your season.",
    },
    {
      href: "#/lab/track-record",
      title: "Track record",
      note: "Your real forecasts, sealed before kickoff and scored after — running log loss, Brier, and reliability.",
    },
    {
      href: "#/lab/backtests",
      title: "Backtests",
      note: "Every model over held-out seasons: log loss, Brier, RPS, ECE. No permanent champion.",
    },
    {
      href: "#/lab/worldcup-2026",
      title: "World Cup 2026 retrospective",
      note: "Every match replayed at its own pre-kickoff cutoff, and — kept separate — whether the models had skill. A backtest, never a record.",
    },
    {
      href: "#/lab/ratings",
      title: "Golavo Ratings",
      note: "An in-house national-team Elo table from public results — leak-safe, with each team's trend. Not the FIFA ranking.",
    },
    {
      href: "#/lab/methods",
      title: "Methodologies",
      note: "What the five families are, why three of them are one voice, and how abstention works.",
    },
    {
      href: "#/lab/forecasts",
      title: "Sealed forecasts",
      note: "The immutable artifacts you’ve sealed, newest first.",
    },
    {
      href: "#/guide/sealing",
      title: "Sealing guide",
      note: "New to sealing? How a forecast gets on the record, in plain terms — with a worked example.",
    },
  ];
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Model Lab</h1>
        <p className="measure dim" style={{ margin: 0 }}>
          How the models are built, how honest they are, and how your sealed forecasts have actually
          done. The provenance and audit machinery lives here — the product up front stays about the
          games.
        </p>
      </header>
      <div className="league-grid">
        {links.map((l) => (
          <a key={l.href} className="league-card" href={l.href}>
            <div className="league-card__name">{l.title}</div>
            <div className="league-card__note small muted">{l.note}</div>
            <ChevronRight size={16} />
          </a>
        ))}
      </div>
    </div>
  );
}

export function Methodologies() {
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.25rem" }}>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/lab">Model Lab</a>
        <ChevronRight size={14} />
        <span aria-current="page">Methodologies</span>
      </nav>
      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Methodologies</h1>
        <p className="measure dim" style={{ margin: 0 }}>
          Golavo fits five deterministic model families — but they are not five independent
          opinions. Here is the honest picture.
        </p>
      </header>

      <section className="panel">
        <div className="panel__head"><h2>Two voices and a baseline</h2></div>
        <div className="panel__body stack measure" style={{ ["--gap" as string]: ".8rem" }}>
          <p style={{ margin: 0 }}>
            <strong>Ratings — Elo (ordered logit).</strong> Tracks overall team strength from
            results and maps the rating gap to home/draw/away. It models no goal process, so it
            carries no exact-score grid.
          </p>
          <p style={{ margin: 0 }}>
            <strong>Goals — Dixon–Coles.</strong> Fits weighted attack and defence rates and a
            low-score correction, giving 1X2, expected goals, and a full exact-score distribution
            that are coherent by construction.
          </p>
          <p style={{ margin: 0 }}>
            <strong>Baseline — climatology.</strong> League-wide base rates that ignore the teams.
            Shown for reference, never as a third opinion: a voice earns its keep only by beating
            this.
          </p>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head"><h2>Why three of the families are one voice</h2></div>
        <div className="panel__body stack measure" style={{ ["--gap" as string]: ".8rem" }}>
          <p style={{ margin: 0 }}>
            Independent Poisson, Dixon–Coles, and bivariate Poisson share a single fitting class and
            differ only in how they shape the low-score corner of the grid. On our data the
            independent and bivariate variants produce identical numbers in every backtest fold — so
            treating them as separate votes would be false plurality. The cockpit shows Dixon–Coles
            as the goal voice and discloses the variants as exactly that: variants.
          </p>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head"><h2>No permanent champion · honest abstention</h2></div>
        <div className="panel__body stack measure" style={{ ["--gap" as string]: ".8rem" }}>
          <p style={{ margin: 0 }}>
            Which method leads depends on the league and season — Elo tends to lead the near-neutral
            internationals, the goal model tends to lead the higher home-advantage leagues, and the
            ranking flips across folds. Golavo never averages them into a synthetic consensus.
          </p>
          <p style={{ margin: 0 }}>
            When either side has too little history, every model <em>abstains</em> rather than
            guessing. See the numbers behind all this in the{" "}
            <a href="#/lab/backtests">backtests ›</a>
          </p>
        </div>
      </section>
    </div>
  );
}
