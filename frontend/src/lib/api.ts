export type Role = 'demo' | 'admin' | 'api'
export type AnalysisStatus = 'pending' | 'approved' | 'rejected'

export interface Me {
  role: Role
  demo_analyses_left?: number
}

export interface Incident {
  id: number
  incident_id: string
  description: string
  latest_status: AnalysisStatus | null
}

export interface Analysis {
  probable_cause: string
  suggested_steps: string[]
  evidence: string[]
}

export interface SimilarIncident {
  incident_id: string
  similarity: number
  has_approved_analysis: boolean
}

export interface AnalysisRecord {
  thread_id: string
  status: AnalysisStatus
  analysis: Analysis
  similar_incidents: SimilarIncident[]
  reviewer_comment: string | null
  requested_by: string | null
  decided_by: string | null
  created_at: string
  reviewed_at: string | null
}

export interface PendingAnalysis {
  thread_id: string
  incident_id: string
  description: string
  probable_cause: string
  created_at: string
}

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

let onUnauthorized: () => void = () => {}

// The app uses this to send people to the sign-in page when their session ends
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

// A 401 from these is an answer ("not signed in", "wrong key"), not an expired session
const SIGN_IN_PATHS = ['/auth/me', '/auth/login']

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'X-Fixwright-Client': 'web' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(path, {
    method,
    headers,
    // The session cookie only ever goes back to this site
    credentials: 'same-origin',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    if (response.status === 401 && !SIGN_IN_PATHS.includes(path)) onUnauthorized()
    throw new ApiError(response.status, errorDetail(data))
  }
  return data as T
}

// FastAPI sends {"detail": "text"}, or {"detail": [{"msg": "..."}, ...]} for invalid input
function errorDetail(data: unknown): string {
  const detail = (data as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (item as { msg?: unknown } | null)?.msg)
      .filter((msg): msg is string => typeof msg === 'string')
      .join('. ')
  }
  return 'Request failed'
}

export function incidentPath(incidentId: string) {
  return '/incidents/' + encodeURIComponent(incidentId)
}

export const getMe = () => request<Me>('GET', '/auth/me')
export const signInDemo = () => request<Me>('POST', '/auth/demo')
export const signInAdmin = (apiKey: string) => request<Me>('POST', '/auth/login', { api_key: apiKey })
export const signOut = () => request<unknown>('POST', '/auth/logout')

export const listIncidents = () => request<Incident[]>('GET', '/incidents')
export const getIncident = (incidentId: string) => request<Incident>('GET', incidentPath(incidentId))
export const createIncident = (incidentId: string, description: string) =>
  request<unknown>('POST', '/incidents', { incident_id: incidentId, description })

export const listAnalyses = (incidentId: string) =>
  request<AnalysisRecord[]>('GET', incidentPath(incidentId) + '/analyses')
export const listPending = () => request<PendingAnalysis[]>('GET', '/analyses?status=pending')
export const analyze = (incidentId: string) => request<unknown>('POST', incidentPath(incidentId) + '/analyze')
export const decide = (threadId: string, approved: boolean, comment?: string) =>
  request<unknown>('POST', '/analyses/' + encodeURIComponent(threadId) + '/decision', {
    approved,
    comment: comment || null,
  })