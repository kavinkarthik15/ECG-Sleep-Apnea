import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ResultsPage } from './ResultsPage'
import { AssistantPanel } from '../components/analysis/AssistantPanel'
import { AssistantAnalysisProvider } from '../components/analysis/AssistantAnalysisProvider'
import {
  askAnalysisAssistant,
  getAnalysis,
  getAnalysisWindow,
  getApiError,
  getCurrentAnalysis,
} from '../services/api'
import type { RecordingAnalysisResponse } from '../types/api'

vi.mock('../services/api', () => ({
  getAnalysis: vi.fn(),
  getAnalysisWindow: vi.fn(),
  askAnalysisAssistant: vi.fn(),
  getApiError: vi.fn(() => ({ message: 'The saved analysis is unavailable.' })),
  getCurrentAnalysis: vi.fn(),
}))

const response: RecordingAnalysisResponse = {
  status: 'success',
  model_version: 'test-model',
  analysis_ref: 'owned-reference',
  summary: {
    total_windows: 0,
    valid_windows: 0,
    rejected_windows: 0,
    apnea_pattern_windows: 0,
    normal_pattern_windows: 0,
    apnea_window_percentage: 0,
    mean_apnea_class_score: null,
  },
  ignored_samples: 0,
  ignored_seconds: 0,
  windows: [],
}

const responseWithWindow: RecordingAnalysisResponse = {
  ...response,
  summary: {
    total_windows: 1,
    valid_windows: 1,
    rejected_windows: 0,
    apnea_pattern_windows: 0,
    normal_pattern_windows: 1,
    apnea_window_percentage: 0,
    mean_apnea_class_score: 0.1,
  },
  windows: [{
    window_index: 0,
    start_second: 0,
    end_second: 60,
    status: 'success',
    window: { duration_seconds: 60, sampling_rate: 100, samples: 6000 },
    result: { class: 'N', label: 'No apnea-related pattern detected', apnea_class_score: 0.1, threshold: 0.5 },
    signal_quality: { n_rpeaks: 20, n_rr_total: 19, n_rr_valid: 19, rr_valid_ratio: 1 },
    features: {
      mean_rr: 750,
      median_rr: 750,
      mean_hr: 80,
      min_hr: 80,
      max_hr: 80,
      sdnn: 0,
      rmssd: 0,
      pnn50: 0,
      rr_range: 0,
      rr_cv: 0,
      mean_abs_rr_diff: 0,
      std_rr_diff: 0,
      hr_std: 0,
    },
    rpeak_samples: [60],
    waveform: [
      { sample_index: 0, value: 0 },
      { sample_index: 60, value: 0.2 },
      { sample_index: 5999, value: -0.1 },
    ],
  }],
}

const metadataResponseWithWindow: RecordingAnalysisResponse = {
  ...responseWithWindow,
  windows: responseWithWindow.windows.map((window) => {
    const metadata = { ...window }
    delete metadata.waveform
    delete metadata.rpeak_samples
    return metadata
  }),
}

const windowDetail = {
  window: responseWithWindow.windows[0],
  sampling_rate: 100,
  window_seconds: 60,
}

function renderResults(entry: {
  pathname: string
  search?: string
  state?: unknown
}) {
  return render(
    <AssistantAnalysisProvider>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/results" element={<ResultsPage />} />
        </Routes>
        <AssistantPanel />
      </MemoryRouter>
    </AssistantAnalysisProvider>,
  )
}

async function openAssistant() {
  fireEvent.click(await screen.findByRole('button', { name: /open ecg assistant/i }))
  expect(await screen.findByText('ECG assistant')).toBeInTheDocument()
}

