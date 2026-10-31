import { useParams } from 'react-router'

export function IncidentPage() {
  const { incidentId } = useParams()
  return <h1 className="text-2xl font-semibold break-words">{incidentId}</h1>
}