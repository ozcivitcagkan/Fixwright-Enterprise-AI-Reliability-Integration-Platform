import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { ErrorMessage } from '@/components/ErrorMessage'
import { StatusBadge } from '@/components/StatusBadge'
import { incidentPath, listIncidents } from '@/lib/api'

export function IncidentList() {
  const incidents = useQuery({ queryKey: ['incidents'], queryFn: listIncidents })

  if (incidents.isError) return <ErrorMessage error={incidents.error} />
  if (!incidents.data) return null
  if (incidents.data.length === 0) return <p className="text-sm text-muted-foreground">No incidents yet.</p>

  return (
    <ul className="divide-y rounded-xl border">
      {incidents.data.map((incident) => (
        <li key={incident.id}>
          <Link
            to={incidentPath(incident.incident_id)}
            className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/50"
          >
            <span className="max-w-[40%] shrink-0 truncate font-medium">{incident.incident_id}</span>
            <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">{incident.description}</span>
            <StatusBadge status={incident.latest_status} />
          </Link>
        </li>
      ))}
    </ul>
  )
}