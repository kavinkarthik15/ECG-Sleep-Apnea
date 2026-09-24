import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import App from './App'

vi.mock('./services/api', () => ({
  checkHealth: vi.fn().mockResolvedValue({
    status: 'healthy',
    model_loaded: true,
    model_version: 'ecg_apnea_hrv_lr_v2',
  }),
}))

describe('App', () => {
  it('renders the overview page shell', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('button', { name: /go to overview/i })).toBeInTheDocument()
    expect(await screen.findByText(/Academic ECG research interface/i)).toBeInTheDocument()
  })
})
