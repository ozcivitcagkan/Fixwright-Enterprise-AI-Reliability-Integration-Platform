import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import './index.css'
import { ApiError } from '@/lib/api'
import { routes, watchSession } from './routes'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A 4xx answer (signed out, not found) will not change on a retry; network and server errors get one more try
      retry: (failureCount, error) => !(error instanceof ApiError && error.status < 500) && failureCount < 1,
    },
  },
})
const router = createBrowserRouter(routes, { basename: '/ui' })
watchSession(router, queryClient)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)