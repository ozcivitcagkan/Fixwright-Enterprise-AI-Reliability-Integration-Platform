import { ChevronDown } from 'lucide-react'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import type { AnalysisRecord } from '@/lib/api'
import { timeAgo } from '@/lib/labels'

// Older analyses stay out of the way until someone asks for them
export function History({ records }: { records: AnalysisRecord[] }) {
  if (records.length === 0) return null

  return (
    <Collapsible className="space-y-3 border-t pt-4">
      <CollapsibleTrigger asChild>
        <Button variant="ghost" className="group px-0">
          Earlier analyses ({records.length})
          <ChevronDown className="transition-transform group-data-[state=open]:rotate-180" />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ul className="space-y-3">
          {records.map((record) => (
            <li key={record.thread_id} className="space-y-1">
              <div className="flex items-center gap-2">
                <StatusBadge status={record.status} />
                <span className="text-xs text-muted-foreground">{timeAgo(record.created_at)}</span>
              </div>
              <p className="text-sm whitespace-pre-wrap break-words">{record.analysis.probable_cause}</p>
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  )
}