describe('ResultsPage backend validation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('retrieves a referenced analysis on direct navigation', async () => {
    vi.mocked(getAnalysis).mockResolvedValue(response)

    renderResults({ pathname: '/results', search: '?analysis=owned-reference' })

    expect(screen.getByRole('status')).toHaveTextContent(/loading saved analysis/i)
    expect(await screen.findByText('Analysis complete')).toBeInTheDocument()
    expect(getAnalysis).toHaveBeenCalledWith('owned-reference')
    expect(getCurrentAnalysis).not.toHaveBeenCalled()
  })

  it('retrieves the analysis again after a results page remount (refresh)', async () => {
    vi.mocked(getAnalysis).mockResolvedValue(response)

    const firstRender = renderResults({ pathname: '/results', search: '?analysis=owned-reference' })
    expect(await screen.findByText('Analysis complete')).toBeInTheDocument()
    firstRender.unmount()

    renderResults({ pathname: '/results', search: '?analysis=owned-reference' })
    expect(await screen.findByText('Analysis complete')).toBeInTheDocument()
    expect(getAnalysis).toHaveBeenCalledTimes(2)
  })

  it('shows an empty state instead of stale route state when validation fails', async () => {
    vi.mocked(getAnalysis).mockRejectedValue(new Error('not found'))
    vi.mocked(getApiError).mockReturnValue({
      status: 'error',
      code: 'ANALYSIS_NOT_FOUND',
      message: 'The saved analysis was not found.',
    })
    const staleResponse = {
      ...response,
      summary: { ...response.summary, apnea_pattern_windows: 9, valid_windows: 9 },
    }

    renderResults({
      pathname: '/results',
      search: '?analysis=old-reference',
      state: {
        response: staleResponse,
        fileName: 'stale result',
        fileSize: 1,
        samplingRate: 100,
      },
    })

    expect(await screen.findByRole('heading', { name: /no analysis to show/i })).toBeInTheDocument()
    expect(screen.getByText('The saved analysis was not found.')).toBeInTheDocument()
    expect(screen.queryByText('stale result')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /analyze an ecg/i })).toHaveAttribute('href', '/analyze')
    await waitFor(() => expect(getAnalysis).toHaveBeenCalledWith('old-reference'))
  })

  it('does not display an analysis after the visitor session expires', async () => {
    vi.mocked(getCurrentAnalysis).mockRejectedValue({ response: { status: 401 } })
    vi.mocked(getApiError).mockReturnValue({
      status: 'error',
      code: 'VISITOR_SESSION_EXPIRED',
      message: 'Your visitor session has expired.',
    })

    renderResults({ pathname: '/results' })

    expect(await screen.findByRole('heading', { name: /no analysis to show/i })).toBeInTheDocument()
    expect(screen.getByText('Your visitor session has expired.')).toBeInTheDocument()
    expect(screen.queryByText('Analysis complete')).not.toBeInTheDocument()
    expect(getCurrentAnalysis).toHaveBeenCalledOnce()
  })

  it('sends the selected detected R-peak as lookup context', async () => {
    vi.mocked(getAnalysis).mockResolvedValue(metadataResponseWithWindow)
    vi.mocked(getAnalysisWindow).mockResolvedValue(windowDetail)
    vi.mocked(askAnalysisAssistant).mockResolvedValue({
      status: 'success',
      reply: 'Selected peak is at the saved detector sample.',
      context: {
        window_index: 0,
        interval_start_sample: null,
        interval_end_sample: null,
        peak_sample: 60,
        selected_feature: null,
      },
    })

    renderResults({ pathname: '/results', search: '?analysis=owned-reference' })
    fireEvent.click(await screen.findByRole('button', { name: /detected r-peak at sample 60/i }))
    expect(await screen.findByText(/selected r-peak: sample 60/i)).toBeInTheDocument()
    await openAssistant()

    fireEvent.change(screen.getByLabelText(/ask a question/i), {
      target: { value: 'What time is this R-peak?' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^ask/i }))

    await waitFor(() => expect(askAnalysisAssistant).toHaveBeenCalledWith({
      analysis_ref: 'owned-reference',
      question: 'What time is this R-peak?',
      window_index: 0,
      peak_sample: 60,
    }))
    expect(await screen.findByText('Selected peak is at the saved detector sample.')).toBeInTheDocument()
  })

  it('sends the selected measured HRV feature to the local guide', async () => {
    vi.mocked(getAnalysis).mockResolvedValue(metadataResponseWithWindow)
    vi.mocked(getAnalysisWindow).mockResolvedValue(windowDetail)
    vi.mocked(askAnalysisAssistant).mockResolvedValue({
      status: 'success',
      reply: 'Mean RR is 750 ms.',
      context: {
        window_index: 0,
        interval_start_sample: null,
        interval_end_sample: null,
        peak_sample: null,
        selected_feature: 'mean_rr',
      },
    })

    renderResults({ pathname: '/results', search: '?analysis=owned-reference' })
    fireEvent.click(await screen.findByRole('button', { name: /mean rr: 750 ms/i }))
    await openAssistant()
    fireEvent.change(screen.getByLabelText(/ask a question/i), {
      target: { value: 'Explain this selected feature.' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^ask/i }))

    await waitFor(() => expect(askAnalysisAssistant).toHaveBeenCalledWith({
      analysis_ref: 'owned-reference',
      question: 'Explain this selected feature.',
      window_index: 0,
      selected_feature: 'mean_rr',
    }))
    expect(await screen.findByText('Mean RR is 750 ms.')).toBeInTheDocument()
  })

  it('sends interval sample bounds selected from the waveform', async () => {
    vi.mocked(getAnalysis).mockResolvedValue(metadataResponseWithWindow)
    vi.mocked(getAnalysisWindow).mockResolvedValue(windowDetail)
    vi.mocked(askAnalysisAssistant).mockResolvedValue({
      status: 'success',
      reply: 'The selected interval is grounded in the saved analysis.',
      context: {
        window_index: 0,
        interval_start_sample: 100,
        interval_end_sample: 200,
        peak_sample: null,
        selected_feature: null,
      },
    })

    renderResults({ pathname: '/results', search: '?analysis=owned-reference' })
    await screen.findByRole('heading', { name: 'ECG waveform' })
    fireEvent.change(screen.getByLabelText('Interval start sample'), { target: { value: '100' } })
    fireEvent.change(screen.getByLabelText('Interval end sample'), { target: { value: '200' } })
    fireEvent.click(screen.getByRole('button', { name: 'Select interval' }))
    await openAssistant()
    fireEvent.change(screen.getByLabelText(/ask a question/i), {
      target: { value: 'Explain this selected interval.' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^ask/i }))

    await waitFor(() => expect(askAnalysisAssistant).toHaveBeenCalledWith({
      analysis_ref: 'owned-reference',
      question: 'Explain this selected interval.',
      window_index: 0,
      interval_start_sample: 100,
      interval_end_sample: 200,
    }))
  })

  it('hides results if the selected-window validation finds an expired session', async () => {
    vi.mocked(getAnalysis).mockResolvedValue(metadataResponseWithWindow)
    vi.mocked(getAnalysisWindow).mockRejectedValue({ response: { status: 401 } })
    vi.mocked(getApiError).mockReturnValue({
      status: 'error',
      code: 'VISITOR_SESSION_EXPIRED',
      message: 'Your visitor session has expired.',
    })

    renderResults({ pathname: '/results', search: '?analysis=owned-reference' })

    expect(await screen.findByRole('heading', { name: /no analysis to show/i })).toBeInTheDocument()
    expect(screen.getByText('Your visitor session has expired.')).toBeInTheDocument()
    expect(screen.queryByText('Analysis complete')).not.toBeInTheDocument()
  })
})
