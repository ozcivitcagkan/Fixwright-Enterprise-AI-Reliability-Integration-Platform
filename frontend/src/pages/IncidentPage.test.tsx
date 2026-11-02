import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { mockApi } from '@/test/mockApi'
import { renderApp } from '@/test/renderApp'

const ADMIN = { role: 'admin' }
const DEMO = { role: 'demo', demo_analyses_left: 27 }
const INCIDENT = { id: 1, incident_id: 'INC-1', description: 'Salary batch did not finish', latest_status: null }

function hoursAgo(hours: number) {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString()
}

function analysis(status: 'pending' | 'approved' | 'rejected', changes: Record<string, unknown> = {}) {
  const decided = status !== 'pending'
  return {
    thread_id: 't-1',
    status,
    analysis: {
      probable_cause: 'The database disk was full',
      suggested_steps: ['Free disk space', 'Restart the batch'],
      evidence: ['Disk usage reached 100% at 02:00'],
    },
    similar_incidents: [],
    reviewer_comment: null,
    requested_by: 'admin',
    decided_by: decided ? 'admin' : null,
    created_at: hoursAgo(3),
    reviewed_at: decided ? hoursAgo(1) : null,
    ...changes,
  }
}

type Routes = Parameters<typeof mockApi>[0]

// The incident page asks who is signed in, the incident and its analyses (newest first)
function incidentApi(analyses: Routes[string], routes: Routes = {}) {
  return mockApi({
    'GET /auth/me': { body: ADMIN },
    'GET /incidents/INC-1': { body: INCIDENT },
    'GET /incidents/INC-1/analyses': analyses,
    ...routes,
  })
}

function callsTo(api: ReturnType<typeof mockApi>, method: string, path: string) {
  return api.calls.filter((call) => call.method === method && call.path === path)
}

test('no analysis shows only Analyze and the demo allowance', async () => {
  incidentApi({ body: [] }, { 'GET /auth/me': { body: DEMO } })
  renderApp('/ui/incidents/INC-1')

  expect(await screen.findByRole('button', { name: 'Analyze' })).toBeInTheDocument()
  expect(screen.getByText('27 analyses left today')).toBeInTheDocument()
  expect(screen.getByText('Salary batch did not finish')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  expect(screen.queryByText(/Earlier analyses/)).not.toBeInTheDocument()
})

test('analyze button sends one request when clicked twice', async () => {
  let finish: () => void = () => {}
  const hold = new Promise<void>((resolve) => {
    finish = () => resolve()
  })
  const api = incidentApi([{ body: [] }, { body: [analysis('pending')] }], {
    'POST /incidents/INC-1/analyze': { body: { thread_id: 't-1', status: 'pending_approval' }, hold },
  })
  const { user } = renderApp('/ui/incidents/INC-1')

  await user.dblClick(await screen.findByRole('button', { name: 'Analyze' }))

  const running = await screen.findByRole('button', { name: 'Analyzing… this takes 10 to 30 seconds' })
  expect(running).toBeDisabled()
  finish()

  expect(await screen.findByRole('button', { name: 'Approve' })).toBeInTheDocument()
  expect(callsTo(api, 'POST', '/incidents/INC-1/analyze')).toHaveLength(1)
})

test('pending shows the analysis, similar incident labels and the decision buttons', async () => {
  incidentApi({
    body: [
      analysis('pending', {
        similar_incidents: [
          { incident_id: 'INC-2', similarity: 0.72, has_approved_analysis: true },
          { incident_id: 'INC-3', similarity: 0.5, has_approved_analysis: false },
        ],
      }),
    ],
  })
  renderApp('/ui/incidents/INC-1')

  expect(await screen.findByText('The database disk was full')).toBeInTheDocument()
  expect(screen.getByText('Restart the batch')).toBeInTheDocument()
  expect(screen.getByText('Disk usage reached 100% at 02:00')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'INC-2' })).toHaveAttribute('href', '/ui/incidents/INC-2')
  expect(screen.getByText('Strong match')).toBeInTheDocument()
  expect(screen.getByText('Possible match')).toBeInTheDocument()
  expect(screen.getAllByText('approved analysis')).toHaveLength(1)
  expect(screen.queryByText(/0\.72|0\.5/)).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Analyze' })).not.toBeInTheDocument()
})

