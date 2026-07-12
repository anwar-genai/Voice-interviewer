// Shared API shapes. Hand-written to mirror the backend Pydantic models
// (app/llm/schemas.py, app/routers/interviews.py). Small and stable enough that
// an OpenAPI codegen pipeline would be more machinery than it's worth.
// ponytail: hand-written types; wire up openapi-typescript if the API surface grows.

/** ParsedJob — every field optional (extraction may miss any of them). */
export type Job = {
  job_title: string | null
  job_type: string | null
  location: string | null
  start_date: string | null
  qualifications: string | null
  responsibilities: string | null
  benefits: string | null
}

export type Feedback = {
  strengths: string[]
  improvements: string[]
  recommendations: string[]
  overall_score: number
  technical_score: number
  communication_score: number
}

export type InterviewSummary = {
  id: string
  status: string
  job_title: string | null
  overall_score: number | null
  created_at: string
}

export type Turn = { role: 'agent' | 'user'; content: string }

export type InterviewDetail = InterviewSummary & {
  job: Partial<Job>
  resume: string
  turns: Turn[]
}
