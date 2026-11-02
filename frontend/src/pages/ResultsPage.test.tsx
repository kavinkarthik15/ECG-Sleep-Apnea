import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ResultsPage } from './ResultsPage'
import {
  getAnalysis,
  getAnalysisWindow,
  getApiError,
  getCurrentAnalysis,
} from '../services/api'
import type { RecordingAnalysisResponse } from '../types/api'

vi.mock('../services/api', () => ({
  getAnalysis: vi.fn(),
  getAnalysisWindow: vi.fn(),
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

function renderResults(entry: {
  pathname: string
  search?: string
  state?: unknown
}) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/results" element={<ResultsPage />} />
      </Routes>
    </MemoryRouter>,
  )
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
