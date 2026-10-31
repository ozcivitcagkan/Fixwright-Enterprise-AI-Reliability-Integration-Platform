import { expect, test } from 'vitest'
import type { AnalysisRecord, AnalysisStatus } from './api'
import { incidentState } from './incidentState'

function record(status: AnalysisStatus, threadId: string): AnalysisRecord {
  const decided = status !== 'pending'
  return {
    thread_id: threadId,
    status,
    analysis: { probable_cause: 'Disk full', suggested_steps: [], evidence: [] },
    similar_incidents: [],
    reviewer_comment: null,
    requested_by: 'demo',
    decided_by: decided ? 'demo' : null,
    created_at: '2026-10-31T10:00:00Z',
    reviewed_at: decided ? '2026-10-31T10:05:00Z' : null,
  }
}

test('no analyses means nothing to show yet', () => {
  expect(incidentState([])).toEqual({ kind: 'none' })
})

test('a pending newest analysis waits for a decision and older ones are history', () => {
  const pending = record('pending', 't2')
  const approved = record('approved', 't1')

  expect(incidentState([pending, approved])).toEqual({
    kind: 'pending',
    latest: pending,
    history: [approved],
  })
})

test('a decided newest analysis shows the result', () => {
  const rejected = record('rejected', 't1')

  expect(incidentState([rejected])).toEqual({ kind: 'decided', latest: rejected, history: [] })
})