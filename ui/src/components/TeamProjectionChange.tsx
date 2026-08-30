import { useEffect, useRef, useState } from "react";
import type { SeasonOutlook, SeasonOutlookTeam, SeasonOutlookVoice } from "../lib/contract";

const SNAPSHOT_VERSION = "0.1.0" as const;

export interface TeamProjectionSnapshot {
  schemaVersion: typeof SNAPSHOT_VERSION;
  competitionId: string;
  season: string;
  team: string;
  voiceId: SeasonOutlookVoice["voice_id"];
  simulationRule: SeasonOutlook["simulation_rule"];
  seed: number;
  iterations: number;
  asOfUtc: string;
  indexSha256: string;
  expectedPoints: number | null;
  title: number;
  topFour: number;
  relegation: number;
}

export interface TeamProjectionDelta {
  previousIndexSha256: string;
  currentIndexSha256: string;
  expectedPoints: number | null;
  title: number;
  topFour: number;
  relegation: number;
}

const VOICE_IDS = new Set<SeasonOutlookVoice["voice_id"]>([
  "elo_ordlogit",
  "dixon_coles",
  "equal-chance-baseline",
]);

function finiteProbability(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
}

export function isTeamProjectionSnapshot(value: unknown): value is TeamProjectionSnapshot {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const row = value as Record<string, unknown>;
  const strings = ["competitionId", "season", "team", "simulationRule"] as const;
  return row.schemaVersion === SNAPSHOT_VERSION
    && strings.every((key) => typeof row[key] === "string" && row[key].length > 0)
    && typeof row.voiceId === "string"
    && VOICE_IDS.has(row.voiceId as SeasonOutlookVoice["voice_id"])
    && typeof row.seed === "number"
    && Number.isInteger(row.seed)
    && row.seed >= 0
    && typeof row.iterations === "number"
    && Number.isInteger(row.iterations)
    && row.iterations > 0
    && typeof row.asOfUtc === "string"
    && Number.isFinite(Date.parse(row.asOfUtc))
    && typeof row.indexSha256 === "string"
    && /^[0-9a-f]{64}$/u.test(row.indexSha256)
    && (row.expectedPoints === null
      || (typeof row.expectedPoints === "number" && Number.isFinite(row.expectedPoints)))
    && finiteProbability(row.title)
    && finiteProbability(row.topFour)
    && finiteProbability(row.relegation);
}

export function teamProjectionSnapshot(
  outlook: SeasonOutlook,
  voice: SeasonOutlookVoice,
  projection: SeasonOutlookTeam,
): TeamProjectionSnapshot | null {
  if (outlook.status !== "available" || outlook.scenario !== null || outlook.seed === null)
    return null;
  const snapshot: TeamProjectionSnapshot = {
    schemaVersion: SNAPSHOT_VERSION,
    competitionId: outlook.competition_id,
    season: outlook.season,
    team: projection.team,
    voiceId: voice.voice_id,
    simulationRule: outlook.simulation_rule,
    seed: outlook.seed,
    iterations: outlook.iterations,
    asOfUtc: outlook.as_of_utc,
    indexSha256: outlook.provenance.index_sha256,
    expectedPoints: typeof projection.expected_points === "number" ? projection.expected_points : null,
    title: projection.title,
    topFour: projection.top_four,
    relegation: projection.relegation,
  };
  return isTeamProjectionSnapshot(snapshot) ? snapshot : null;
}

function sameIdentity(previous: TeamProjectionSnapshot, current: TeamProjectionSnapshot): boolean {
  return previous.schemaVersion === SNAPSHOT_VERSION
    && previous.competitionId === current.competitionId
    && previous.season === current.season
    && previous.team === current.team
    && previous.voiceId === current.voiceId
    && previous.simulationRule === current.simulationRule
    && previous.seed === current.seed
    && previous.iterations === current.iterations;
}

export function compareTeamProjectionSnapshots(
  previous: TeamProjectionSnapshot,
  current: TeamProjectionSnapshot,
): TeamProjectionDelta | null {
  if (!sameIdentity(previous, current) || previous.indexSha256 === current.indexSha256) return null;
  return {
    previousIndexSha256: previous.indexSha256,
    currentIndexSha256: current.indexSha256,
    expectedPoints: previous.expectedPoints === null || current.expectedPoints === null
      ? null
      : current.expectedPoints - previous.expectedPoints,
    title: current.title - previous.title,
    topFour: current.topFour - previous.topFour,
    relegation: current.relegation - previous.relegation,
  };
}

function signed(value: number, digits = 1): string {
  const rounded = value.toFixed(digits);
  return value > 0 ? `+${rounded}` : rounded;
}

export function TeamProjectionChange({
  outlook,
  voice,
  projection,
}: {
  outlook: SeasonOutlook;
  voice: SeasonOutlookVoice;
  projection: SeasonOutlookTeam;
}) {
  const [delta, setDelta] = useState<TeamProjectionDelta | null>(null);
  const consumedSignature = useRef<string | null>(null);
  useEffect(() => {
    const current = teamProjectionSnapshot(outlook, voice, projection);
    if (!current) {
      consumedSignature.current = null;
      setDelta(null);
      return;
    }
    const key = `golavo:team-projection:${encodeURIComponent(current.competitionId)}:${encodeURIComponent(current.team)}`;
    const signature = `${key}:${current.indexSha256}`;
    if (consumedSignature.current === signature) return;
    consumedSignature.current = signature;
    setDelta(null);
    try {
      const raw = localStorage.getItem(key);
      let previous: TeamProjectionSnapshot | null = null;
      if (raw) {
        try {
          const parsed: unknown = JSON.parse(raw);
          previous = isTeamProjectionSnapshot(parsed) ? parsed : null;
        }
        catch { /* replace a malformed convenience snapshot below */ }
      }
      if (previous) setDelta(compareTeamProjectionSnapshots(previous, current));
      localStorage.setItem(key, JSON.stringify(current));
    } catch {
      // A private-storage failure removes this convenience note, never the outlook.
    }
  }, [outlook, projection, voice]);
  if (!delta) return null;
  return (
    <aside className="callout callout--info" aria-live="polite">
      <div>
        <div className="callout__title">Local projection change</div>
        <p className="small dim">Index {delta.previousIndexSha256.slice(0, 10)}… → {delta.currentIndexSha256.slice(0, 10)}…</p>
        <ul className="small">
          <li>Projected points: {delta.expectedPoints === null ? "unavailable" : signed(delta.expectedPoints)}</li>
          <li>Title: {signed(delta.title * 100)} percentage points</li>
          <li>Top four: {signed(delta.topFour * 100)} percentage points</li>
          <li>Relegation: {signed(delta.relegation * 100)} percentage points</li>
        </ul>
        <p className="small dim">Like-for-like local comparison for {voice.label}. It cannot explain why the source index changed, prove improvement, or act as a seal.</p>
      </div>
    </aside>
  );
}
