import type { SourceKind } from "../lib/contract";
import type { WorldCupAward, WorldCupPedigreeData, WorldCupTeamPedigree } from "../lib/factValues";
import { yearSpan } from "../lib/format";
import { SourcePopover } from "./CommentatorsNotebook";
import { SparkIcon, StarIcon } from "./icons";

const POSITION = {
  1: "Champions",
  2: "Runners-up",
  3: "Third place",
  4: "Fourth place",
} as const;

function titleLabel(team: WorldCupTeamPedigree): string {
  const years = team.titleYears;
  if (years.length === 0) return "0 World Cup titles";
  const joined = years.length === 1 ? String(years[0]) : `${years.slice(0, -1).join(", ")} and ${years.at(-1)}`;
  return `${team.titles} World Cup ${team.titles === 1 ? "title" : "titles"}, won ${joined}`;
}

function Awards({ awards }: { awards: WorldCupAward[] }) {
  if (awards.length === 0) return null;
  const render = (award: WorldCupAward) => (
    <li key={`${award.year}-${award.award}-${award.player}`}>
      <SparkIcon size={14} />
      <span>{award.award}</span>
      <b>{award.player}</b>
      <span className="dim num">{award.year}</span>
    </li>
  );
  return (
    <div className="wcp-awards">
      <h4>Individual awards</h4>
      <ul>{awards.slice(0, 4).map(render)}</ul>
      {awards.length > 4 && (
        <details>
          <summary>{awards.length - 4} more awards</summary>
          <ul>{awards.slice(4).map(render)}</ul>
        </details>
      )}
    </div>
  );
}

function TeamShelf({
  team,
  data,
  away = false,
}: {
  team: string;
  data: WorldCupTeamPedigree | null;
  away?: boolean;
}) {
  if (!data) {
    return (
      <div className={`wcp-team${away ? " wcp-team--away" : ""}`}>
        <h3>{team}</h3>
        <p className="small dim">
          No World Cup record cleared the guards for {team} — nothing is invented to fill the gap.
        </p>
      </div>
    );
  }
  return (
    <div className={`wcp-team${away ? " wcp-team--away" : ""}`}>
      <h3>{team}</h3>
      <div className="wcp-stars" role="img" aria-label={titleLabel(data)}>
        <span className="wcp-stars__row" aria-hidden>
          {Array.from({ length: Math.min(data.titles, 5) }, (_, index) => (
            <StarIcon key={index} filled />
          ))}
        </span>
        <strong className="num">{data.titles}</strong>
      </div>
      {data.titleYears.length > 0 && (
        <div className="wcp-years" aria-label="Title years">
          {data.titleYears.map((year) => <span key={year}>{year}</span>)}
        </div>
      )}
      <dl className="wcp-records">
        <div><dt>Finals</dt><dd>{data.finals}</dd></div>
        <div><dt>Appearances</dt><dd>{data.appearances}</dd></div>
        {data.bestRecent && POSITION[data.bestRecent.position] && (
          <div>
            <dt>Best recent</dt>
            <dd>{POSITION[data.bestRecent.position]} <span className="dim num">{data.bestRecent.year}</span></dd>
          </div>
        )}
      </dl>
      <Awards awards={data.awards} />
      <div className="small muted wcp-source">
        Source <SourcePopover ids={data.sourceIds} snapshots={[]} />
      </div>
    </div>
  );
}

export function WorldCupPedigree({
  competition,
  sourceKind,
  story,
  headingLevel = 2,
}: {
  competition: string;
  sourceKind: SourceKind;
  story: WorldCupPedigreeData | null;
  headingLevel?: 2 | 3;
}) {
  if (competition !== "FIFA World Cup" || sourceKind !== "international" || !story) return null;
  const era = yearSpan(story.dateRange);
  const Heading = headingLevel === 3 ? "h3" : "h2";
  return (
    <section className="panel wcp" aria-labelledby="wcp-h">
      <div className="panel__head">
        <Heading id="wcp-h">World Cup pedigree</Heading>
        {era && <span className="chip chip--neutral wcp-era">{era}</span>}
      </div>
      <div className="panel__body wcp-grid">
        <TeamShelf team={story.homeTeam} data={story.home} />
        <TeamShelf team={story.awayTeam} data={story.away} away />
      </div>
    </section>
  );
}
