import type { QueryClient } from '@tanstack/react-query'
import { Navigate, type DataRouter, type RouteObject } from 'react-router'
import { RequireSession } from '@/components/RequireSession'
import { setUnauthorizedHandler } from '@/lib/api'
import { HomePage } from '@/pages/HomePage'
import { IncidentPage } from '@/pages/IncidentPage'
import { LoginPage } from '@/pages/LoginPage'

// Paths are written without /ui; the router adds that prefix (basename)
export const routes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    // Every page inside needs a session; RequireSession sends people without one to /login
    element: <RequireSession />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/incidents/:incidentId', element: <IncidentPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]

// A 401 on any request means the session ended: go to sign in with a message, then forget cached data
export function watchSession(router: DataRouter, queryClient: QueryClient) {
  setUnauthorizedHandler(() => {
    void router.navigate('/login?expired=1').then(() => queryClient.clear())
  })
}