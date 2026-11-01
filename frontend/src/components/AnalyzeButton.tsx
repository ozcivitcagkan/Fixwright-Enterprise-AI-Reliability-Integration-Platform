import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef } from 'react'
import { ErrorMessage } from '@/components/ErrorMessage'
import { useMe } from '@/components/RequireSession'
import { Button } from '@/components/ui/button'
import { analyze } from '@/lib/api'
import { analysesLeftText } from '@/lib/labels'

export function AnalyzeButton({ incidentId, again = false }: { incidentId: string; again?: boolean }) {
  const me = useMe()
  const queryClient = useQueryClient()
  // A second click can land before React has redrawn the button as disabled; this stops that one too
  const started = useRef(false)

  const run = useMutation({
    mutationFn: () => analyze(incidentId),
    // A new analysis changes this page, both home page lists and the demo allowance. Waiting for
    // the reloads keeps the button disabled until the analysis is on the page.
    onSuccess: () =>
      Promise.all(
        [['analyses', incidentId], ['incident', incidentId], ['pending'], ['incidents'], ['me']].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  })

  function start() {
    if (started.current) return
    started.current = true
    run.mutate(undefined, {
      onSettled: () => {
        started.current = false
      },
    })
  }

  return (
    <div className="space-y-2">
      <Button size="lg" disabled={run.isPending} onClick={start}>
        {run.isPending ? 'Analyzing… this takes 10 to 30 seconds' : again ? 'Analyze again' : 'Analyze'}
      </Button>
      {me.role === 'demo' && (
        <p className="text-sm text-muted-foreground">{analysesLeftText(me.demo_analyses_left ?? 0)}</p>
      )}
      <ErrorMessage error={run.error} />
    </div>
  )
}