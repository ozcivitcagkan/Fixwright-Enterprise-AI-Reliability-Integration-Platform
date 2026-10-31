import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { DemoNotice } from '@/components/DemoNotice'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError, signInAdmin, signInDemo, type Me } from '@/lib/api'

function errorText(error: Error) {
  if (error instanceof ApiError && error.status === 401) return 'That key is not valid.'
  if (error instanceof ApiError) return error.detail
  return 'Fixwright cannot be reached right now. Try again in a minute.'
}

export function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const [showKey, setShowKey] = useState(false)
  const [apiKey, setApiKey] = useState('')

  // The sign-in answer already says who is signed in; storing it keeps the session guard from
  // acting on an older "signed out" answer
  function enter(me: Me) {
    queryClient.setQueryData(['me'], me)
    void navigate('/')
  }

  const demo = useMutation({ mutationFn: signInDemo, onSuccess: enter })
  const admin = useMutation({ mutationFn: signInAdmin, onSuccess: enter })
  const busy = demo.isPending || admin.isPending
  const error = admin.error ?? demo.error

  return (
    <main className="mx-auto flex min-h-svh max-w-sm flex-col justify-center gap-6 px-4 py-10">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold">Fixwright</h1>
        <p className="text-muted-foreground">AI incident analysis with a human decision on every result.</p>
      </div>

      {searchParams.get('expired') === '1' && (
        <Alert>
          <AlertDescription>Your session expired. Sign in again.</AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <Button size="lg" className="w-full" disabled={busy} onClick={() => demo.mutate()}>
          Try the demo
        </Button>
        <p className="text-center text-sm text-muted-foreground">No sign-up. Up to 30 demo analyses per day.</p>
      </div>

      <DemoNotice />

      {showKey ? (
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault()
            admin.mutate(apiKey)
          }}
        >
          <Label htmlFor="api-key">API key</Label>
          <Input
            id="api-key"
            type="password"
            autoComplete="current-password"
            required
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
          />
          <Button type="submit" variant="outline" className="w-full" disabled={busy}>
            Sign in
          </Button>
        </form>
      ) : (
        <Button variant="link" onClick={() => setShowKey(true)}>
          Sign in with API key
        </Button>
      )}

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {errorText(error)}
        </p>
      )}

      <Link to="/privacy" className="text-center text-sm text-muted-foreground underline-offset-4 hover:underline">
        Privacy
      </Link>
    </main>
  )
}