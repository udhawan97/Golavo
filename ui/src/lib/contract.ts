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
export const ANALYSIS_SCHEMA_VERSION = "0.5.0" as const;
export const PICK_SCHEMA_VERSION = "0.1.0" as const;
export const FOLLOW_SCHEMA_VERSION = "0.1.0" as const;
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
  report_cards?: ReportCard[];
}

export interface ReportCardModel {
  family: ModelFamily;
  n_matches: number;
  n_folds: number;
  log_loss: number;
  brier: number;
  ece: number;
  rps: number;
  skill_score: number;
  skill_ci_95: [number, number] | null;
  sample_status: "available" | "insufficient_sample";
  mean_rank: number;
  best_rank: number;
  worst_rank: number;
  first_place_folds: number;
}

export interface ReportCard {
  competition: string;
  baseline_family: "climatological";
  primary_metric: "log_loss";
  minimum_matches: number;
  bootstrap: {
    method: "fold-stratified-match-bootstrap";
    replicates: number;
    seed: number;
  };
  window_start: string;
  window_end: string;
  models: ReportCardModel[];
}

// ---- Existing-data competition analytics ----------------------------------

export type AnalyticsStatus = "available" | "insufficient_sample" | "unavailable" | "blocked";

export interface StrengthPoint {
  cutoff_utc: string;
  sample_matches: number;
  attack_index: number;
  defence_index: number;
  overall_index: number;
}

export interface TeamStrengthTrend {
  team: string;
  current: StrengthPoint;
  trend: StrengthPoint[];
}

export interface TeamWorkload {
  team: string;
  last_indexed_match_utc: string;
  rest_days: number;
  matches_last_7_days: number;
  matches_last_14_days: number;
  matches_last_28_days: number;
  congestion: "normal" | "elevated" | "high";
}

export interface CompetitionAnalytics {
  schema_version: string;
  competition_id: string;
  competition_name: string;
  as_of_utc: string;
  scope: {
    team_category: "club" | "international";
    strength_comparison: "this_competition_only";
    model_input: false;
  };
  provenance: { source_ids: string[]; index_sha256?: string };
  strength_trends: {
    status: AnalyticsStatus;
    reason: string | null;
    method: string;
    minimum_matches: number;
    data_through_utc?: string;
    comparison_scope?: "this_competition_only";
    teams: TeamStrengthTrend[];
  };
  rest_congestion: {
    status: AnalyticsStatus;
    reason: string | null;
    method: string;
    coverage_note: string;
    teams: TeamWorkload[];
  };
  schedule_difficulty: {
    status: "blocked" | "unavailable";
    reason: string;
    required_capability: string;
  };
}

// ---- Historical team research ---------------------------------------------

export interface ResearchTeamRow {
  team_id: number;
  team: string;
  matches: number;
  passes_attempted: number;
  passes_completed: number;
  pass_completion_pct: number;
  progressive_passes_per_match: number;
  shots_per_match: number;
  goals_per_match: number;
  chain_proxy_events: number;
  chain_proxy_count: number;
  progressive_chains_per_match: number;
  research_xt_created_per_match: number;
}

export interface ResearchTeamAnalytics {
  schema_version: "0.1.0";
  status: "available";
  label: string;
  competition_id: string;
  competition_name: string;
  era: string;
  team_scope: "team_aggregate_only";
  coverage: { matches: number; events: number; teams: number };
  methods: { progressive_pass: string; chain_proxy: string; research_xt: string };
  teams: ResearchTeamRow[];
  provenance: {
    source_id: "pappalardo-wyscout-events";
    license: "CC-BY-4.0";
    attribution: string;
    modifications: string;
  };
}

// ---- Tournament outlook ----------------------------------------------------

export interface TournamentOutlookTeam {
  team: string;
  reach_final: number;
  reach_third_place_match: number;
  champion: number;
  third: number;
}

export interface TournamentOutlookVoice {
  voice_id: "elo_ordlogit" | "dixon_coles" | "equal-chance-baseline";
  label: string;
  role: "voice" | "baseline";
  draw_resolution: string;
  teams: TournamentOutlookTeam[];
  totals: {
    reach_final: number;
    reach_third_place_match: number;
    champion: number;
    third: number;
  };
}

