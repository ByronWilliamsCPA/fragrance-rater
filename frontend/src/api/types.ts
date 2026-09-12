export type Person = { id: string; name: string }

export type FragranceSummary = Person & {
  brand: string
  concentration: string
  version_key: string
}

export type Access = {
  username: string
  manager: boolean
}

export type Assignment = {
  id: string
  program_id: string
  reviewer_id: string
}

export type Observation = {
  id: string
  phase: string
  stage: string
  elapsed_minutes: number
  detected: boolean | null
  intensity: number | null
  liking: number | null
  confidence: number | null
  sweetness: number | null
  freshness: number | null
  density: number | null
  familiarity: number | null
  dryness: number | null
  clean_soapy: number | null
  earthy_rooty: number | null
  bodily_animalic: number | null
  discomfort: number | null
  opening_liking: number | null
  drydown_liking: number | null
  would_wear: number | null
  would_buy: number | null
  artistic_appreciation: number | null
  projection: number | null
  longevity_minutes: number | null
  perceived_notes: string[] | null
  likes: string | null
  dislikes: string | null
  reminds_me_of: string | null
  comments: string | null
}

export type Prediction = {
  id: string
  reviewer_id: string
  fragrance_id: string
  checkpoint_id: string | null
  model_id: string
  model_version: string
  feature_snapshot_version: string | null
  predicted_scale: string
  predicted_rating: number | null
  uncertainty: number | null
  percentile_rank: number | null
  scenario: string | null
  input_manifest: Record<string, unknown>[]
  explanation: Record<string, unknown> | null
  created_at: string
  recorded_by: string | null
  outcome_evaluation_id: string | null
  outcome_observation_id: string | null
  outcome_linked_at: string | null
  outcome_recorded_by: string | null
}

export type Sample = {
  id: string
  session_id: string
  blind_code: string
  position: number
  skin_planned: boolean
  blotter_locked: boolean
  skin_locked: boolean
  identity?: { name: string; brand: string; concentration: string }
  observations: Observation[]
}

export type Enrollment = Assignment & {
  revealed: boolean
  reveal_eligible: boolean
  reveal_blocker: 'BLOTTER' | 'SKIN_PLAN' | 'SKIN' | null
  skin_plan_locked: boolean
  presentations: Sample[]
}

export type Program = Person & {
  version: string
  status: string
}

export type FragellaResult = {
  id: string
  name: string
  brand: string
  year: number | null
  oil_type: string | null
  gender: string | null
  general_notes: string[]
  top_notes: string[]
  middle_notes: string[]
  base_notes: string[]
  confidence: string | null
}

export type FragellaLookupSummary = {
  checked_at: string
  query: string
  status: 'success' | 'error'
  error_message: string | null
  results: FragellaResult[]
}

export type FragellaUsage = {
  plan?: string
  billing_period?: { start?: string; end?: string }
  limit?: { total_effective_limit?: number }
  usage?: { requests_made?: number; requests_remaining?: number }
}

export type ProgramMember = {
  id: string
  fragrance_id: string
  fragrance_name: string
  fragrance_brand: string
  concentration: string
  version_key: string
  role: string
  repeat_of_id: string | null
  group_name: string
  identity_evidence: string | null
  fragella: FragellaLookupSummary | null
}

export type ManagerEnrollment = {
  id: string
  program_name: string
  program_version: string
  reviewer_name: string
  recorder_usernames: string[]
  total_presentations: number
  blotter_complete: number
  skin_planned: number
  skin_complete: number
  reveal_eligible: boolean
  reveal_blocker: 'BLOTTER' | 'SKIN_PLAN' | 'SKIN' | null
  revealed: boolean
}

export type MappingRow = {
  session_id: string
  position: number
  blind_code: string
  fragrance_name: string
  fragrance_brand: string
  concentration: string
  version_key: string
  role: string
}

export type OperationalEvent = {
  id: string
  reviewer_id: string
  event_type: 'CONNECTIVITY_FAILURE' | 'MANUAL_RECOVERY'
  details: string | null
  occurred_at: string
  recorded_by: string
}

export type OperationalStatus = {
  status: 'available' | 'attention'
  unresolved_reviewer_ids: string[]
  guidance: string
}

export type Metrics = {
  reviewer_id: string
  window_start: string
  window_end: string
  reviewer_population: string[]
  exclusion_policy: string[]
  excluded_impressions: number
  algorithm_versions: string[]
  candidate_strategies: string[]
  run_filters: Record<string, unknown>[]
  source_snapshots: Record<string, unknown>[]
  eligible_impressions: number
  explicit_interest_responses: number
  positive_interest_responses: number
  response_coverage: number | null
  interest_rate: number | null
  sampled_recommendations: number
  sampling_conversion: number | null
  linked_outcomes: number
  connectivity_failures: number
  manual_recoveries: number
  [key: string]: unknown
}

export type Encounter = {
  id: string
  fragrance_id: string
  rating: number
  evaluated_at: string
  notes?: string | null
}

export type RecommendationImpression = {
  id: string
  fragrance_id: string
  fragrance_name: string
  fragrance_brand: string
  rank: number
  match_percent: number
  shown_at: string
  responses: RecommendationResponse[]
}

export type RecommendationRun = {
  id: string
  reviewer_id: string
  created_at: string
  impressions: RecommendationImpression[]
}

export type RecommendationResponse = {
  id: string
  impression_id: string
  revision: number
  created_at: string
  interested: boolean | null
  sampling_state: 'PLANNED' | 'ACQUIRED' | 'SAMPLED' | 'UNAVAILABLE' | null
  unavailable_reason: string | null
  outcome_evaluation_id: string | null
  outcome_observation_id: string | null
  would_wear: boolean | null
  would_buy: boolean | null
}

export type HistoryItem = {
  id: string
  workflow: 'ORDINARY' | 'CONTROLLED'
  fragrance_id?: string
  identity?: { fragrance_id: string; name: string; brand: string }
  observed_at?: string
  created_at?: string
  rating?: number
  liking?: number | null
}

export type Capabilities = {
  canRecordCalibration: boolean
  canManagePrograms: boolean
}

export function capabilitiesFor(access: Access, assignments: Assignment[]): Capabilities {
  return {
    canRecordCalibration: access.manager || assignments.length > 0,
    canManagePrograms: access.manager,
  }
}
