import { Badge } from '@/components/ui/badge'
import type { AnalysisStatus } from '@/lib/api'
import { statusLabel } from '@/lib/labels'

// Pending is the dark one because it is the only status that waits for someone
const VARIANTS = { pending: 'default', approved: 'secondary', rejected: 'destructive' } as const

export function StatusBadge({ status }: { status: AnalysisStatus | null }) {
  return <Badge variant={status === null ? 'outline' : VARIANTS[status]}>{statusLabel(status)}</Badge>
}