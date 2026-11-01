import { ApiError } from '@/lib/api'

const SOMETHING_WENT_WRONG = 'Something went wrong. Try again.'

// One plain sentence per failure; a 409 means something different on each page, so the caller names it
function errorText(error: Error, conflict: string) {
  if (!(error instanceof ApiError)) return SOMETHING_WENT_WRONG
  if (error.status === 429) return "Today's demo limit is reached. Try again tomorrow."
  if (error.status === 409) return conflict
  if (error.status === 404) return 'Incident not found.'
  return SOMETHING_WENT_WRONG
}

export function ErrorMessage({ error, conflict = SOMETHING_WENT_WRONG }: { error: Error | null; conflict?: string }) {
  if (!error) return null
  return (
    <p role="alert" className="text-sm text-destructive">
      {errorText(error, conflict)}
    </p>
  )
}