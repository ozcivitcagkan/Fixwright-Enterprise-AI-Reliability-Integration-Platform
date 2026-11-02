import type { AnalysisStatus } from './api'

// 0.45 is the search cut-off; in the retrieval eval every match from 0.55 up was relevant
export function similarityLabel(score: number): 'Strong match' | 'Possible match' {
  return score >= 0.55 ? 'Strong match' : 'Possible match'
}

const STATUS_LABELS = { pending: 'Pending', approved: 'Approved', rejected: 'Rejected' } as const

export function statusLabel(status: AnalysisStatus | null) {
  return status === null ? 'Not analyzed' : STATUS_LABELS[status]
}

export function analysesLeftText(count: number) {
  return `${count} ${count === 1 ? 'analysis' : 'analyses'} left today`
}

// Largest unit first, so three hours reads "3 hours ago" and not "180 minutes ago"
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 60 * 60],
  ['month', 30 * 24 * 60 * 60],
  ['week', 7 * 24 * 60 * 60],
  ['day', 24 * 60 * 60],
  ['hour', 60 * 60],
  ['minute', 60],
]

export function timeAgo(iso: string, now: Date = new Date()) {
  const seconds = (new Date(iso).getTime() - now.getTime()) / 1000
  const format = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return format.format(Math.round(seconds / size), unit)
  }
  return format.format(0, 'second')
}