export interface TournamentOutlook {
  schema_version: "0.1.0";
  status: "available" | "unavailable";
  label: string;
  tournament_id: "worldcup-2026";
  tournament_name: string;
  as_of_utc: string;
  reason?: string;
  data_through_utc?: string;
  outlook_rule?: "ko-2026.07.1";
  method?: "exact-four-team-bracket-enumeration";
  ledger_status?: "never_persisted_or_scored_as_a_seal";
  snapshot_status?: "current_for_index" | "result_refresh_needed";
  snapshot_note?: string;
  semifinals: Array<{
    match_id: string;
    kickoff_utc: string;
    home_team: string;
    away_team: string;
    status: "complete" | "unresolved";
  }>;
  voices: TournamentOutlookVoice[];
  provenance: {
    index_sha256: string;
    training_source_ids?: string[];
    fixture_source_id?: string;
  };
}

// ---- Domestic season outlook ----------------------------------------------

export interface SeasonStandingRow {
  position: number;
  team: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points_adjustment: number;
  points: number;
}

export interface SeasonOutlookTeam {
  team: string;
  title: number;
  top_four: number;
  relegation: number;
  display_percent: {
    title: number;
    top_four: number;
    relegation: number;
  };
}

export interface SeasonOutlookVoice {
  voice_id: "elo_ordlogit" | "dixon_coles" | "equal-chance-baseline";
  label: string;
  role: "voice" | "baseline";
  scoreline_method: string;
  teams: SeasonOutlookTeam[];
  totals: { title: number; top_four: number; relegation: number };
}

