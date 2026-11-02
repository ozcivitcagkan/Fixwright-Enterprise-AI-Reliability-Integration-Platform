import { Link } from 'react-router'
import { Section } from '@/components/Section'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { incidentPath, type SimilarIncident } from '@/lib/api'
import { similarityLabel } from '@/lib/labels'

// Plain labels for people; the raw score stays in a tooltip for those who want it
export function SimilarIncidents({ items }: { items: SimilarIncident[] }) {
  if (items.length === 0) return null

  return (
    <Section title="Similar incidents">
      <TooltipProvider>
        <ul className="space-y-2">
          {items.map((item) => {
            const label = similarityLabel(item.similarity)
            return (
              <li key={item.incident_id} className="flex flex-wrap items-center gap-2">
                <Link to={incidentPath(item.incident_id)} className="font-medium break-all underline-offset-4 hover:underline">
                  {item.incident_id}
                </Link>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant={label === 'Strong match' ? 'default' : 'outline'} tabIndex={0}>
                      {label}
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>Similarity {item.similarity.toFixed(2)}</TooltipContent>
                </Tooltip>
                {item.has_approved_analysis && <span className="text-xs text-muted-foreground">approved analysis</span>}
              </li>
            )
          })}
        </ul>
      </TooltipProvider>
    </Section>
  )
}