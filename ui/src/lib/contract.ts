/**
 * Golavo frozen contract v0.2.0 — TypeScript mirror.
 *
 * These types mirror the canonical schema owned by the Codex lane EXACTLY.
 * The UI consumes artifacts as-is. If a view needs something the contract
 * cannot express, that gap is documented in ui/HANDOFF.md — never invented
 * here. A 64-hex sha256 and a 40-hex git sha are plain strings at the type
 * level; validated at runtime by lib/api.ts guards.
 *
 * v0.2.0 is additive over v0.1.0 (optional snapshot upstream_committed_at_utc,
 * optional void_reason, CalibrationSummary), so the UI accepts both.
 */

export const SCHEMA_VERSION = "0.2.0" as const;
// 0.3.0 is additive: the on-demand MatchAnalysis read model (Match Cockpit) and
// the Games-home recent rails. The sealed ForecastArtifact contract is unchanged
// at 0.2.0, so the artifact/eval/calibration guards keep their existing set.
export const ACCEPTED_SCHEMA_VERSIONS = ["0.1.0", "0.2.0"] as const;
export const ANALYSIS_SCHEMA_VERSION = "0.3.0" as const;
export type SchemaVersion = (typeof ACCEPTED_SCHEMA_VERSIONS)[number];

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

/**
 * Exact-score distribution the sealed 1X2 forecast already implies (Phase 8,
 * additive). Present only for goal-based families (independent / Dixon-Coles /
 * bivariate Poisson); absent for climatological/elo and abstained seals. grid[i][j]
 * is P(home=i, away=j) for 0..max_goals per side; everything beyond folds into the
 * outcome-decomposed tail. grid + tail is an exact partition, so its win/draw/loss
 * marginals reproduce forecast.probs (the engine enforces this on every load).
 */
export interface ScoreMatrix {
  max_goals: number;
  resolution: number;
  grid: number[][];
  tail: {
    probability: number;
    home: number;
    draw: number;
    away: number;
  };
  most_likely: {
    home: number;
    away: number;
    probability: number;
  };
  total_probability: number;
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
  /** Optional exact-score distribution (Phase 8). Absent → no goal model / abstained. */
  score_matrix?: ScoreMatrix | null;
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
  /** When the pinned upstream ref was committed — the data-state anchor that
   *  seal validity is checked against (v0.2.0; absent on older packs). */
  upstream_committed_at_utc?: string | null;
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
  schema_version: SchemaVersion;
  artifact_id: string; // "fa_..."
  status: ArtifactStatus;
  supersedes: string | null;
  /** Recorded when a seal is voided (postponement/abandonment) — v0.2.0. */
  void_reason?: string | null;
  match: MatchInfo;
  forecast: ForecastBlock;
  model: ModelBlock;
  inputs: InputsBlock;
  provenance: ProvenanceBlock;
  evaluation: EvaluationBlock | null;
}

// ---- Evaluation summary -----------------------------------------------------
// Mirrors the canonical EvalSummary owned by the backend. Reliability bins are
// confidence-vs-accuracy (the basis of ECE): each bin holds the model's mean
// top-probability and the observed accuracy of that top pick, with a Wilson
// interval. Empty bins carry nulls.

export interface ReliabilityBin {
  lower: number;
  upper: number;
  count: number;
  mean_confidence: number | null;
  accuracy: number | null;
  wilson_low: number | null;
  wilson_high: number | null;
}

export interface FoldModel {
  family: ModelFamily;
  params?: Record<string, unknown>;
  log_loss: number;
  brier: number;
  ece?: number;
  rps?: number;
  reliability_bins?: ReliabilityBin[];
}

export interface Fold {
  fold_id: string;
  competition?: string;
  window_start?: string;
  window_end?: string;
  training_cutoff_utc?: string;
  n_matches: number;
  models: FoldModel[];
}

export interface EvalSummary {
  schema_version: SchemaVersion;
  primary_metric?: string;
  sources?: (Snapshot | null)[];
  folds: Fold[];
}

// ---- Calibration record (v0.2.0) --------------------------------------------
// The REAL prediction ledger: sealed→scored/voided chains aggregated from
// immutable artifacts. Entirely distinct from the backtest eval folds above.

export type ResolutionStatus = "pending" | "scored" | "voided";

export interface ChainResolution {
  status: ResolutionStatus;
  artifact_id: string | null;
  resolved_at_utc: string | null;
  actual: EvaluationBlock["actual"] | null;
  metrics: EvaluationBlock["metrics"] | null;
  void_reason: string | null;
}

