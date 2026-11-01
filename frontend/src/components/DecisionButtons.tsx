import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ErrorMessage } from '@/components/ErrorMessage'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, decide } from '@/lib/api'

type Props = {
  incidentId: string
  threadId: string
  onAlreadyDecided: (threadId: string) => void
}

export function DecisionButtons({ incidentId, threadId, onAlreadyDecided }: Props) {
  const queryClient = useQueryClient()
  const [commenting, setCommenting] = useState(false)
  const [comment, setComment] = useState('')

  const decision = useMutation({
    mutationFn: (approved: boolean) => decide(threadId, approved, comment.trim()),
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) onAlreadyDecided(threadId)
    },
    // After our decision, or after learning that someone else made one, show what is stored now
    onSettled: () =>
      Promise.all(
        [['analyses', incidentId], ['incident', incidentId], ['pending'], ['incidents']].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      ),
  })

  // The page shows the 409 message itself, because this part disappears once the page reloads
  const conflict = decision.error instanceof ApiError && decision.error.status === 409

  return (
    <div className="space-y-3">
      {commenting ? (
        <div className="space-y-2">
          <Label htmlFor="decision-comment">Comment</Label>
          <Textarea
            id="decision-comment"
            rows={3}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
          />
        </div>
      ) : (
        <Button variant="link" className="h-auto px-0" onClick={() => setCommenting(true)}>
          Add a comment
        </Button>
      )}

      <div className="flex gap-2">
        <Button size="lg" disabled={decision.isPending} onClick={() => decision.mutate(true)}>
          Approve
        </Button>
        <Button size="lg" variant="outline" disabled={decision.isPending} onClick={() => decision.mutate(false)}>
          Reject
        </Button>
      </div>

      <ErrorMessage error={conflict ? null : decision.error} />
    </div>
  )
}