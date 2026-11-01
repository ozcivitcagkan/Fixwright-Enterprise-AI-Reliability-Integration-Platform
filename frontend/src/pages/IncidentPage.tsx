import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router'
import { AnalysisView, DecidedResult } from '@/components/AnalysisView'
import { AnalyzeButton } from '@/components/AnalyzeButton'
import { DecisionButtons } from '@/components/DecisionButtons'
import { ErrorMessage } from '@/components/ErrorMessage'
import { History } from '@/components/History'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { getIncident, listAnalyses } from '@/lib/api'
import { incidentState } from '@/lib/incidentState'

export function IncidentPage() {
  const { incidentId = '' } = useParams()
  // A new key per incident, so following a similar-incident link starts with a clean page
  return <IncidentDetails key={incidentId} incidentId={incidentId} />
}

function IncidentDetails({ incidentId }: { incidentId: string }) {
  // The analysis someone else decided while this page was open, to explain why the page changed
  const [decidedElsewhere, setDecidedElsewhere] = useState<string | null>(null)
  const incident = useQuery({ queryKey: ['incident', incidentId], queryFn: () => getIncident(incidentId) })
  const analyses = useQuery({ queryKey: ['analyses', incidentId], queryFn: () => listAnalyses(incidentId) })

  const error = (incident.data ? null : incident.error) ?? (analyses.data ? null : analyses.error)
  if (error) return <ErrorMessage error={error} />
  if (!incident.data || !analyses.data) return null

  const state = incidentState(analyses.data)

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold break-words">{incident.data.incident_id}</h1>
        <p className="whitespace-pre-wrap break-words text-muted-foreground">{incident.data.description}</p>
      </section>

      {state.kind !== 'none' && state.latest.thread_id === decidedElsewhere && (
        <Alert>
          <AlertDescription>This analysis was already decided.</AlertDescription>
        </Alert>
      )}

      {state.kind === 'none' && <AnalyzeButton incidentId={incidentId} />}
      {state.kind === 'pending' && (
        <>
          <AnalysisView record={state.latest} />
          <DecisionButtons
            incidentId={incidentId}
            threadId={state.latest.thread_id}
            onAlreadyDecided={setDecidedElsewhere}
          />
        </>
      )}
      {state.kind === 'decided' && (
        <>
          <DecidedResult record={state.latest} />
          <AnalyzeButton incidentId={incidentId} again />
        </>
      )}

      {state.kind !== 'none' && <History records={state.history} />}
    </div>
  )
}