export interface CalibrationChain {
  sealed_artifact_id: string;
  match: MatchInfo;
  sealed_at_utc: string;
  horizon: Horizon;
  family: ModelFamily;
  abstained: boolean;
  probs: Probs | null;
  resolution: ChainResolution;
}

export interface CalibrationSummary {
  schema_version: SchemaVersion;
  generated_from: string;
  primary_metric: "log_loss";
  counts: {
    sealed: number;
    abstained: number;
    scored: number;
    voided: number;
    pending: number;
  };
  running: {
    n_scored: number;
    log_loss: number;
    brier: number;
    prob_assigned_to_outcome: number;
  } | null;
  reliability_bins: ReliabilityBin[];
  chains: CalibrationChain[];
}

// ---- Commentator's Notebook (Phase 7) ---------------------------------------
// Deterministic, source-backed facts computed by a fixed template family. Every
// fact is labelled and sample-guarded; coincidences are capped and quarantined.
// A notebook NEVER carries or changes a forecast probability. Mirrors
// docs/contracts/facts.schema.json.

export type FactLabel = "predictive" | "context" | "coincidence";
export type FactScope = "team" | "head_to_head" | "match" | "competition";
export type FactNumberUnit = "percent" | "goals" | "count";

export interface FactNumber {
  key: string;
  value: number;
  unit: FactNumberUnit;
  display: string;
}

export interface FactFreshness {
  as_of_utc: string;
  last_event_utc: string;
  age_days: number;
  stale: boolean;
  staleness_days: number | null;
}

export interface NotebookFact {
  id: string;
  version: string;
  label: FactLabel;
  scope: FactScope;
  subject: string;
  text: string;
  values: Record<string, unknown>;
  numbers: FactNumber[];
  sample_n: number;
  denominator: number;
  base_rate: number | null;
  date_range: [string, string];
  source_ids: string[];
  freshness: FactFreshness;
  min_sample: number;
  specificity: number;
}

export interface NotebookSuppression {
  id: string;
  subject?: string;
  reason: "min_sample" | "stale" | "no_source" | "coincidence_cap" | "empty";
  detail?: string;
}

export interface CommentatorsNotebook {
  schema_version: string;
  notebook_id: string;
  registry_version: string;
  as_of_utc: string;
  match: {
    home_team: string;
    away_team: string;
    competition: string;
    neutral_venue: boolean;
    kickoff_utc?: string | null;
  };
  source_ids: string[];
  family_size: number;
  coincidence_cap: number;
  facts: NotebookFact[];
  suppressed: NotebookSuppression[];
  generator: string;
}

/** The read-only /facts endpoint envelope (or its mock). */
export interface NotebookResponse {
  artifact_id: string;
  available: boolean;
  notebook: CommentatorsNotebook | null;
}

// ---- Match directory (Workstream D) -----------------------------------------
// The read-only match-search / match-detail / competitions endpoints, plus the
// per-match notebook wrapper. A MatchRow is a DISPLAY projection of engine-
// produced matches: the numbers (scores, forecast links) are copied verbatim,
// never minted here. The server workstream implements the identical shapes; the
// mock branch of lib/api.ts filters bundled rows client-side. Every mock row
// carries a synthetic source_id so it can never be mistaken for real data.

export type SourceKind = "international" | "club";

/** A sealed forecast that exists for a match — enough to render the "seal
 *  exists" state and deep-link to #/forecast/{artifact_id}. */
export interface MatchForecastLink {
  artifact_id: string;
  status: ArtifactStatus;
  horizon: Horizon;
  sealed_at_utc: string;
}

export interface MatchRow {
  match_id: string;
  kickoff_utc: string; // ISO 8601
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  competition: string;
  country: string | null;
  city: string | null;
  neutral: boolean;
  /** Invariant: is_complete === (home_score !== null && away_score !== null). */
  is_complete: boolean;
  source_kind: SourceKind;
  source_id: string;
  forecasts: MatchForecastLink[];
}

export interface MatchSearchResponse {
  schema_version: SchemaVersion;
  query: string;
  total: number;
  limit: number;
  offset: number;
  matches: MatchRow[];
}

/** Whether a fixture can be forward-sealed in-app, with a typed reason. Additive
 *  (optional) so an older backend that omits it degrades gracefully. */
export interface SealEligibility {
  eligible: boolean;
  /** Stable machine code; the UI maps known values to copy and falls back to
   *  `detail` for anything it doesn't recognise. */
  reason_code: string;
  detail: string;
  family: string;
  existing_artifact_ids: string[];
}

