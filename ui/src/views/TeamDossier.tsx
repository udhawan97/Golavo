import { FollowButton } from "../components/FollowButton";
import { useState, type ReactNode } from "react";
import {
  clubImportance,
  projectionCoverageCaveat,
  RUN_IN_LENGTH,
  topStake,
} from "../components/SeasonOutlook";
import { BlockSkeleton, EmptyState, ErrorState } from "../components/states";
import {
  clearApiCache,
  fetchClubRatings,
  fetchCompetitionAnalytics,
  fetchSeasonOutlook,
} from "../lib/api";
import type { CompetitionAnalytics, RatingsTable, SeasonOutlook } from "../lib/contract";
import { useDataGenerationRevision } from "../lib/data-refresh-context";
import { num, pctWhole, utc, utcDate } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { LEAGUES } from "../lib/leagues";

function ordinal(value: number): string {
  const remainder = value % 100;
  const suffix = remainder >= 11 && remainder <= 13
    ? "th"
    : value % 10 === 1
      ? "st"
      : value % 10 === 2
        ? "nd"
        : value % 10 === 3
          ? "rd"
          : "th";
  return `${value}${suffix}`;
}

function EvidenceMetric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="team-dossier__metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}

function ContextUnavailable({ children }: { children: ReactNode }) {
  return <p className="team-dossier__unavailable small dim">{children}</p>;
}

function AnalyticsEvidence({ data, team }: { data: CompetitionAnalytics; team: string }) {
  const pulse = data.current_season.teams.find((item) => item.team === team);
  const strength = data.strength_trends.teams.find((item) => item.team === team);
  const workload = data.rest_congestion.teams.find((item) => item.team === team);
  const schedule = data.schedule_difficulty.teams.find((item) => item.team === team);

  return (
    <>
      <p className="small dim">Analytics sources: {data.provenance.source_ids.join(", ") || "unavailable"}. Index fingerprint: <code>{data.provenance.index_sha256 ?? "unavailable"}</code>.</p>
      <div className="team-dossier__context-group">
        <h3>Current-season sample</h3>
        {data.current_season.status === "available" && pulse ? (
          <div className="team-dossier__metrics">
            <EvidenceMetric label="Points / match" value={num(pulse.points_per_game, 2)} />
            <EvidenceMetric label="Goals / match" value={num(pulse.goals_for_per_match, 2)} />
            <EvidenceMetric label="Against / match" value={num(pulse.goals_against_per_match, 2)} />
            <EvidenceMetric label="Clean sheets" value={String(pulse.clean_sheets)} />
          </div>
        ) : (
          <ContextUnavailable>{data.current_season.reason ?? "No exact current-season sample for this team."}</ContextUnavailable>
        )}
      </div>

      <div className="team-dossier__context-group">
        <h3>Competition-local strength</h3>
        {data.strength_trends.status === "available" && strength ? (
          <div className="team-dossier__metrics">
            <EvidenceMetric label="Overall strength" value={num(strength.current.overall_index, 1)} note="100 = competition baseline" />
            <EvidenceMetric label="Attack" value={num(strength.current.attack_index, 1)} />
            <EvidenceMetric label="Defence" value={num(strength.current.defence_index, 1)} />
          </div>
        ) : (
          <ContextUnavailable>{data.strength_trends.reason ?? "No exact strength record for this team."}</ContextUnavailable>
        )}
      </div>

      <div className="team-dossier__context-group">
        <h3>Workload &amp; run-in</h3>
        <div className="team-dossier__metrics">
          {data.rest_congestion.status === "available" && workload ? (
            <>
              <EvidenceMetric label="Recovery" value={`${workload.rest_days} days rest`} />
              <EvidenceMetric label="28-day load" value={`${workload.matches_last_28_days} matches`} note={workload.congestion} />
            </>
          ) : (
            <ContextUnavailable>{data.rest_congestion.reason ?? "No exact workload record for this team."}</ContextUnavailable>
          )}
          {data.schedule_difficulty.status === "available" && schedule ? (
            <>
              <EvidenceMetric label="Run-in difficulty" value={ordinal(schedule.rank)} note="hardest first" />
              <EvidenceMetric label="Mean opponent rating" value={num(schedule.mean_opponent_rating, 1)} />
            </>
          ) : (
            <ContextUnavailable>{data.schedule_difficulty.reason ?? "Run-in difficulty is not certified."}</ContextUnavailable>
          )}
        </div>
      </div>
    </>
  );
}

