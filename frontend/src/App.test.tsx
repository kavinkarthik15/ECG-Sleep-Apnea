import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import App from './App'
import { askAnalysisAssistant } from './services/api'

vi.mock('./services/api', () => ({
  ensureVisitorSession: vi.fn().mockResolvedValue(undefined),
  askAnalysisAssistant: vi.fn(),
  getApiError: vi.fn(() => ({ message: 'Assistant unavailable.' })),
  checkHealth: vi.fn().mockResolvedValue({
    status: 'healthy',
    model_loaded: true,
    model_version: 'ecg_apnea_hrv_lr_v2',
  }),
}))

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the overview page shell', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('button', { name: /go to overview/i })).toBeInTheDocument()
    expect(await screen.findByText(/Academic ECG research interface/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /open ecg assistant/i })).toBeInTheDocument()
  })

  it('opens, minimizes, reopens and closes the site-wide assistant', async () => {
    render(
      <MemoryRouter initialEntries={['/analyze']}>
        <App />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: /open ecg assistant/i }))
    expect(screen.getByText('ECG assistant')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /minimize assistant panel/i }))
    expect(screen.getByRole('button', { name: /reopen assistant panel/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /reopen assistant panel/i }))
    fireEvent.click(screen.getByRole('button', { name: /close assistant/i }))
    expect(screen.getByRole('button', { name: /open ecg assistant/i })).toBeInTheDocument()
  })

  it('sends general questions without analysis context and retries failures', async () => {
    vi.mocked(askAnalysisAssistant)
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce({
        status: 'success',
        reply: 'Upload a CSV or TXT file at 100 Hz.',
        context: {
          window_index: null,
          interval_start_sample: null,
          interval_end_sample: null,
          peak_sample: null,
          selected_feature: null,
        },
      })

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: /open ecg assistant/i }))
    fireEvent.change(screen.getByLabelText('Ask a question'), {
      target: { value: 'What file should I upload?' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^ask/i }))
    expect(await screen.findByRole('button', { name: /retry/i })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(await screen.findByText(/upload a csv or txt/i)).toBeInTheDocument()
    expect(vi.mocked(askAnalysisAssistant)).toHaveBeenLastCalledWith({
      question: 'What file should I upload?',
    })
  })
})
