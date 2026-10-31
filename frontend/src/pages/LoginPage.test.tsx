import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { mockApi } from '@/test/mockApi'
import { renderApp } from '@/test/renderApp'

const DEMO = { role: 'demo', demo_analyses_left: 30 }
const ADMIN = { role: 'admin' }
const SIGNED_OUT = { status: 401, body: { detail: 'Invalid or missing API key' } }
const EMPTY_HOME = {
  'GET /analyses?status=pending': { body: [] },
  'GET /incidents': { body: [] },
}
const EXPIRED = 'Your session expired. Sign in again.'

test('demo button leads to the home page', async () => {
  const api = mockApi({ 'POST /auth/demo': { body: DEMO }, 'GET /auth/me': { body: DEMO }, ...EMPTY_HOME })
  const { user } = renderApp('/ui/login')

  await user.click(await screen.findByRole('button', { name: 'Try the demo' }))

  expect(await screen.findByRole('heading', { name: 'Incidents' })).toBeInTheDocument()
  expect(api.calls.map((call) => `${call.method} ${call.path}`)).toContain('POST /auth/demo')
})

test('signed-out visit goes to sign in without the expired message', async () => {
  mockApi({ 'GET /auth/me': SIGNED_OUT })
  renderApp('/ui/')

  expect(await screen.findByRole('button', { name: 'Try the demo' })).toBeInTheDocument()
  expect(screen.queryByText(EXPIRED)).not.toBeInTheDocument()
})

test('expired session shows the message', async () => {
  mockApi({})
  renderApp('/ui/login?expired=1')

  expect(await screen.findByText(EXPIRED)).toBeInTheDocument()
})

test('wrong api key shows an error and right key signs in', async () => {
  const api = mockApi({
    'POST /auth/login': [{ status: 401, body: { detail: 'Invalid API key' } }, { body: ADMIN }],
    'GET /auth/me': { body: ADMIN },
    ...EMPTY_HOME,
  })
  const { user } = renderApp('/ui/login')

  expect(await screen.findByRole('button', { name: 'Try the demo' })).toBeInTheDocument()
  expect(screen.queryByLabelText('API key')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Sign in with API key' }))
  const keyField = screen.getByLabelText('API key')
  expect(keyField).toHaveAttribute('type', 'password')

  await user.type(keyField, 'wrong-key')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  expect(await screen.findByText('That key is not valid.')).toBeInTheDocument()

  await user.clear(keyField)
  await user.type(keyField, 'right-key')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
  expect(await screen.findByRole('heading', { name: 'Incidents' })).toBeInTheDocument()

  const logins = api.calls.filter((call) => call.path === '/auth/login')
  expect(logins.map((call) => call.body)).toEqual([{ api_key: 'wrong-key' }, { api_key: 'right-key' }])
})

test('admin sessions have no demo badge', async () => {
  mockApi({ 'GET /auth/me': { body: ADMIN }, ...EMPTY_HOME })
  renderApp('/ui/')

  expect(await screen.findByRole('heading', { name: 'Incidents' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  expect(screen.queryByText('Demo')).not.toBeInTheDocument()
})

test('demo sessions show a badge and sign out returns to sign in', async () => {
  const api = mockApi({
    'GET /auth/me': { body: DEMO },
    'POST /auth/logout': { body: { message: 'Signed out' } },
    ...EMPTY_HOME,
  })
  const { user } = renderApp('/ui/')

  expect(await screen.findByText('Demo')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Sign out' }))

  expect(await screen.findByRole('button', { name: 'Try the demo' })).toBeInTheDocument()
  expect(screen.queryByText(EXPIRED)).not.toBeInTheDocument()
  expect(api.calls.map((call) => `${call.method} ${call.path}`)).toContain('POST /auth/logout')
})

test('sign in page shows the demo notice and a privacy link', async () => {
  mockApi({})
  renderApp('/ui/login')

  expect(await screen.findByRole('heading', { name: 'Fixwright' })).toBeInTheDocument()
  expect(screen.getByText('No sign-up. Up to 30 demo analyses per day.')).toBeInTheDocument()
  expect(
    screen.getByText(
      'Demo data is public. Do not enter personal or confidential information. Demo data is deleted after 7 days.',
    ),
  ).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Privacy' })).toHaveAttribute('href', '/ui/privacy')
})