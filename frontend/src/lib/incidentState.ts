import type { AnalysisRecord } from './api'

export type IncidentState =
  | { kind: 'none' }
  | { kind: 'pending' | 'decided'; latest: AnalysisRecord; history: AnalysisRecord[] }

// The API lists analyses newest first; the newest one decides what the page shows
export function incidentState(analyses: AnalysisRecord[]): IncidentState {
  const [latest, ...history] = analyses
  if (!latest) return { kind: 'none' }
  return { kind: latest.status === 'pending' ? 'pending' : 'decided', latest, history }
}