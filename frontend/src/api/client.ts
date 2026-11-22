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

export type RarityStatus =
  | 'being_seen'
  | 'single_report'
  | 'no_news'
  | 'no_new_reports'
  | 'probably_gone'

export interface Rarity {
  species_code: string
  common_name: string
  status: RarityStatus
  reason: string | null
  first_reported: string
  last_reported: string
  outings: number
  outings_today: number
  outings_yesterday: number
  days_reported: number
  unreviewed: boolean
  hotspots: string[]
  area: string | null
  is_current: boolean
}

export interface RaritiesResponse {
  region_code: string
  today: string
  updated_at: string | null
  counts_through: string | null
  items: Rarity[]
}

export interface RaritySearch {
  id: number
  species_code: string
  common_name: string
  searched_at: string
  found: boolean
  status_then: RarityStatus | null
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

// The search log requires this header, which other websites can't send to localhost
const APP_HEADER = { 'X-Field-Odds': '1' }

async function request(path: string, init: RequestInit = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...APP_HEADER, 'Content-Type': 'application/json' },
  })
  if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`)
  return res
}

export const api = {
  rarities: () => get<RaritiesResponse>('/api/rarities'),
  searches: async () => (await (await request('/api/searches')).json()) as RaritySearch[],
  logSearch: (speciesCode: string, found: boolean, searchedAt?: string) =>
    request('/api/searches', {
      method: 'POST',
      body: JSON.stringify({ species_code: speciesCode, found, searched_at: searchedAt }),
    }),
  removeSearch: (id: number) => request(`/api/searches/${id}`, { method: 'DELETE' }),
  today: (opts: { region?: string; minLikelihood?: number } = {}) =>
    get<TodayResponse>('/api/predictions/today', {
      region: opts.region,
      min_likelihood: opts.minLikelihood,
    }),
  pipelineRuns: (limit = 20) => get<PipelineRun[]>('/api/pipeline/runs', { limit }),
}
