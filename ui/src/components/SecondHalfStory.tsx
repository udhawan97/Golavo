import type { SourceKind } from "../lib/contract";
import type { HalfTimeStoryData, HalfTimeTeamStory } from "../lib/factValues";
import { SourcePopover } from "./CommentatorsNotebook";
import { MirrorRow } from "./TeamStyleProfile";

function saved(team: HalfTimeTeamStory): number {
  return team.comebackWins + team.comebackDraws;
}

function savedLabel(team: HalfTimeTeamStory): string {
  return `${team.team} saved ${saved(team)} of ${team.deficits} half-time deficits (${team.comebackWins} wins, ${team.comebackDraws} draws)`;
}

function leadLabel(team: HalfTimeTeamStory): string {
  return `${team.team} won ${team.leadsWon} of ${team.leads} matches after leading at half-time (${team.leadsDrawn} draws)`;
}

export function SecondHalfStory({
  sourceKind,
  story,
}: {
  sourceKind: SourceKind;
  story: HalfTimeStoryData | null;
}) {
  if (sourceKind !== "club" || !story) return null;
  return (
    <section className="panel shs" aria-labelledby="shs-h">
      <div className="panel__head">
        <h2 id="shs-h">Second-half story</h2>
        <span className="chip chip--neutral" style={{ marginLeft: "auto" }}>
          recorded half-times only
        </span>
      </div>
      <div className="panel__body stack" style={{ ["--gap" as string]: ".8rem" }}>
        <div className="style-profile__teams small muted">
          <span>{story.home.team}</span>
          <span>{story.away.team}</span>
        </div>
        <MirrorRow
          label="Saved from behind"
          homeFrac={saved(story.home) / story.home.deficits}
          awayFrac={saved(story.away) / story.away.deficits}
          homeText={`${saved(story.home)}/${story.home.deficits}`}
          awayText={`${saved(story.away)}/${story.away.deficits}`}
          expert
          ariaLabel={`${savedLabel(story.home)}; ${savedLabel(story.away)}`}
        />
        <MirrorRow
          label="Leads kept"
          homeFrac={story.home.leadsWon / story.home.leads}
          awayFrac={story.away.leadsWon / story.away.leads}
          homeText={`${story.home.leadsWon}/${story.home.leads}`}
          awayText={`${story.away.leadsWon}/${story.away.leads}`}
          expert
          ariaLabel={`${leadLabel(story.home)}; ${leadLabel(story.away)}`}
        />
        <p className="small dim" style={{ margin: 0 }}>
          Counted only over matches with a recorded half-time score — older seasons in the pack
          lack one.
        </p>
        <div className="small muted">
          Source <SourcePopover ids={story.sourceIds} snapshots={[]} />
        </div>
      </div>
    </section>
  );
}