test('comment is hidden until Add a comment and is sent with the decision', async () => {
  const api = incidentApi(
    [{ body: [analysis('pending')] }, { body: [analysis('approved', { reviewer_comment: 'Checked the disk' })] }],
    { 'POST /analyses/t-1/decision': { body: { thread_id: 't-1', status: 'approved' } } },
  )
  const { user } = renderApp('/ui/incidents/INC-1')

  expect(await screen.findByRole('button', { name: 'Approve' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Comment')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Add a comment' }))
  await user.type(screen.getByLabelText('Comment'), 'Checked the disk')
  await user.click(screen.getByRole('button', { name: 'Approve' }))

  expect(await screen.findByRole('button', { name: 'Analyze again' })).toBeInTheDocument()
  expect(callsTo(api, 'POST', '/analyses/t-1/decision').map((call) => call.body)).toEqual([
    { approved: true, comment: 'Checked the disk' },
  ])
})

test('decided shows the result and Analyze again only', async () => {
  incidentApi({ body: [analysis('approved', { reviewer_comment: 'Disk cleaned' })] })
  renderApp('/ui/incidents/INC-1')

  expect(await screen.findByRole('button', { name: 'Analyze again' })).toBeInTheDocument()
  expect(screen.getByText('Approved')).toBeInTheDocument()
  expect(screen.getByText('The database disk was full')).toBeInTheDocument()
  expect(screen.getByText('Decided by admin 1 hour ago')).toBeInTheDocument()
  expect(screen.getByText('Disk cleaned')).toBeInTheDocument()
  expect(screen.queryByText('Restart the batch')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Analyze' })).not.toBeInTheDocument()
})

test('already decided elsewhere shows the message', async () => {
  incidentApi([{ body: [analysis('pending')] }, { body: [analysis('approved', { decided_by: 'api' })] }], {
    'POST /analyses/t-1/decision': { status: 409, body: { detail: 'Analysis already decided' } },
  })
  const { user } = renderApp('/ui/incidents/INC-1')

  await user.click(await screen.findByRole('button', { name: 'Reject' }))

  expect(await screen.findByText('This analysis was already decided.')).toBeInTheDocument()
  expect(await screen.findByText('Decided by api 1 hour ago')).toBeInTheDocument()
})

test('demo limit message on analyze', async () => {
  incidentApi(
    { body: [] },
    {
      'GET /auth/me': { body: { role: 'demo', demo_analyses_left: 0 } },
      'POST /incidents/INC-1/analyze': { status: 429, body: { detail: 'Daily demo limit reached' } },
    },
  )
  const { user } = renderApp('/ui/incidents/INC-1')

  await user.click(await screen.findByRole('button', { name: 'Analyze' }))

  expect(await screen.findByText("Today's demo limit is reached. Try again tomorrow.")).toBeInTheDocument()
})

test('decision after session expiry goes to sign in', async () => {
  incidentApi(
    { body: [analysis('pending')] },
    { 'POST /analyses/t-1/decision': { status: 401, body: { detail: 'Invalid or missing API key' } } },
  )
  const { user } = renderApp('/ui/incidents/INC-1')

  await user.click(await screen.findByRole('button', { name: 'Approve' }))

  expect(await screen.findByText('Your session expired. Sign in again.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Try the demo' })).toBeInTheDocument()
})

test('html in a description is shown as text', async () => {
  const hostile = '<img src=x onerror=alert(1)>'
  mockApi({
    'GET /auth/me': { body: ADMIN },
    'GET /incidents/INC-1': { body: { ...INCIDENT, description: hostile } },
    'GET /incidents/INC-1/analyses': { body: [] },
  })
  renderApp('/ui/incidents/INC-1')

  expect(await screen.findByText(hostile)).toBeInTheDocument()
  expect(document.querySelector('img')).toBeNull()
})

test('earlier analyses are collapsed', async () => {
  const older = (status: 'approved' | 'rejected', cause: string, threadId: string) =>
    analysis(status, { thread_id: threadId, analysis: { probable_cause: cause, suggested_steps: [], evidence: [] } })
  incidentApi({
    body: [
      analysis('pending', { thread_id: 't-3' }),
      older('rejected', 'A botnet attack', 't-2'),
      older('approved', 'An expired certificate', 't-1'),
    ],
  })
  const { user } = renderApp('/ui/incidents/INC-1')

  const toggle = await screen.findByRole('button', { name: 'Earlier analyses (2)' })
  expect(screen.queryByText('A botnet attack')).not.toBeInTheDocument()

  await user.click(toggle)

  expect(screen.getByText('A botnet attack')).toBeInTheDocument()
  expect(screen.getByText('An expired certificate')).toBeInTheDocument()
})

test('unknown incident shows not found', async () => {
  mockApi({
    'GET /auth/me': { body: ADMIN },
    'GET /incidents/INC-404': { status: 404, body: { detail: 'Incident not found' } },
    'GET /incidents/INC-404/analyses': { status: 404, body: { detail: 'Incident not found' } },
  })
  renderApp('/ui/incidents/INC-404')

  expect(await screen.findByText('Incident not found.')).toBeInTheDocument()
})