export interface SeasonOutlook {
  schema_version: "0.1.0";
  status: "blocked" | "complete" | "available";
  label: string;
  competition_id: string;
  competition_name: string;
  season: string;
  as_of_utc: string;
  simulation_rule: "season-mc-2026.07.1";
  ledger_status: "never_persisted_or_scored_as_a_seal";
  reason_code: string | null;
  reason: string | null;
  standings_rule_id: string;
  fixture_certificate: {
    expected_teams: number;
    observed_teams: number;
    teams: string[];
    expected_matches: number;
    observed_matches: number;
    unique_ordered_pairs: number;
    duplicate_ordered_pairs: number;
    self_fixtures: number;
    incomplete_fixtures: number;
    past_result_gaps: number;
    future_completed_results: number;
    complete_fixture_list: boolean;
  };
  current_table: SeasonStandingRow[];
  iterations: number;
  seed: number | null;
  voices: SeasonOutlookVoice[];
  provenance: {
    source_ids: string[];
    training_source_ids?: string[];
    training_data_through_utc?: string;
    index_sha256: string;
  };
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

export type SettlementPendingReason =
  | "result_not_published"
  | "source_conflict"
  | "scoring_refused";

export interface SettlementReport {
  schema_version: SchemaVersion;
  checked_at_utc: string;
  pending_before_check: number;
  eligible: number;
  deferred_in_progress: string[];
  sources_checked: string[];
  scored: Array<{
    sealed_artifact_id: string;
    scored_artifact_id: string;
    home_team: string;
    away_team: string;
    home_goals: number;
    away_goals: number;
    source_id: string;
  }>;
  still_pending: Array<{
    artifact_id: string;
    reason: SettlementPendingReason;
  }>;
  errors: Array<{
    source_id: string;
    message: string;
  }>;
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
  kickoff_precision?: "exact" | "day";
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
  provenance?: {
    identity?: string | null;
    result?: string | null;
    kickoff?: string | null;
    venue?: string | null;
    training?: string | null;
  };
  upstream_fixture_key?: string | null;
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

// ---- User picks (v0.1.0) ----------------------------------------------------

export type PickStatus = "draft" | "locked" | "scored" | "void";
export type RivalCapability = "score" | "outcome_only" | "abstained";

export interface ScorePick {
  home_goals: number;
  away_goals: number;
}

export interface RivalPick {
  family: ModelFamily;
  capability: RivalCapability;
  score_pick: ScorePick | null;
  outcome_pick: Outcome | null;
}

export type RivalModel = RivalPick;

export interface UserPick {
  schema_version: typeof PICK_SCHEMA_VERSION;
  pick_id: string | null;
  status: "draft" | "locked";
  match: {
    match_id: string;
    kickoff_utc: string;
    kickoff_time_known: boolean;
    home_team: string;
    away_team: string;
    home_norm: string;
    away_norm: string;
    competition: string | null;
  };
  user_pick: ScorePick & { outcome: Outcome };
  rivals: RivalPick[];
  analysis_fingerprint: {
    index_fingerprint: string;
    analysis_schema_version: string;
    information_cutoff_utc: string;
  };
  created_at_utc: string;
  updated_at_utc: string;
  lock_at_utc: string;
  locked_at_utc: string | null;
  payload_sha256: string | null;
}

export type PickRecord = UserPick;

export interface PickPoints {
  exact: number;
  outcome: number;
  total: number;
}

export interface PickScoring {
  user: PickPoints & { bonus: number };
  rivals: Array<PickPoints & { family: ModelFamily }>;
  beat_ai: boolean;
  best_rival_total: number;
}

export interface PickView {
  schema_version: typeof PICK_SCHEMA_VERSION;
  status: PickStatus;
  record: UserPick;
  result: (ScorePick & { outcome: Outcome }) | null;
  scoring: PickScoring | null;
  /** Web-preview practice record; never emitted by the real sidecar. */
  preview?: boolean;
}

export interface PickResponse {
  schema_version: typeof PICK_SCHEMA_VERSION;
  match_id: string;
  pick: PickView | null;
  editable: boolean;
  lock_at_utc: string | null;
  now_utc: string;
}

export interface PicksListResponse {
  schema_version: typeof PICK_SCHEMA_VERSION;
  items: PickView[];
  total: number;
  limit: number;
  offset: number;
}

export interface PicksSummary {
  schema_version: typeof PICK_SCHEMA_VERSION;
  season: string | null;
  counts: Record<PickStatus, number>;
  user: { total: number; exact: number; outcome: number; bonus: number };
  rivals: Array<{ family: ModelFamily; total: number; exact: number; outcome: number }>;
  series: Array<{
    kickoff_utc: string;
    match_id: string;
    user_total: number;
    per_family_totals: Partial<Record<ModelFamily, number>>;
  }>;
  accuracy: { exact: number; winner: number };
  streak: { current: number; best: number };
  goal_diff_mae: number;
}

export interface MatchDetailResponse {
  schema_version: SchemaVersion;
  match: MatchRow;
  linked_by: "match_id" | "fixture" | null;
  seal_eligibility?: SealEligibility;
  pick?: { id: string | null; status: PickStatus } | null;
  follow?: FollowedMatch | null;
}

// ---- Local followed-match monitoring (display/audit only) -----------------

export type FollowSubscriptionState = "active" | "unfollowed";
export type FollowResolutionState = "resolved" | "identity_unresolved";
export type FollowDataState =
  | "current"
  | "stale"
  | "source_conflict"
  | "source_unavailable"
  | "completed";
export type FollowEventType =
  | "followed"
  | "unfollowed"
  | "refollowed"
  | "match_repointed"
  | "identity_unresolved"
  | "kickoff_changed"
  | "venue_changed"
  | "score_published"
  | "settlement_available"
  | "settlement_recorded"
  | "source_revision_available"
  | "source_conflict"
  | "source_unavailable"
  | "source_recovered";
export type FollowNotificationStatus =
  | "not_eligible"
  | "pending"
  | "claimed"
  | "submitted"
  | "suppressed_visible"
  | "permission_denied"
  | "failed";

export type FollowMatchSnapshot = Omit<MatchRow, "forecasts">;

export interface FollowEvent {
  schema_version: typeof FOLLOW_SCHEMA_VERSION;
  event_id: string;
  follow_id: string;
  event_type: FollowEventType;
  detected_at_utc: string;
  effective_at_utc: string | null;
  source: {
    source_id: string;
    source_ref: string | null;
    checked_at_utc: string | null;
  };
  generation_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  conflict: Record<string, unknown> | null;
  read_at_utc: string | null;
  notification_status: FollowNotificationStatus;
}

export interface FollowedMatch {
  schema_version: typeof FOLLOW_SCHEMA_VERSION;
  follow_id: string;
  namespace: "core-cc0";
  subscription_state: FollowSubscriptionState;
  resolution_state: FollowResolutionState;
  data_state: FollowDataState;
  canonical_match_id: string;
  identity_source_id: string;
  upstream_fixture_key: string | null;
  created_at_utc: string;
  updated_at_utc: string;
  unfollowed_at_utc: string | null;
  last_observed_at_utc: string | null;
  current: FollowMatchSnapshot;
  unread_event_count: number;
  events: FollowEvent[];
}

export interface FollowListResponse {
  schema_version: typeof FOLLOW_SCHEMA_VERSION;
  items: FollowedMatch[];
  total: number;
  unread_event_count: number;
}

export interface FollowSettings {
  schema_version: typeof FOLLOW_SCHEMA_VERSION;
  notifications_opt_in: boolean;
  notifications_supported: boolean;
}

export interface FollowNotificationClaim {
  schema_version: typeof FOLLOW_SCHEMA_VERSION;
  batch_id: string | null;
  events: FollowEvent[];
}

// ---- Conditions Snapshot (display-only contract 0.3.0) --------------------

export type ContextStatus = "available" | "unknown";

export interface ContextSourceRef {
  source_id: string;
  source_record_id: string;
  source_revision: string;
  snapshot_sha256: string;
  retrieved_at_utc: string | null;
  field: string;
}

export interface ContextClaim {
  claim_id: string;
  source_refs: ContextSourceRef[];
}

export interface ContextDerivation {
  generator: "golavo-derived-context";
  algorithm_id: string;
  algorithm_version: string;
  formula: string;
  input_claim_ids: string[];
}

export interface ContextCapability {
  schema_version: "0.1.0";
  status: "available" | "partial" | "unavailable";
  display_only: true;
  model_input: false;
  context_pack_version: string | null;
  context_pack_sha256: string | null;
  index_fingerprint: string;
  features: Record<string, "available" | "partial" | "unknown" | "blocked">;
  reason_codes: string[];
}

export interface ConditionsLocation {
  status: ContextStatus;
  reason: string | null;
  entity_id: string | null;
  resolution_status: "resolved" | "unresolved";
  city: string | null;
  country: string | null;
  latitude: number | null;
  longitude: number | null;
  elevation_m: number | null;
  elevation_source: "survey" | "dem" | null;
  timezone: string | null;
  source_id: "geonames" | null;
  provenance: Record<string, ContextClaim>;
}

export interface ConditionsVenue {
  status: "available" | "unknown" | "conflict";
  reason: string | null;
  entity_id: string | null;
  name: string | null;
  latitude: number | null;
  longitude: number | null;
  capacity: number | null;
  identity_link_status: "accepted" | "conflicting" | "unknown";
  identity_conflict_reason: string | null;
  provenance: Record<string, ContextClaim>;
}

export interface ConditionsTeam {
  side: "home" | "away";
  team: string;
  team_entity_id: string;
  kickoff_gap: {
    status: ContextStatus;
    reason: string | null;
    precision: "exact" | "calendar-day" | "unknown";
    elapsed_hours: number | null;
    complete_days: number | null;
    calendar_gap_days: number | null;
    previous_match_id: string | null;
    previous_kickoff_utc: string | null;
    coverage_label: string;
    derivation: ContextDerivation | null;
  };
  rest: {
    status: ContextStatus;
    reason: string | null;
    days: number | null;
    previous_match_id: string | null;
    previous_kickoff_utc: string | null;
  };
  travel: {
    status: ContextStatus;
    reason: string | null;
    distance_km: number | null;
    origin: ConditionsLocation | null;
    destination: ConditionsLocation;
    measurement: "great-circle-between-indexed-match-locations";
    derivation: ContextDerivation | null;
  };
}

export interface TravelRoute {
  side: "home" | "away";
  team: string;
  distance_km: number;
  origin: ConditionsLocation;
  destination: ConditionsLocation;
  derivation: ContextDerivation;
}

export interface ConditionsSnapshot {
  schema_version: "0.3.0";
  label: "Context, not a model input.";
  capability: ContextCapability;
  match: {
    match_id: string;
    kickoff_utc: string;
    kickoff_precision: "exact" | "day";
    source_refs: ContextSourceRef[];
    local_kickoff: {
      status: ContextStatus;
      reason: string | null;
      value: string | null;
      timezone: string | null;
      utc_offset_minutes: number | null;
      tzdb_fingerprint: string | null;
      derivation: ContextDerivation | null;
    };
    venue: ConditionsVenue;
    location: ConditionsLocation;
  };
  teams: ConditionsTeam[];
  travel_map: {
    status: "available" | "partial" | "unknown";
    source_id: "natural-earth";
    attribution: string;
    routes: TravelRoute[];
  };
  weather_context: {
    status: "blocked";
    reason_code: "no_leakage_safe_historical_forecast_source";
    reason: string;
    model_input: false;
    source_id: null;
  };
  sources: Array<{
    source_id: "geonames" | "natural-earth" | "openfootball-worldcup-json" | "wikidata";
    attribution: string;
    license: string;
    upstream_ref: string;
    retrieved_at_utc: string;
    manifest_sha256: string;
  }>;
}

export interface WorldMapFeature {
  type: "Feature";
  properties: { name: string | null; iso_a2: string | null };
  geometry: {
    type: "Polygon" | "MultiPolygon";
    coordinates: number[][][] | number[][][][];
  };
}

export interface WorldMap {
  type: "FeatureCollection";
  source_id: "natural-earth";
  version: string;
  attribution: string;
  context_pack_version?: string;
  sha256?: string;
  features: WorldMapFeature[];
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

export type RefreshHealth =
  | "current"
  | "unchanged"
  | "stale"
  | "offline"
  | "backoff"
  | "invalid"
  | "conflict"
  | "unavailable";

export type RefreshCapability =
  | "available"
  | "partial"
  | "complete"
  | "absent"
  | "invalid"
  | "unavailable";

export interface RefreshErrorDetail {
  code: string;
  message: string;
  retryable: boolean;
  details?: Array<Record<string, unknown>>;
}

export interface RefreshSourceStatus {
  source_id: string;
  health: RefreshHealth;
  capability: RefreshCapability;
  active_ref: string | null;
  observed_ref: string | null;
  etag: string | null;
  last_checked_at_utc: string | null;
  last_changed_at_utc: string | null;
  last_activated_at_utc: string | null;
  data_through_utc: string | null;
  next_check_after_utc: string | null;
  season: string | null;
  current_paths: string[];
  competitions: Array<{
    competition?: string;
    league_code?: string;
    season?: string;
    capability: RefreshCapability;
    certificate?: Record<string, unknown>;
  }>;
  error: RefreshErrorDetail | null;
}

export interface DataRefreshJob {
  schema_version: "0.1.0";
  job_id: string;
  state: "queued" | "running" | "done" | "failed" | "cancelled";
  stage: "queued" | "checking" | "downloading" | "validating" | "building" | "activating" | "done";
  mode: "check" | "refresh";
  trigger: "manual" | "launch" | "periodic";
  scope?: "all" | "followed";
  source_ids: string[];
  created_at_utc: string;
  updated_at_utc: string;
  cancel_requested: boolean;
  progress: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: RefreshErrorDetail | null;
  deduplicated?: boolean;
}

export interface DataRefreshStatus {
  schema_version: "0.1.0";
  refresh_supported: boolean;
  active_generation: {
    generation_id: string;
    activated_at_utc: string | null;
    index_sha256: string;
    rollback_available: boolean;
    using_previous_generation: boolean;
    using_bundled_fallback: false;
  } | null;
  using_bundled_fallback: boolean;
  sources: RefreshSourceStatus[];
  job: DataRefreshJob | null;
  last_error: RefreshErrorDetail | null;
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

/** One completed result from a team's perspective (pre-cutoff), for the form strip. */
export interface FormEntry {
  result: "W" | "D" | "L";
  opponent: string;
  gf: number;
  ga: number;
  date: string; // YYYY-MM-DD
  is_home: boolean;
  neutral: boolean;
}

export interface TeamStyleEntry {
  attack: number;
  defence: number;
  expected_goals_for: number | null;
  expected_goals_against: number | null;
}

/** The goal voice's fitted-from-results style profile. NOT event data. */
export interface TeamStyle {
  family: ModelFamily;
  derivation: "fitted_from_results";
  baseline: number;
  clip: { min: number; max: number };
  teams: Record<string, TeamStyleEntry>;
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
    source_id?: string | null;
  };
  information_cutoff_utc: string;
  abstained: boolean;
  abstain_reason: string | null;
  /** Legacy compatibility tag. UI must present explanation.history_support,
   *  never relabel this match-count heuristic as confidence. */
  uncertainty: Uncertainty;
  team_history: Record<string, number>;
  min_team_matches: number;
  /** Last-5 results per team (optional so an older 0.3.0 backend degrades gracefully). */
  team_form?: Record<string, FormEntry[]>;
  /** Fitted style profile, or null when abstained (optional for the same reason). */
  team_style?: TeamStyle | null;
  council: CouncilSummary;
  models: CouncilModel[];
  score_matrix: ScoreMatrix | null;
  score_matrix_family: ModelFamily | null;
  /** Exact BTTS + clean-sheet marginals (0.4.1+). Null when the goal voice abstained. */
  derived_markets?: DerivedMarkets | null;
  /** Phase 8 descriptive explanation over the existing outputs. No new fit. */
  explanation?: AnalysisExplanation;
}

export type HistorySupportLevel = "limited" | "moderate" | "strong";
export type DisagreementStatus = "modal_agreement" | "modal_split" | "not_comparable";

export interface AnalysisExplanation {
  schema_version: "0.1.0";
  descriptive_only: true;
  hypothetical_only: true;
  averaged_consensus: false;
  calibrated_confidence: false;
  causal_claims: false;
  sealed_forecast_immutable: true;
  analysis_kind: AnalysisKind;
  history_support: {
    level: HistorySupportLevel;
    minimum_qualifying_matches: number;
    model_floor: number;
    meaning: string;
  };
  disagreement: {
    status: DisagreementStatus;
    voices: Array<{ family: string; method: string; modal_outcome: Outcome }>;
    outcome_gap_percentage_points: Record<Outcome, number> | null;
    largest_gap: { outcome: Outcome; percentage_points: number } | null;
    meaning: string;
  };
  change_triggers: Array<{ id: string; label: string; description: string }>;
  capability_coverage: {
    available_count: number;
    assessed_count: number;
    meaning: string;
    items: Array<{ id: string; label: string; available: boolean; source_ids: string[] }>;
  };
  missing_evidence: Array<"verified_lineups" | "verified_injuries" | "observed_xg">;
  provenance: {
    source_ids: string[];
    engine_source_id: "engine:match_analysis";
    formula_version: "analysis-explanation-1";
    input_fields: string[];
  };
}

/** Both-teams-to-score and clean-sheet marginals, computed exactly from the goal
 *  voice's full joint matrix (not recoverable from the truncated score grid). */
export interface DerivedMarkets {
  family: string;
  source: "full_resolution_matrix";
  btts: { yes: number; no: number };
  clean_sheets: { home: number; away: number };
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

export type MatchWindow = "week" | "month" | "upcoming";

export interface CompetitionCount {
  competition: string;
  source_kind: SourceKind;
  n_matches: number;
}

/** The Matchday home feed: matches within a time window + per-competition counts.
 *  week/month are anchored to the freshest result in the snapshot (see the server
 *  `matches_window`); `latest_result_utc` lets the UI show an honest staleness note. */
export interface MatchesWindowResponse {
  schema_version: SchemaVersion;
  window: MatchWindow;
  window_start_utc: string | null;
  window_end_utc: string | null;
  latest_result_utc: string | null;
  total: number;
  matches: MatchRow[];
  competitions: CompetitionCount[];
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

/** UI-only sub-grouping of the "context" label into readable categories, by
 *  template id. Display metadata — NOT part of the wire contract; an unknown id
 *  falls to "other" so future templates render without a code change. */
export type FactCategory = "form" | "head_to_head" | "records" | "signature" | "other";

export const FACT_CATEGORY: Record<string, FactCategory> = {
  unbeaten_run: "form",
  winless_run: "form",
  win_streak: "form",
  clean_sheet_run: "form",
  home_away_form: "form",
  in_form_scorer: "form",
  head_to_head_record: "head_to_head",
  head_to_head_goals: "head_to_head",
  biggest_win: "records",
  neutral_venue_record: "records",
  top_scorer: "records",
  shootout_record: "records",
  both_teams_scored_rate: "signature",
  clean_sheet_rate: "signature",
  scoring_trend: "signature",
  goal_timing_profile: "signature",
  penalty_goal_share: "signature",
  ht_comeback_record: "signature",
  ht_lead_conversion: "signature",
  wc_pedigree: "records",
  wc_awards: "records",
  tournament_record: "records",
  shootout_first_shooter_edge: "records",
  own_goal_quirk: "other",
};

export const FACT_CATEGORY_TEXT: Record<FactCategory, string> = {
  form: "Form",
  head_to_head: "Head-to-head",
  records: "Records",
  signature: "Signature stats",
  other: "Other",
};

/** Stable display order for the context sub-groups. */
export const FACT_CATEGORY_ORDER: FactCategory[] = [
  "form", "head_to_head", "records", "signature", "other",
];

/** Plain-language display copy for every registered fact template. The engine's
 *  exact, number-disciplined sentence remains the detailed source of truth; this
 *  metadata gives casual readers a short label and a one-line explanation for
 *  scanning. Unknown future templates fall back gracefully in the notebook. */
export interface FactDisplay {
  title: string;
  explainer: string;
}

export const FACT_DISPLAY: Record<string, FactDisplay> = {
  unbeaten_run: {
    title: "Unbeaten run",
    explainer: "How long this team has gone without losing.",
  },
  winless_run: {
    title: "Wait for a win",
    explainer: "How long it has been since this team last won.",
  },
  win_streak: {
    title: "Winning streak",
    explainer: "Consecutive wins in the team’s current run.",
  },
  clean_sheet_run: {
    title: "Clean-sheet streak",
    explainer: "Consecutive matches without conceding a goal.",
  },
  home_away_form: {
    title: "Venue form",
    explainer: "Recent results in the same home-or-away role as this fixture.",
  },
  in_form_scorer: {
    title: "In-form scorer",
    explainer: "The leading scorer across this team’s most recent matches.",
  },
  head_to_head_record: {
    title: "Previous meetings",
    explainer: "The win, draw and loss record when these teams have met.",
  },
  head_to_head_goals: {
    title: "Goals when they meet",
    explainer: "The scoring character of previous meetings between these teams.",
  },
  biggest_win: {
    title: "Biggest win",
    explainer: "The widest winning scoreline in the available history.",
  },
  neutral_venue_record: {
    title: "Neutral-ground record",
    explainer: "How this team has performed away from either side’s home ground.",
  },
  top_scorer: {
    title: "Leading scorer",
    explainer: "The team’s highest-scoring player in the available data.",
  },
  shootout_record: {
    title: "Penalty shootouts",
    explainer: "How often this team has won a shootout in the available history.",
  },
  both_teams_scored_rate: {
    title: "Both teams scored",
    explainer: "How often each side found the net in this team’s recent matches.",
  },
  clean_sheet_rate: {
    title: "Clean sheets",
    explainer: "How often this team stopped the opposition from scoring recently.",
  },
  scoring_trend: {
    title: "Scoring momentum",
    explainer: "Recent goals per game compared with the run immediately before it.",
  },
  goal_timing_profile: {
    title: "When they score",
    explainer: "Whether this team’s goals skew toward the opening or closing stages.",
  },
  penalty_goal_share: {
    title: "Penalty share",
    explainer: "How much of this team’s scoring comes from penalties (scored only).",
  },
  ht_comeback_record: {
    title: "Saved from behind",
    explainer: "Wins and draws recovered after trailing at half-time.",
  },
  ht_lead_conversion: {
    title: "Leads kept",
    explainer: "How often a half-time lead became a win.",
  },
  wc_pedigree: {
    title: "World Cup pedigree",
    explainer: "Titles, finals, appearances and the best recent finish in this data.",
  },
  wc_awards: {
    title: "World Cup awards",
    explainer: "Individual tournament awards won by this team’s players.",
  },
  tournament_record: {
    title: "Record in this competition",
    explainer: "This team’s all-time win record in the fixture’s competition.",
  },
  shootout_first_shooter_edge: {
    title: "Shooting first",
    explainer: "How often the side taking the first penalty goes on to win the shootout.",
  },
  own_goal_quirk: {
    title: "Own goals gifted",
    explainer: "A curio: how many own goals this team has benefited from.",
  },
  home_advantage_base_rate: {
    title: "Home advantage",
    explainer: "How often the home side has won in this competition’s history.",
  },
  competition_debut_base_rate: {
    title: "First-year teams",
    explainer: "How often newly arrived teams have won during their first year.",
  },
  day_of_week_streak: {
    title: "Day-of-week streak",
    explainer: "A calendar pattern kept separate from the forecast.",
  },
  scoreline_repeat: {
    title: "Repeated scoreline",
    explainer: "A score that has appeared more than once in this matchup.",
  },
  calendar_date_repeat: {
    title: "Calendar-date echo",
    explainer: "A date pattern shown as trivia, never as predictive evidence.",
  },
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
