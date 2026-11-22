// Typed wrapper around the Field Odds API. Types mirror backend/app/api/schemas.py.

export interface PredictionItem {
  species_code: string
  common_name: string
  sci_name: string | null
  likelihood: number
  sample_size: number | null
  reported_days_ago: number | null
  last_seen: string | null
  last_location: string | null
}

export interface TodayResponse {
  region_code: string
  for_date: string | null
  model_name: string
  items: PredictionItem[]
}

export interface PipelineRun {
  id: number
  job_name: string
  params: Record<string, unknown>
  status: 'running' | 'success' | 'failed'
  rows_written: number
  error: string | null
  started_at: string
  finished_at: string | null
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function get<T>(path: string, params: Record<string, string | number | undefined> = {}) {
  const query = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined) query.set(k, String(v))
  const qs = query.toString()
  const res = await fetch(`${BASE}${path}${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`)
  return (await res.json()) as T
}

export const api = {
  today: (opts: { region?: string; minLikelihood?: number } = {}) =>
    get<TodayResponse>('/api/predictions/today', {
      region: opts.region,
      min_likelihood: opts.minLikelihood,
    }),
  pipelineRuns: (limit = 20) => get<PipelineRun[]>('/api/pipeline/runs', { limit }),
}
