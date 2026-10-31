import { expect, onTestFinished, vi } from 'vitest'

type Reply = { status?: number; body?: unknown }

export type ApiCall = {
  method: string
  path: string
  headers: Record<string, string>
  credentials: RequestCredentials | undefined
  body: unknown
}

// Stands in for the Fixwright API in tests. Keys look like "GET /incidents" or
// "GET /analyses?status=pending". A list of replies is used in order and the last one repeats.
// A request without a matching key fails the test, so no test reaches a real server.
export function mockApi(routes: Record<string, Reply | Reply[]>) {
  const calls: ApiCall[] = []
  const unmatched: string[] = []
  const used: Record<string, number> = {}

  vi.stubGlobal('fetch', async (path: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET'
    const key = `${method} ${path}`
    calls.push({
      method,
      path,
      headers: (init.headers ?? {}) as Record<string, string>,
      credentials: init.credentials,
      body: typeof init.body === 'string' ? JSON.parse(init.body) : undefined,
    })

    const route = routes[key]
    if (route === undefined) {
      unmatched.push(key)
      throw new Error(`No mock reply for ${key}`)
    }
    const replies = Array.isArray(route) ? route : [route]
    const reply = replies[Math.min(used[key] ?? 0, replies.length - 1)]
    used[key] = (used[key] ?? 0) + 1
    return new Response(JSON.stringify(reply.body ?? null), {
      status: reply.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })

  onTestFinished(() => {
    vi.unstubAllGlobals()
    expect(unmatched, 'requests without a mock reply').toEqual([])
  })

  return { calls }
}