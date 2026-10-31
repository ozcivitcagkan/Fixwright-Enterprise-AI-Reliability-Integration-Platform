import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import App from './App'

test('app renders the product name', () => {
  render(<App />)

  expect(screen.getByText('Fixwright')).toBeInTheDocument()
})