function RatingsEvidence({ data, team }: { data: RatingsTable; team: string }) {
  const rating = data.teams.find((item) => item.team === team);
  if (!rating) return <ContextUnavailable>No exact competition rating for this team.</ContextUnavailable>;
  return (
    <div className="team-dossier__context-group">
      <h3>Golavo Ratings</h3>
      <div className="team-dossier__metrics">
        <EvidenceMetric label="Competition rank" value={ordinal(rating.rank)} />
        <EvidenceMetric label="Rating" value={num(rating.rating, 0)} />
        <EvidenceMetric label="Rated matches" value={String(rating.matches)} />
      </div>
      <p className="small dim">Derived locally from completed matches scoped to {data.scope}; results through {data.data_through_utc ? utcDate(data.data_through_utc) : utcDate(data.as_of_utc)}. Index fingerprint: <code>{data.provenance?.index_sha256 ?? "unavailable"}</code>.</p>
    </div>
  );
}

function analyticsMatchesOutlook(data: CompetitionAnalytics, outlook: SeasonOutlook): boolean {
  return data.competition_id === outlook.competition_id
    && data.as_of_utc === outlook.as_of_utc
    && data.current_season.season === outlook.season
    && data.provenance.index_sha256 === outlook.provenance.index_sha256;
}

function ratingsMatchOutlook(data: RatingsTable, outlook: SeasonOutlook): boolean {
  return data.scope === outlook.competition_id
    && data.as_of_utc === outlook.as_of_utc
    && data.provenance?.index_sha256 === outlook.provenance.index_sha256;
}

interface TeamDossierProps {
  competitionId: string;
  team: string;
}

export function TeamDossier({ competitionId, team }: TeamDossierProps) {
  const dataGenerationRevision = useDataGenerationRevision();
  const [retryRevision, setRetryRevision] = useState(0);
  const generationKey = JSON.stringify([
    competitionId,
    team,
    dataGenerationRevision,
    retryRevision,
  ]);
  return (
    <TeamDossierGeneration
      key={generationKey}
      competitionId={competitionId}
      team={team}
      onRetry={() => {
        clearApiCache();
        setRetryRevision((value) => value + 1);
      }}
    />
  );
}

