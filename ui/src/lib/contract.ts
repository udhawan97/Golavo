/**
 * Golavo frozen contract v0.1.0 — TypeScript mirror.
 *
 * These types mirror the canonical schema owned by the Codex lane EXACTLY.
 * The UI consumes artifacts as-is. If a view needs something the contract
 * cannot express, that gap is documented in ui/HANDOFF.md — never invented
 * here. A 64-hex sha256 and a 40-hex git sha are plain strings at the type
 * level; validated at runtime by lib/api.ts guards.
 */

export const SCHEMA_VERSION = "0.1.0" as const;

export type ArtifactStatus = "sealed" | "scored" | "abstained" | "voided";
export type Horizon = "T-72h" | "T-24h" | "T-60m";
export type Uncertainty = "low" | "medium" | "high";
export type Outcome = "home" | "draw" | "away";
export type Market = "1x2_regulation";

export type ModelFamily =
  | "climatological"
  | "elo_ordlogit"
  | "poisson_independent"
  | "dixon_coles"
  | "bivariate_poisson";

export interface MatchInfo {
  match_id: string;
  competition: string;
  stage?: string;
  kickoff_utc: string; // ISO 8601
  home_team: string;
  away_team: string;
  neutral_venue: boolean;
  city?: string;
  country?: string;
}

export interface Probs {
  home: number; // [0, 1]
  draw: number;
  away: number;
}

export interface ExpectedGoals {
  home: number;
  away: number;
}

export interface ForecastBlock {
  market: Market;
  sealed_at_utc: string;
  horizon: Horizon;
  probs: Probs | null;
  expected_goals: ExpectedGoals | null;
  abstained: boolean;
  abstain_reason: string | null;
  uncertainty: Uncertainty;
}

export interface ModelBlock {
  model_id: string;
  family: ModelFamily;
  version: string;
  params_hash: string;
  code_git_sha: string;
  seed: number;
}

export interface Snapshot {
  snapshot_id: string;
  source_id: string;
  url: string;
  upstream_ref: string;
  retrieved_at_utc: string;
  sha256: string; // 64 hex
  license: string;
}

export interface InputsBlock {
  training_cutoff_utc: string;
  snapshots: Snapshot[];
}

export interface ProvenanceBlock {
  created_at_utc: string;
  generator: string;
  deterministic: true;
  payload_sha256: string; // 64 hex
}

export interface EvaluationBlock {
  actual: {
    home_goals: number;
    away_goals: number;
    outcome: Outcome;
  };
  scored_at_utc: string;
  metrics: {
    log_loss: number;
    brier: number;
    prob_assigned_to_outcome: number;
  };
}

export interface ForecastArtifact {
  schema_version: typeof SCHEMA_VERSION;
  artifact_id: string; // "fa_..."
  status: ArtifactStatus;
  supersedes: string | null;
  match: MatchInfo;
  forecast: ForecastBlock;
  model: ModelBlock;
  inputs: InputsBlock;
  provenance: ProvenanceBlock;
  evaluation: EvaluationBlock | null;
}

// ---- Evaluation summary -----------------------------------------------------

export interface ReliabilityBin {
  p_mid: number;
  n: number;
  observed_rate: number;
}

export interface FoldModel {
  model_id: string;
  log_loss: number;
  brier: number;
  ece?: number;
  rps?: number;
  reliability_bins?: ReliabilityBin[];
}

export interface Fold {
  fold_id: string;
  n_matches: number;
  models: FoldModel[];
}

export interface EvalSummary {
  schema_version: typeof SCHEMA_VERSION;
  folds: Fold[];
}

// ---- Display metadata (UI-side only — not part of the wire contract) --------

export const FAMILY_LABELS: Record<ModelFamily, string> = {
  climatological: "Climatological",
  elo_ordlogit: "Elo · ordered logit",
  poisson_independent: "Poisson (independent)",
  dixon_coles: "Dixon–Coles",
  bivariate_poisson: "Bivariate Poisson",
};

export const STATUS_LABELS: Record<ArtifactStatus, string> = {
  sealed: "Sealed",
  scored: "Scored",
  abstained: "Abstained",
  voided: "Voided",
};

export const HORIZON_LABELS: Record<Horizon, string> = {
  "T-72h": "T−72h",
  "T-24h": "T−24h",
  "T-60m": "T−60m",
};
