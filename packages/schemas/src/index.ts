// packages/schemas/src/index.ts
// Thailand Digital Market Twin Platform — 版本化数据契约 v1

// ─────────────────────────────────────────
// Study Input
// ─────────────────────────────────────────
export interface StudyInputV1 {
  schema_version: "1";
  study_type: StudyType;
  name: string;
  description?: string;
  language: "zh" | "en" | "th";
  population_size: PopulationSize;
  inputs: StudyInputData;
  business_questions: string[];
  scenarios?: ScenarioDefinition[];
  assumptions?: AssumptionOverride[];
}

export type StudyType =
  | "PRODUCT_VALIDATION"
  | "VENUE_STUDY"
  | "SITE_COMPARISON"
  | "PRICING_STUDY"
  | "CREATIVE_TEST"
  | "OPERATING_SCENARIO"
  | "RESTAURANT"
  | "CAFE"
  | "BAR"
  | "RETAIL";

export type PopulationSize = 100 | 10000 | 30000 | 100000 | 300000;

export interface StudyInputData {
  text_description?: string;
  product_name?: string;
  price?: number;
  currency?: string;
  selling_points?: string[];
  channels?: string[];
  competitor_products?: string[];
  venue_type?: string;
  location?: {
    address?: string;
    lat?: number;
    lng?: number;
    google_maps_url?: string;
  };
  operating_hours?: OperatingHours;
  capacity?: number;
  average_check?: number;
  cuisine_type?: string;
  menu_items?: string[];
  parking_available?: boolean;
  delivery_available?: boolean;
  advertising_budget?: number;
  target_audience_description?: string;
  file_ids?: string[];
}

export interface OperatingHours {
  monday?: DayHours;
  tuesday?: DayHours;
  wednesday?: DayHours;
  thursday?: DayHours;
  friday?: DayHours;
  saturday?: DayHours;
  sunday?: DayHours;
}

export interface DayHours {
  open: string; // "HH:MM"
  close: string;
  is_closed?: boolean;
}

export interface ScenarioDefinition {
  scenario_id: string;
  name: string;
  changes: Record<string, unknown>;
}

export interface AssumptionOverride {
  field: string;
  value: unknown;
  source: "user_confirmed" | "system_default" | "user_override";
}

// ─────────────────────────────────────────
// Population Profile
// ─────────────────────────────────────────
export interface PopulationProfileV1 {
  schema_version: "1";
  world_model_version: string;
  population_size: number;
  seed: number;
  geo_focus: string;
  segments: PopulationSegment[];
  generated_at: string;
  parquet_uri: string;
}

export interface PopulationSegment {
  segment_id: string;
  name: string;
  size: number;
  share: number;
  key_characteristics: Record<string, unknown>;
}

// ─────────────────────────────────────────
// Agent Response
// ─────────────────────────────────────────
export interface AgentResponseV1 {
  schema_version: "1";
  representative_id: string;
  segment_id: string;
  study_run_id: string;
  prompt_version: string;
  model_provider: string;
  model_id: string;
  awareness_probability: number;
  comprehension_score: number;
  interest_score: number;
  trust_score: number;
  value_score: number;
  purchase_probability: number | null;
  visit_probability: number | null;
  repeat_probability: number;
  share_probability: number;
  main_reasons: string[];
  main_barriers: string[];
  confidence: number;
  generated_at: string;
}

// ─────────────────────────────────────────
// Simulation Config
// ─────────────────────────────────────────
export interface SimulationConfigV1 {
  schema_version: "1";
  run_id: string;
  study_type: StudyType;
  population_size: number;
  monte_carlo_rounds: number;
  scenarios: ScenarioDefinition[];
  sensitivity_params: string[];
  root_seed: number;
  world_model_version: string;
  simulation_model_version: string;
  prompt_version: string;
}

// ─────────────────────────────────────────
// Metric Result
// ─────────────────────────────────────────
export interface MetricResultV1 {
  schema_version: "1";
  run_id: string;
  scenario_id: string | null;
  metric_code: string;
  metric_label: string;
  segment_code: string | null;
  value_mean: number;
  value_median: number;
  value_p10: number;
  value_p25: number;
  value_p75: number;
  value_p90: number;
  standard_deviation: number;
  unit: string;
  sample_population: number;
  rounds: number;
  data_version: string;
  model_version: string;
}

// ─────────────────────────────────────────
// Report Data
// ─────────────────────────────────────────
export interface ReportDataV1 {
  schema_version: "1";
  report_id: string;
  run_id: string;
  study_id: string;
  language: "zh" | "en" | "th";
  generated_at: string;
  executive_summary: ExecutiveSummary;
  study_setup: StudySetup;
  market_response: MarketResponse;
  segments: SegmentResult[];
  scenarios: ScenarioComparison[];
  consumer_voices: ConsumerVoice[];
  assumptions: AssumptionItem[];
  methodology: string;
}

export interface ExecutiveSummary {
  recommendation: string;
  best_audience: string;
  main_barrier: string;
  best_scenario: string | null;
  next_steps: string[];
  key_metrics: MetricResultV1[];
}

export interface StudySetup {
  study_type: StudyType;
  population_size: number;
  monte_carlo_rounds: number;
  scenario_count: number;
  world_model_version: string;
  simulation_model_version: string;
}

export interface MarketResponse {
  eligible_population: number;
  reach: number;
  notice_rate: number;
  comprehension_rate: number;
  consideration_rate: number;
  purchase_rate: MetricResultV1;
  repeat_rate: MetricResultV1;
  referral_rate: MetricResultV1;
  funnel_chart_data: FunnelStage[];
}

export interface FunnelStage {
  stage: string;
  label: string;
  value: number;
}

export interface SegmentResult {
  segment_id: string;
  segment_name: string;
  size: number;
  share: number;
  purchase_rate: number;
  key_drivers: string[];
  key_barriers: string[];
}

export interface ScenarioComparison {
  scenario_id: string;
  scenario_name: string;
  purchase_rate: MetricResultV1;
  revenue_index: MetricResultV1;
  margin_index: MetricResultV1;
  vs_baseline_pct: number;
}

export interface ConsumerVoice {
  persona_description: string;
  segment_id: string;
  sentiment: "positive" | "neutral" | "negative";
  quote: string;
  reasoning: string;
}

export interface AssumptionItem {
  field: string;
  label: string;
  value: unknown;
  source: "identified_fact" | "system_inference" | "missing_default";
  confidence_grade: "A" | "B" | "C" | "D";
  note?: string;
}

// ─────────────────────────────────────────
// Project Status Machine
// ─────────────────────────────────────────
export type StudyStatus =
  | "DRAFT"
  | "PARSING"
  | "NEEDS_CONFIRMATION"
  | "READY"
  | "QUEUED"
  | "PREPARING_POPULATION"
  | "RUNNING_AGENTS"
  | "RUNNING_SIMULATION"
  | "RUNNING_SCENARIOS"
  | "GENERATING_REPORT"
  | "COMPLETED"
  | "PAUSED"
  | "RETRYING"
  | "FAILED_RECOVERABLE"
  | "FAILED_FINAL"
  | "CANCEL_REQUESTED"
  | "CANCELLED"
  | "EXPIRED";

export type PlanCode = "PREVIEW" | "STANDARD" | "PROFESSIONAL" | "DEEP" | "ENTERPRISE";

export const PLAN_POPULATION: Record<PlanCode, PopulationSize> = {
  PREVIEW: 100,
  STANDARD: 10000,
  PROFESSIONAL: 30000,
  DEEP: 100000,
  ENTERPRISE: 300000,
};
