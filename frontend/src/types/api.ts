export interface HealthResponse {
  status: string
  model_loaded: boolean
  model_version: string | null
}

export interface ModelInfoResponse {
  model_version: string
  sampling_rate: number
  window_seconds: number
  required_samples: number
  feature_count: number
  threshold: number
  supported_file_types: string[]
}

export interface ApiError {
  status: 'error'
  code: string
  message: string
}

export interface SignalQuality {
  n_rpeaks: number
  n_rr_total: number
  n_rr_valid: number
  rr_valid_ratio: number
}

export interface WindowResult {
  window_index: number
  start_second: number
  end_second: number
  status: 'success' | 'rejected'
  model_version?: string
  window?: { duration_seconds: number; sampling_rate: number; samples: number }
  result?: {
    class: 'A' | 'N'
    label: string
    apnea_class_score: number
    threshold: number
  }
  signal_quality?: SignalQuality
  error?: ApiError
}

export interface RecordingSummary {
  total_windows: number
  valid_windows: number
  rejected_windows: number
  apnea_pattern_windows: number
  normal_pattern_windows: number
  apnea_window_percentage: number
  mean_apnea_class_score: number | null
}

export interface RecordingAnalysisResponse {
  status: string
  model_version: string
  summary: RecordingSummary
  ignored_samples: number
  ignored_seconds: number
  windows: WindowResult[]
}

export interface AnalysisState {
  response: RecordingAnalysisResponse
  fileName: string
  fileSize: number
  samplingRate: number
}