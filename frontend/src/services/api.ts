import axios from 'axios'
import type { ApiError, HealthResponse, ModelInfoResponse, RecordingAnalysisResponse } from '../types/api'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  timeout: 120_000,
})

export function getApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Partial<ApiError> | undefined
    if (data?.message && data.code) {
      return { status: 'error', code: data.code, message: data.message }
    }
    if (!error.response) {
      return { status: 'error', code: 'NETWORK_ERROR', message: 'The analysis service is currently unavailable.' }
    }
    return { status: 'error', code: `HTTP_${error.response.status}`, message: 'The service could not complete this request.' }
  }
  return { status: 'error', code: 'UNKNOWN_ERROR', message: 'Something unexpected happened. Please try again.' }
}

export async function checkHealth(): Promise<HealthResponse> {
  const { data } = await client.get<HealthResponse>('/health')
  return data
}

export async function getModelInfo(): Promise<ModelInfoResponse> {
  const { data } = await client.get<ModelInfoResponse>('/api/v1/model-info')
  return data
}

export async function analyzeECGFile(file: File, samplingRate = 100): Promise<RecordingAnalysisResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('sampling_rate', String(samplingRate))
  const { data } = await client.post<RecordingAnalysisResponse>('/api/v1/analyze-file', formData)
  return data
}

export async function analyzeECGSamples(ecgSamples: number[], samplingRate = 100, includeFeatures = false): Promise<RecordingAnalysisResponse> {
  const { data } = await client.post<RecordingAnalysisResponse>('/api/v1/analyze-samples', { sampling_rate: samplingRate, ecg_samples: ecgSamples, include_features: includeFeatures })
  return data
}