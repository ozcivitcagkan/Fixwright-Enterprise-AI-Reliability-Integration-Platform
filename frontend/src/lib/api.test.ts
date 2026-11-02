import { expect, test, vi } from 'vitest'
import { mockApi } from '@/test/mockApi'
import {
  ApiError,
  createIncident,
  getMe,
  incidentPath,
  listIncidents,
  setUnauthorizedHandler,
} from './api'

test('requests send the web header and the cookie', async () => {
  const api = mockApi({ 'GET /incidents': { body: [] } })

  await listIncidents()

  expect(api.calls[0].headers['X-Fixwright-Client']).toBe('web')
  expect(api.calls[0].credentials).toBe('same-origin')
})

test('a request body is sent as JSON', async () => {
  const api = mockApi({ 'POST /incidents': { body: {} } })

  await createIncident('INC-1', 'Disk full')

  expect(api.calls[0].body).toEqual({ incident_id: 'INC-1', description: 'Disk full' })
  expect(api.calls[0].headers['Content-Type']).toBe('application/json')
})

test('errors carry status and detail', async () => {
  mockApi({ 'POST /incidents': { status: 409, body: { detail: 'Incident already exists' } } })

  await expect(createIncident('A', 'b')).rejects.toMatchObject({
    status: 409,
    detail: 'Incident already exists',
  })
})

test('validation errors become one sentence', async () => {
  mockApi({
    'POST /incidents': {
      status: 422,
      body: { detail: [{ msg: 'Field required' }, { msg: 'String should have at least 1 character' }] },
    },
  })

  await expect(createIncident('A', '')).rejects.toMatchObject({
    status: 422,
    detail: 'Field required. String should have at least 1 character',
  })
})

test('unauthorized handler is called on 401', async () => {
  const handler = vi.fn()
  setUnauthorizedHandler(handler)
  mockApi({
    'GET /incidents': { status: 401, body: { detail: 'Invalid or missing API key' } },
    'GET /auth/me': { status: 401, body: { detail: 'Invalid or missing API key' } },
  })

  await expect(listIncidents()).rejects.toBeInstanceOf(ApiError)
  await expect(getMe()).rejects.toBeInstanceOf(ApiError)

  // Only the incidents call means "session expired"; /auth/me just answers "not signed in"
  expect(handler).toHaveBeenCalledTimes(1)
})

test('incident paths are encoded', () => {
  expect(incidentPath('INC 1/#2%')).toBe('/incidents/INC%201%2F%232%25')
})