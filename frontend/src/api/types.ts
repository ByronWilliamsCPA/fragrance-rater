export type Person = { id: string; name: string }

export type FragranceSummary = Person & {
  brand: string
  concentration: string
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
  liking: number | null
  comments: string | null
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
  skin_plan_locked: boolean
  presentations: Sample[]
}

export type Program = Person & {
  version: string
  status: string
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
