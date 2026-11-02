import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Card, CardContent } from '@/components/ui/card'
import { incidentPath, listPending } from '@/lib/api'
import { timeAgo } from '@/lib/labels'

const CAUSE_LENGTH = 120

function shorten(text: string) {
  return text.length > CAUSE_LENGTH ? text.slice(0, CAUSE_LENGTH) + '…' : text
}

// Shown only when an analysis waits for a decision, so the work to do is the first thing on the page
export function PendingCards() {
  const pending = useQuery({ queryKey: ['pending'], queryFn: listPending })
  if (!pending.data?.length) return null

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Waiting for your decision</h2>
      {pending.data.map((item) => (
        // The page path is the same as the API path, so incidentPath gives the encoded link too
        <Link key={item.thread_id} to={incidentPath(item.incident_id)} className="block">
          <Card className="transition-colors hover:bg-muted/50">
            <CardContent className="space-y-1">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-medium break-all">{item.incident_id}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(item.created_at)}</span>
              </div>
              <p className="text-sm break-words text-muted-foreground">{shorten(item.probable_cause)}</p>
            </CardContent>
          </Card>
        </Link>
      ))}
    </section>
  )
}