function TeamDossierGeneration({
  competitionId,
  team,
  onRetry,
}: TeamDossierProps & { onRetry: () => void }) {
  const league = LEAGUES.find((item) => item.competitionId === competitionId && item.seasonOutlook);
  const outlookState = useAsync(
    () => league ? fetchSeasonOutlook(competitionId) : Promise.reject(new Error("unknown competition")),
    [competitionId],
  );
  const canonicalOutlook = outlookState.status === "ready" && outlookState.data.status === "available"
    ? outlookState.data
    : null;
  const analyticsState = useAsync<CompetitionAnalytics | null>(
    () => league && canonicalOutlook
      ? fetchCompetitionAnalytics(competitionId, canonicalOutlook.as_of_utc)
      : Promise.resolve(null),
    [
      competitionId,
      canonicalOutlook?.as_of_utc,
      canonicalOutlook?.season,
      canonicalOutlook?.provenance.index_sha256,
    ],
  );
  const ratingsState = useAsync<RatingsTable | null>(
    () => league && canonicalOutlook
      ? fetchClubRatings(competitionId, {
          asOfUtc: canonicalOutlook.as_of_utc,
          indexSha256: canonicalOutlook.provenance.index_sha256,
        })
      : Promise.resolve(null),
    [
      competitionId,
      canonicalOutlook?.as_of_utc,
      canonicalOutlook?.season,
      canonicalOutlook?.provenance.index_sha256,
    ],
  );
  if (!league) {
    return (
      <EmptyState title="Competition not found" variant="notfound">
        Team dossiers require a certified domestic competition. <a href="#/leagues">Browse leagues ›</a>
      </EmptyState>
    );
  }
  if (outlookState.status === "loading") return <BlockSkeleton lines={7} />;
  if (outlookState.status === "error") {
    return (
      <ErrorState
        title="Team dossier unavailable"
        error={outlookState.error}
        onRetry={onRetry}
      />
    );
  }

  const outlook = outlookState.data;
  if (outlook.competition_id !== competitionId) {
    return (
      <EmptyState title="Season evidence identity mismatch">
        Golavo withheld this dossier because the response did not match the requested competition.
      </EmptyState>
    );
  }
  if (outlook.scenario !== null) {
    return (
      <EmptyState title="Canonical season outlook required">
        Golavo withheld this dossier because the response contained a hypothetical scenario.
      </EmptyState>
    );
  }
  if (outlook.status === "blocked") {
    return (
      <EmptyState title="Season evidence is not certified">
        {outlook.reason ?? "Golavo cannot certify this local season outlook yet."} <a href={`#/league/${league.slug}`}>Open {league.name} ›</a>
      </EmptyState>
    );
  }

  const standing = outlook.current_table.find((item) => item.team === team);
  if (!standing) {
    return (
      <EmptyState title="Exact team identity not present">
        Golavo will not guess through a rename, promotion, or relegation. <a href={`#/league/${league.slug}`}>Open the current {league.name} table ›</a>
      </EmptyState>
    );
  }

  const analytics = analyticsState.status === "ready"
    && analyticsState.data
    && analyticsMatchesOutlook(analyticsState.data, outlook)
    ? analyticsState.data
    : null;
  const ratings = ratingsState.status === "ready"
    && ratingsState.data
    && ratingsMatchOutlook(ratingsState.data, outlook)
    ? ratingsState.data
    : null;
  const pulse = analytics?.current_season.teams.find((item) => item.team === team);
  const modelVoices = outlook.voices.filter((voice) => voice.role === "voice");
  const voices = modelVoices.flatMap((voice) => {
      const projection = voice.teams.find((item) => item.team === team);
      return projection ? [{ voice, projection }] : [];
    });
  const completeVoiceSet = modelVoices.length > 0 && voices.length === modelVoices.length;
  const fixtures = outlook.remaining_fixtures
    .filter((item) => item.home_team === team || item.away_team === team)
    .slice(0, RUN_IN_LENGTH);

  return (
    <article className="team-dossier stack" style={{ ["--gap" as string]: "1.35rem" }}>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <a href="#/leagues">Leagues &amp; Europe</a>
        <span aria-hidden>›</span>
        <a href={`#/league/${league.slug}`}>{league.name}</a>
        <span aria-hidden>›</span>
        <span aria-current="page">Team dossier</span>
      </nav>

      <header className="team-dossier__hero">
        <div>
          <span className="upper">{outlook.season.replace("-", "–")} · exact identity</span>
          <h1>{team}</h1>
          <p className="team-dossier__standing">{ordinal(standing.position)} · {standing.points} points</p>
        </div>
        <div className="team-dossier__hero-record" aria-label="Observed current record">
          <span><strong>{standing.played}</strong> played</span>
          <span><strong>{standing.won}</strong> won</span>
          <span><strong>{standing.drawn}</strong> drawn</span>
          <span><strong>{standing.lost}</strong> lost</span>
          <span className="team-dossier__form"><small>Recent form</small><strong>{pulse?.recent_form.join(",") || "—"}</strong></span>
        </div>
      </header>

      <div className="team-dossier__spine">
        <section className="team-dossier__layer team-dossier__layer--record" aria-labelledby="dossier-record">
          <div className="team-dossier__layer-index" aria-hidden>01</div>
          <div className="team-dossier__layer-body">
            <span className="upper">Observed record</span>
            <h2 id="dossier-record">What has happened</h2>
            <p className="measure dim">Completed-match facts lead. These numbers describe the current table and never borrow authority from a projection.</p>
            <div className="team-dossier__metrics team-dossier__metrics--wide">
              <EvidenceMetric label="Goals" value={`${standing.goals_for} for`} />
              <EvidenceMetric label="Against" value={String(standing.goals_against)} />
              <EvidenceMetric label="Difference" value={standing.goal_difference > 0 ? `+${standing.goal_difference}` : String(standing.goal_difference)} />
              {pulse && <EvidenceMetric label="Current form" value={pulse.recent_form.join(",")} note={`${pulse.won}W · ${pulse.drawn}D · ${pulse.lost}L`} />}
            </div>
            <p className="small dim">Table as of {utc(outlook.as_of_utc)}{analytics?.current_season.data_through_utc ? `; current-season sample through ${utcDate(analytics.current_season.data_through_utc)}` : ""}.</p>
          </div>
        </section>

        <section className="team-dossier__layer team-dossier__layer--models" aria-labelledby="dossier-models">
          <div className="team-dossier__layer-index" aria-hidden>02</div>
          <div className="team-dossier__layer-body">
            <span className="upper">Model projections</span>
            <h2 id="dossier-models">What each voice simulates</h2>
            <p className="measure dim">The voices stay separate. Golavo does not average them into a consensus or turn this descriptive season simulation into a sealed forecast.</p>
            {completeVoiceSet ? (
              <div className="team-dossier__voices">
                {voices.map(({ voice, projection }) => (
                  <article className="team-dossier__voice" key={voice.voice_id}>
                    <header><span className="upper">{voice.voice_id.replaceAll("_", " ")}</span><h3>{voice.label}</h3></header>
                    <div className="team-dossier__metrics">
                      <EvidenceMetric label="Projected points" value={typeof projection.expected_points === "number" ? num(projection.expected_points, 1) : "—"} />
                      <EvidenceMetric label="Title" value={pctWhole(projection.title)} />
                      <EvidenceMetric label="Top four" value={pctWhole(projection.top_four)} />
                      <EvidenceMetric label="Relegation" value={pctWhole(projection.relegation)} />
                    </div>
                    {projectionCoverageCaveat(projection) && <p className="small dim">{projectionCoverageCaveat(projection)}</p>}
                  </article>
                ))}
              </div>
            ) : (
              <ContextUnavailable>Model projections are withheld because at least one available model voice does not contain this exact team identity.</ContextUnavailable>
            )}
            <p className="small dim">Seed {outlook.seed ?? "unavailable"} · {outlook.iterations.toLocaleString("en-GB")} runs · rule {outlook.simulation_rule} · never persisted or scored as a seal.</p>
          </div>
        </section>

        <section className="team-dossier__layer team-dossier__layer--evidence" aria-labelledby="dossier-evidence">
          <div className="team-dossier__layer-index" aria-hidden>03</div>
          <div className="team-dossier__layer-body">
            <span className="upper">Evidence context</span>
            <h2 id="dossier-evidence">What supports the reading</h2>
            <p className="measure dim">Every figure remains competition-scoped and source-backed. Missing optional context stays missing instead of erasing the observed record.</p>
            {ratings ? (
              <RatingsEvidence data={ratings} team={team} />
            ) : ratingsState.status === "ready" && ratingsState.data ? (
              <ContextUnavailable>Golavo Ratings were withheld because their competition scope, cutoff, or index fingerprint did not match the certified season outlook.</ContextUnavailable>
            ) : ratingsState.status === "error" ? (
              <ContextUnavailable>Golavo Ratings are unavailable: {ratingsState.error.message}</ContextUnavailable>
            ) : (
              <p className="small dim">Loading competition ratings…</p>
            )}
            {analytics ? (
              <AnalyticsEvidence data={analytics} team={team} />
            ) : analyticsState.status === "ready" && analyticsState.data ? (
              <ContextUnavailable>Competition analytics were withheld because their competition, season, cutoff, or index fingerprint did not match the certified season outlook.</ContextUnavailable>
            ) : analyticsState.status === "error" ? (
              <ContextUnavailable>Competition analytics are unavailable: {analyticsState.error.message}</ContextUnavailable>
            ) : (
              <p className="small dim">Loading competition context…</p>
            )}
          </div>
        </section>
      </div>

      <section className="team-dossier__run-in stack" aria-labelledby="dossier-run-in">
        <div className="hgroup">
          <div><span className="upper">Next five</span><h2 id="dossier-run-in">The run-in</h2></div>
          <a className="small" href={`#/league/${league.slug}`}>Full competition desk ›</a>
        </div>
        {fixtures.length > 0 ? (
          <ol className="team-dossier__fixtures">
            {fixtures.map((fixture) => {
              const importance = clubImportance(fixture, team);
              const stake = importance ? topStake(importance) : null;
              const importanceVoice = fixture.importance
                ? outlook.voices.find((voice) => voice.voice_id === fixture.importance?.voice_id)
                : null;
              const importanceLabel = importance?.score != null && stake
                ? `${Math.round(importance.score * 100)}pp ${stake.replace("_", " ")} swing · ${importanceVoice?.label ?? fixture.importance?.voice_id.replaceAll("_", " ")}`
                : "Season stakes held back";
              const side = fixture.home_team === team ? "Home" : "Away";
              const opponent = fixture.home_team === team ? fixture.away_team : fixture.home_team;
              return (
                <li key={fixture.match_id}>
                  <a className="team-dossier__fixture" href={`#/match/${encodeURIComponent(fixture.match_id)}`}>
                    <span className="upper">{side} · {utc(fixture.kickoff_utc)}</span>
                    <strong>{opponent}</strong>
                    <small>{importanceLabel}</small>
                  </a>
                  <span className="team-dossier__fixture-pick">Pick in Match Cockpit</span>
                  <FollowButton matchId={fixture.match_id} compact />
                </li>
              );
            })}
          </ol>
        ) : (
          <p className="dim">No remaining fixtures in the active outlook.</p>
        )}
      </section>

      <footer className="team-dossier__provenance">
        <span className="upper">Local evidence colophon</span>
        <p>Table and projection sources: {outlook.provenance.source_ids.join(", ") || "unavailable"}. Index fingerprint: <code>{outlook.provenance.index_sha256}</code>. As of {utc(outlook.as_of_utc)}.</p>
        <p>Observed facts, model outputs, and optional evidence context remain separate; each optional envelope carries its own attribution above. This dossier does not author, blend, seal, settle, or recommend a forecast.</p>
      </footer>
    </article>
  );
}