/** The result of POST /matches/{id}/seal — a created or already-existing seal. */
export interface SealResult {
  created: boolean;
  artifact_id: string;
  status: ArtifactStatus;
  family: string;
  abstained: boolean;
  abstain_reason: string | null;
}

export interface MatchDetailResponse {
  schema_version: SchemaVersion;
  match: MatchRow;
  linked_by: "match_id" | "fixture" | null;
  seal_eligibility?: SealEligibility;
}

/** An upcoming fixture present upstream but not yet in this build's index. */
export interface NewFixture {
  date: string;
  home_team: string;
  away_team: string;
  competition: string;
}

export interface FixturesCheckResponse {
  schema_version: SchemaVersion;
  source_ref: string;
  checked_at_utc: string;
  new_fixtures: NewFixture[];
}

export interface CompetitionSummary {
  competition: string;
  source_kind: SourceKind;
  n_matches: number;
}

export interface CompetitionsResponse {
  schema_version: SchemaVersion;
  competitions: CompetitionSummary[];
}

/** Thin wrapper for the per-match notebook endpoint. Reuses the existing
 *  CommentatorsNotebook (the same type fetchNotebook returns), so the notebook
 *  UI is shared. A precomputed notebook is served as-is; otherwise the engine
 *  may compute one on demand. Never carries or changes a probability. */
export interface MatchNotebookResponse {
  available: boolean;
  computed: "precomputed" | "on_demand" | null;
  as_of_horizon: string | null;
  notebook: CommentatorsNotebook | null;
}

// ---- Match Cockpit: on-demand MatchAnalysis (contract 0.3.0, additive) -------
// The read model behind the Match Cockpit. Computed on demand for ANY indexed
// match at the seal's own kickoff−1s cutoff — leak-safe by construction — and
// NEVER sealed. `analysis_kind` distinguishes a Replay (completed fixture,
// reconstructed with pre-kickoff data) from a Preview (scheduled fixture). The
// council is two voices (Elo ratings, the Dixon–Coles goal model) plus a
// climatology baseline; the Poisson variants are disclosed, never averaged.

export type AnalysisKind = "replay" | "preview";
export type CouncilRole = "voice" | "variant" | "baseline";
export type CouncilMethod = "ratings" | "goals" | "base_rate" | "unknown";

export interface CouncilModel {
  family: ModelFamily;
  role: CouncilRole;
  method: CouncilMethod;
  abstained: boolean;
  probs: Probs | null;
  expected_goals: ExpectedGoals | null;
  score_matrix: ScoreMatrix | null;
  params: Record<string, unknown> | null;
}

export interface CouncilSummary {
  voices: number;
  voices_agree: boolean | null;
  leading_outcome: Outcome | null;
  max_delta_p: number | null;
  outcome_range: Record<Outcome, { low: number; high: number }> | null;
}

export interface MatchAnalysis {
  schema_version: string;
  analysis_kind: AnalysisKind;
  match: {
    match_id: string;
    competition: string;
    kickoff_utc: string;
    home_team: string;
    away_team: string;
    neutral_venue: boolean;
    is_complete: boolean;
  };
  information_cutoff_utc: string;
  abstained: boolean;
  abstain_reason: string | null;
  uncertainty: Uncertainty;
  team_history: Record<string, number>;
  min_team_matches: number;
  council: CouncilSummary;
  models: CouncilModel[];
  score_matrix: ScoreMatrix | null;
  score_matrix_family: ModelFamily | null;
}

/** The /matches/{id}/analysis envelope. Fails closed to available:false when a
 *  fixture cannot be modelled (e.g. no kickoff), never a fabricated analysis. */
export interface MatchAnalysisResponse {
  available: boolean;
  reason: string | null;
  analysis: MatchAnalysis | null;
}

/** A directory row pair for the Games home rails. */
export interface RecentMatchesResponse {
  schema_version: SchemaVersion;
  upcoming: MatchRow[];
  recent: MatchRow[];
}

export const ANALYSIS_KIND_LABELS: Record<AnalysisKind, string> = {
  replay: "Replay",
  preview: "Preview",
};

export const FACT_LABEL_TEXT: Record<FactLabel, string> = {
  predictive: "Predictive",
  context: "Context",
  coincidence: "Coincidence",
};

export const FACT_SCOPE_TEXT: Record<FactScope, string> = {
  team: "Team",
  head_to_head: "Head-to-head",
  match: "Match",
  competition: "Competition",
};

// ---- Display metadata (UI-side only — not part of the wire contract) --------

export const FAMILY_LABELS: Record<ModelFamily, string> = {
  climatological: "Climatological",
  elo_ordlogit: "Elo ratings",
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
