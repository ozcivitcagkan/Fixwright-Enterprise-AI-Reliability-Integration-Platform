import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { mockApi } from '@/test/mockApi'
import { renderApp } from '@/test/renderApp'

const ISSUES = 'https://github.com/ozcivitcagkan/Fixwright-Enterprise-AI-Reliability-Integration-Platform/issues'

test('privacy page explains data, retention and the cookie', async () => {
  mockApi({})
  renderApp('/ui/privacy')

  expect(await screen.findByRole('heading', { name: 'Privacy' })).toBeInTheDocument()
  const page = screen.getByRole('main')
  for (const text of ['fixwright_session', '8 hours', '7 days', 'Anthropic', 'Voyage AI', 'Frankfurt']) {
    expect(page).toHaveTextContent(text)
  }
  expect(screen.getByRole('link', { name: 'GitHub issues' })).toHaveAttribute('href', ISSUES)
})

test('privacy page is reachable without a session', async () => {
  const api = mockApi({})
  const { user } = renderApp('/ui/login')

  await user.click(await screen.findByRole('link', { name: 'Privacy' }))
  expect(await screen.findByRole('heading', { name: 'Privacy' })).toBeInTheDocument()

  await user.click(screen.getByRole('link', { name: 'Back to sign in' }))
  expect(await screen.findByRole('button', { name: 'Try the demo' })).toBeInTheDocument()
  expect(api.calls).toEqual([])
})