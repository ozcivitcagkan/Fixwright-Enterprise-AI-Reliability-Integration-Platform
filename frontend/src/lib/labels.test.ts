import { expect, test } from 'vitest'
import { analysesLeftText, similarityLabel, statusLabel, timeAgo } from './labels'

test.each([
  [0.72, 'Strong match'],
  [0.55, 'Strong match'],
  [0.549, 'Possible match'],
  [0.45, 'Possible match'],
])('similarity %s is %s', (score, label) => {
  expect(similarityLabel(score)).toBe(label)
})

test.each([
  ['pending', 'Pending'],
  ['approved', 'Approved'],
  ['rejected', 'Rejected'],
  [null, 'Not analyzed'],
] as const)('status %s is shown as %s', (status, label) => {
  expect(statusLabel(status)).toBe(label)
})

test('analyses left text', () => {
  expect(analysesLeftText(1)).toBe('1 analysis left today')
  expect(analysesLeftText(27)).toBe('27 analyses left today')
})

test('time ago in plain words', () => {
  const now = new Date('2026-10-31T12:00:00Z')

  expect(timeAgo('2026-10-31T11:59:30Z', now)).toBe('now')
  expect(timeAgo('2026-10-31T10:00:00Z', now)).toBe('2 hours ago')
  expect(timeAgo('2026-10-30T12:00:00Z', now)).toBe('yesterday')
})