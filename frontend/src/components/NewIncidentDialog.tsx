import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { DemoNotice } from '@/components/DemoNotice'
import { ErrorMessage } from '@/components/ErrorMessage'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { createIncident, incidentPath, type Role } from '@/lib/api'

// Only characters that stay as they are in a URL, so a new ID can never break a link
const INCIDENT_ID = /^[A-Za-z0-9._-]{1,100}$/
const DEMO_MAX_DESCRIPTION = 1000

export function NewIncidentDialog({ role }: { role: Role }) {
  const [open, setOpen] = useState(false)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>New incident</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New incident</DialogTitle>
          <DialogDescription>Describe what went wrong. You can analyze it on the next page.</DialogDescription>
        </DialogHeader>
        <NewIncidentForm role={role} onCreated={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  )
}

// Lives inside the dialog, so closing the dialog also clears what was typed
function NewIncidentForm({ role, onCreated }: { role: Role; onCreated: () => void }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [incidentId, setIncidentId] = useState('')
  const [description, setDescription] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const create = useMutation({
    mutationFn: (input: { id: string; description: string }) => createIncident(input.id, input.description),
    onSuccess: (_answer, input) => {
      void queryClient.invalidateQueries({ queryKey: ['incidents'] })
      onCreated()
      void navigate(incidentPath(input.id))
    },
  })

  const idValid = INCIDENT_ID.test(incidentId)
  const descriptionValid = description.trim() !== ''

  return (
    <form
      noValidate
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        setSubmitted(true)
        if (idValid && descriptionValid) create.mutate({ id: incidentId, description: description.trim() })
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="incident-id">Incident ID</Label>
        <Input
          id="incident-id"
          autoComplete="off"
          value={incidentId}
          onChange={(event) => setIncidentId(event.target.value)}
          aria-invalid={submitted && !idValid}
          aria-describedby="incident-id-hint"
        />
        <p id="incident-id-hint" className={submitted && !idValid ? 'text-xs text-destructive' : 'text-xs text-muted-foreground'}>
          Letters, numbers, dot, dash and underscore
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="incident-description">Description</Label>
        <Textarea
          id="incident-description"
          rows={5}
          maxLength={role === 'demo' ? DEMO_MAX_DESCRIPTION : undefined}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          aria-invalid={submitted && !descriptionValid}
        />
      </div>

      {role === 'demo' && <DemoNotice />}
      <ErrorMessage error={create.error} conflict="An incident with this ID already exists." />

      <Button type="submit" className="w-full" disabled={create.isPending}>
        Create
      </Button>
    </form>
  )
}