import { screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import { mockApi } from '@/test/mockApi'
import { renderApp } from '@/test/renderApp'

const ADMIN = { role: 'admin' }
const DEMO = { role: 'demo', demo_analyses_left: 30 }
const DEMO_NOTICE =
  'Demo data is public. Do not enter personal or confidential information. Demo data is deleted after 7 days.'

function incident(incidentId: string, latestStatus: string | null, id = 1) {
  return { id, incident_id: incidentId, description: `Description of ${incidentId}`, latest_status: latestStatus }
}

// The home page asks the API three things; each test replaces only what it is about
function homeApi(routes: Parameters<typeof mockApi>[0] = {}) {
  return mockApi({
    'GET /auth/me': { body: ADMIN },
    'GET /analyses?status=pending': { body: [] },
    'GET /incidents': { body: [] },
    ...routes,
  })
}

test('pending section appears only when something waits', async () => {
  homeApi({ 'GET /incidents': { body: [incident('INC-1', null)] } })
  renderApp('/ui/')

  expect(await screen.findByText('INC-1')).toBeInTheDocument()
  expect(screen.queryByText('Waiting for your decision')).not.toBeInTheDocument()
})

test('pending card links to the incident', async () => {
  const cause = 'The nightly batch stopped because the database disk was full. '.repeat(4)
  const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString()
  homeApi({
    'GET /analyses?status=pending': {
      body: [
        { thread_id: 't-1', incident_id: 'INC-7', description: 'Batch failed', probable_cause: cause, created_at: twoHoursAgo },
      ],
    },
  })
  renderApp('/ui/')

  expect(await screen.findByRole('heading', { name: 'Waiting for your decision' })).toBeInTheDocument()
  const card = screen.getByRole('link', { name: /INC-7/ })
  expect(card).toHaveAttribute('href', '/ui/incidents/INC-7')
  expect(within(card).getByText(cause.slice(0, 120) + '…')).toBeInTheDocument()
  expect(within(card).getByText('2 hours ago')).toBeInTheDocument()
})

test('incident rows show plain status words', async () => {
  homeApi({
    'GET /incidents': {
      body: [
        incident('INC-1', 'pending', 1),
        incident('INC-2', 'approved', 2),
        incident('INC-3', 'rejected', 3),
        incident('INC 4', null, 4),
      ],
    },
  })
  renderApp('/ui/')

  for (const word of ['Pending', 'Approved', 'Rejected', 'Not analyzed']) {
    expect(await screen.findByText(word)).toBeInTheDocument()
  }
  expect(screen.getByRole('link', { name: /INC 4/ })).toHaveAttribute('href', '/ui/incidents/INC%204')
})

test('new incident is created and opened', async () => {
  const api = homeApi({
    'POST /incidents': { body: { message: 'Incident received', incident_id: 'INC-9', description: 'Disk full' } },
    'GET /incidents/INC-9': { body: incident('INC-9', null, 9) },
    'GET /incidents/INC-9/analyses': { body: [] },
  })
  const { user } = renderApp('/ui/')

  await user.click(await screen.findByRole('button', { name: 'New incident' }))
  const dialog = screen.getByRole('dialog')
  expect(within(dialog).getByLabelText('Description')).not.toHaveAttribute('maxlength')
  expect(within(dialog).queryByText(DEMO_NOTICE)).not.toBeInTheDocument()

  await user.type(within(dialog).getByLabelText('Incident ID'), 'INC-9')
  await user.type(within(dialog).getByLabelText('Description'), 'Disk full')
  await user.click(within(dialog).getByRole('button', { name: 'Create' }))

  expect(await screen.findByRole('heading', { name: 'INC-9' })).toBeInTheDocument()
  const posts = api.calls.filter((call) => call.method === 'POST' && call.path === '/incidents')
  expect(posts.map((call) => call.body)).toEqual([{ incident_id: 'INC-9', description: 'Disk full' }])
})

test('create button shows progress while the incident is saved', async () => {
  let finish: () => void = () => {}
  const hold = new Promise<void>((resolve) => {
    finish = () => resolve()
  })
  homeApi({
    'POST /incidents': { body: { message: 'Incident received', incident_id: 'INC-9', description: 'Disk full' }, hold },
    'GET /incidents/INC-9': { body: incident('INC-9', null, 9) },
    'GET /incidents/INC-9/analyses': { body: [] },
  })
  const { user } = renderApp('/ui/')

  await user.click(await screen.findByRole('button', { name: 'New incident' }))
  const dialog = screen.getByRole('dialog')
  await user.type(within(dialog).getByLabelText('Incident ID'), 'INC-9')
  await user.type(within(dialog).getByLabelText('Description'), 'Disk full')
  await user.click(within(dialog).getByRole('button', { name: 'Create' }))

  expect(await within(dialog).findByRole('button', { name: 'Creating…' })).toBeDisabled()
  finish()

  expect(await screen.findByRole('heading', { name: 'INC-9' })).toBeInTheDocument()
})

test('incident id with a slash is refused', async () => {
  const api = homeApi()
  const { user } = renderApp('/ui/')

  await user.click(await screen.findByRole('button', { name: 'New incident' }))
  const dialog = screen.getByRole('dialog')
  await user.type(within(dialog).getByLabelText('Incident ID'), 'INC/1')
  await user.type(within(dialog).getByLabelText('Description'), 'Disk full')
  await user.click(within(dialog).getByRole('button', { name: 'Create' }))

  expect(within(dialog).getByLabelText('Incident ID')).toHaveAttribute('aria-invalid', 'true')
  expect(within(dialog).getByText('Letters, numbers, dot, dash and underscore')).toBeInTheDocument()
  expect(api.calls.some((call) => call.method === 'POST')).toBe(false)
})

test('existing incident id shows a clear message', async () => {
  homeApi({ 'POST /incidents': { status: 409, body: { detail: 'Incident already exists' } } })
  const { user } = renderApp('/ui/')

  await user.click(await screen.findByRole('button', { name: 'New incident' }))
  const dialog = screen.getByRole('dialog')
  await user.type(within(dialog).getByLabelText('Incident ID'), 'INC-1')
  await user.type(within(dialog).getByLabelText('Description'), 'Disk full')
  await user.click(within(dialog).getByRole('button', { name: 'Create' }))

  expect(await within(dialog).findByText('An incident with this ID already exists.')).toBeInTheDocument()
})

test('demo limit message on create', async () => {
  homeApi({
    'GET /auth/me': { body: DEMO },
    'POST /incidents': { status: 429, body: { detail: 'Daily demo limit reached' } },
  })
  const { user } = renderApp('/ui/')

  await user.click(await screen.findByRole('button', { name: 'New incident' }))
  const dialog = screen.getByRole('dialog')
  await user.type(within(dialog).getByLabelText('Incident ID'), 'INC-1')
  await user.type(within(dialog).getByLabelText('Description'), 'Disk full')
  await user.click(within(dialog).getByRole('button', { name: 'Create' }))

  expect(await within(dialog).findByText("Today's demo limit is reached. Try again tomorrow.")).toBeInTheDocument()
})

test('demo description is limited to 1000 characters', async () => {
  homeApi({ 'GET /auth/me': { body: DEMO } })
  const { user } = renderApp('/ui/')

  await user.click(await screen.findByRole('button', { name: 'New incident' }))
  const dialog = screen.getByRole('dialog')

  expect(within(dialog).getByLabelText('Description')).toHaveAttribute('maxlength', '1000')
  expect(within(dialog).getByText(DEMO_NOTICE)).toBeInTheDocument()
})