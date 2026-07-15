/**
 * Sealing, explained — a plain-language guide for the app's one side feature.
 *
 * Sealing used to be over-promoted and confusing; it now lives here, off the main
 * analytics path. This page teaches it in layman terms with icons and steps, and
 * shows ONE annotated synthetic example (bundled UI-side, never a real forecast)
 * so a reader sees what a seal looks like without any sample masquerading as data.
 */
import type { ForecastArtifact } from "../lib/contract";
import { utc } from "../lib/format";
import { ProbabilityBar } from "../components/primitives";
import { SealStamp } from "../components/SealStamp";
import { Drawer } from "../components/disclosure";
import {
  CalendarIcon,
  ChevronRight,
  ScaleIcon,
  SealIcon,
  ShieldCheckIcon,
  TrophyIcon,
} from "../components/icons";
import { DOCS_URL } from "../lib/links";
// A single synthetic teaching example — bundled with the UI, clearly labelled,
// and never linked to a real forecast route.
import sampleJson from "../mocks/forecasts/fa_5cb65a59b038d9586aea.json";

const sample = sampleJson as unknown as ForecastArtifact;

interface Step {
  icon: React.ReactNode;
  title: string;
  body: React.ReactNode;
}

const STEPS: Step[] = [
  {
    icon: <CalendarIcon size={18} />,
    title: "1 · Pick an upcoming international",
    body: (
      <>
        Open an upcoming men’s senior international from <a href="#/">Matchday → Upcoming</a> or the{" "}
        <a href="#/league/internationals">Internationals</a> page. Club competitions can’t be sealed —
        they’re bundled as historical data for backtesting, not forward forecasts.
      </>
    ),
  },
  {
    icon: <ScaleIcon size={18} />,
    title: "2 · Read the council",
    body: (
      <>
        The Match Cockpit fits five models and shows where they agree and where they don’t. Golavo
        never averages them into one confident-looking number — disagreement is information.
      </>
    ),
  },
  {
    icon: <SealIcon size={18} />,
    title: "3 · Seal it before kickoff",
    body: (
      <>
        Sealing freezes the forecast and its exact inputs, writes it once, and stamps it with a
        SHA-256 fingerprint. It runs offline and is deterministic — the same inputs reproduce the
        same artifact byte-for-byte. A seal can never be edited after the fact; that’s the point.
      </>
    ),
  },
  {
    icon: <TrophyIcon size={18} />,
    title: "4 · Scored after full time",
    body: (
      <>
        Once the match finishes, Golavo scores the sealed probabilities against the real result. The
        score rewards honest confidence and punishes overconfidence — a bold call that comes off
        scores well; a bold call that misses scores badly.
      </>
    ),
  },
  {
    icon: <ShieldCheckIcon size={18} />,
    title: "5 · It joins your track record",
    body: (
      <>
        Every sealed → scored forecast lands in <a href="#/lab/track-record">Model Lab → Track
        record</a>, misses included. That running record — never the backtests — is your honest
        forward performance.
      </>
    ),
  },
];

export function SealingGuide() {
  return (
    <div className="stack" style={{ ["--gap" as string]: "1.5rem" }}>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/">Matchday</a>
        <ChevronRight size={14} />
        <span aria-current="page">Sealing guide</span>
      </nav>

      <header className="stack" style={{ ["--gap" as string]: ".4rem" }}>
        <h1>Sealing — the trust machinery (expert)</h1>
        <p className="measure dim" style={{ margin: 0 }}>
          Looking for the score-picking game? <a href="#/guide/picks">How picks work ›</a> Sealing is the expert audit layer: a model prediction only counts if it’s locked in <b>before</b> kickoff — everything else is
          hindsight. Sealing is Golavo’s way of putting a forecast on the record, honestly and
          permanently. It’s optional: the deep analytics work on every match without it.
        </p>
      </header>

      <ol className="guide-steps">
        {STEPS.map((s) => (
          <li key={s.title} className="guide-step">
            <div className="guide-step__icon" aria-hidden>{s.icon}</div>
            <div className="guide-step__body">
              <h2 className="guide-step__title">{s.title}</h2>
              <p className="small" style={{ margin: ".2rem 0 0" }}>{s.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <section className="guide-example" aria-label="Annotated example">
        <div className="guide-example__head">
          <h2 className="rail__title">What a seal looks like</h2>
          <span className="chip chip--voided">Synthetic example — never counted</span>
        </div>
        <p className="small dim" style={{ margin: 0 }}>
          A worked example so you can see the parts. This forecast is fabricated for illustration —
          it’s not in your ledger and never touches your track record.
        </p>
        <div className="guide-example__grid">
          <div className="card guide-example__forecast">
            <div className="small muted">{sample.match.competition}</div>
            <div className="guide-example__teams">
              <b>{sample.match.home_team}</b> <span className="muted">v</span>{" "}
              <b>{sample.match.away_team}</b>
            </div>
            {sample.forecast.probs && (
              <ProbabilityBar
                probs={sample.forecast.probs}
                home={sample.match.home_team}
                away={sample.match.away_team}
              />
            )}
            <p className="small dim" style={{ margin: ".5rem 0 0" }}>
              Sealed {utc(sample.forecast.sealed_at_utc)} — before the {utc(sample.match.kickoff_utc)}{" "}
              kickoff. These probabilities are now frozen.
            </p>
          </div>
          <SealStamp artifact={sample} />
        </div>
        <ul className="guide-example__notes small">
          <li><b>Sealed at</b> is stamped before kickoff — proof the call came first, not after.</li>
          <li><b>Horizon</b> is how long before kickoff it was sealed.</li>
          <li><b>Payload sha256</b> is a fingerprint of every input. Change one byte and Golavo refuses to show the artifact — that’s the tamper-evidence.</li>
        </ul>
      </section>

      <section className="stack" style={{ ["--gap" as string]: ".5rem" }} aria-label="Common questions">
        <h2 className="rail__title">Common questions</h2>
        <Drawer title="Why can’t I seal club competition matches?">
          <p className="small">
            The open club datasets are bundled as history for backtesting, with no forward feed.
            Men’s senior internationals are the one surface that refreshes on demand, so they’re the
            only fixtures Golavo can honestly seal ahead of kickoff.
          </p>
        </Drawer>
        <Drawer title="Can a seal be changed later?">
          <p className="small">
            No. A seal writes once and is stamped with a fingerprint of its inputs. If anything
            changed, the fingerprint wouldn’t match and Golavo would refuse to display it. That
            immutability is exactly what makes a track record trustworthy.
          </p>
        </Drawer>
        <Drawer title="What if the models don’t have enough history?">
          <p className="small">
            Golavo abstains rather than guess. An abstained forecast is recorded honestly as “no
            call” — it neither helps nor pads your track record.
          </p>
        </Drawer>
      </section>

      <p className="small dim" style={{ margin: 0 }}>
        <a href={DOCS_URL} target="_blank" rel="noreferrer">Full documentation ›</a>{" · "}
        <a href="#/">Back to Matchday ›</a>
      </p>
    </div>
  );
}
