import { useQuery } from '@tanstack/react-query'
import { Navigate, Outlet } from 'react-router'
import { TopBar } from '@/components/TopBar'
import { ApiError, getMe } from '@/lib/api'

// Layout for every signed-in page: asks who is signed in, then shows the top bar and the page
export function RequireSession() {
  const me = useQuery({ queryKey: ['me'], queryFn: getMe })

  if (me.data) {
    return (
      <>
        <TopBar me={me.data} />
        <main className="mx-auto max-w-3xl px-4 py-6">
          <Outlet />
        </main>
      </>
    )
  }
  if (me.error instanceof ApiError && me.error.status === 401) return <Navigate to="/login" replace />
  if (me.isError) {
    return <p className="p-6 text-sm text-muted-foreground">Fixwright cannot be reached right now. Try again in a minute.</p>
  }
  return null
}