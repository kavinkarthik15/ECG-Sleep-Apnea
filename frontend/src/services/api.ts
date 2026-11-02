import axios from 'axios'
import type {
  ApiError,
  AnalysisWindowResponse,
  HealthResponse,
  ModelInfoResponse,
  RecordingAnalysisResponse,
} from '../types/api'

const configuredApiBaseUrl = import.meta.env.PROD
  ? undefined
  : import.meta.env.VITE_API_BASE_URL?.trim()

export function resolveApiBaseUrl(configuredUrl = configuredApiBaseUrl): string {
  if (!configuredUrl) return '/api/v1'
  const normalizedUrl = configuredUrl.replace(/\/+$/, '')
  return normalizedUrl.endsWith('/api/v1')
    ? normalizedUrl
    : `${normalizedUrl}/api/v1`
}

export function resolveApiRootUrl(configuredUrl = configuredApiBaseUrl): string {
  const apiBaseUrl = resolveApiBaseUrl(configuredUrl)
  return apiBaseUrl.endsWith('/api/v1')
    ? apiBaseUrl.slice(0, -'/api/v1'.length) || '/'
    : apiBaseUrl
}

const client = axios.create({
  baseURL: resolveApiBaseUrl(),
  timeout: 120_000,
  withCredentials: true,
})

const healthClient = axios.create({
  baseURL: resolveApiRootUrl(),
  timeout: 120_000,
  withCredentials: true,
})

let sessionInitialization: Promise<void> | null = null

export function ensureVisitorSession(): Promise<void> {
  if (!sessionInitialization) {
    sessionInitialization = client.post('/session')
      .catch((error: unknown) => {
        if (axios.isAxiosError(error) && error.response?.status === 401) {
          return client.post('/session')
        }
        throw error
      })
      .then(() => undefined)
      .finally(() => { sessionInitialization = null })
  }
  return sessionInitialization
}

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
  const { data } = await healthClient.get<HealthResponse>('/health')
  return data
}

export async function getModelInfo(): Promise<ModelInfoResponse> {
  const { data } = await client.get<ModelInfoResponse>('/model-info')
  return data
}

export async function analyzeECGFile(file: File, samplingRate = 100): Promise<RecordingAnalysisResponse> {
  await ensureVisitorSession()
  const formData = new FormData()
  formData.append('file', file)
  formData.append('sampling_rate', String(samplingRate))
  formData.append('include_features', 'true')
  const { data } = await client.post<RecordingAnalysisResponse>('/analyze-file', formData)
  return data
}

export async function analyzeECGSamples(ecgSamples: number[], samplingRate = 100, includeFeatures = true): Promise<RecordingAnalysisResponse> {
  await ensureVisitorSession()
  const { data } = await client.post<RecordingAnalysisResponse>('/analyze-samples', { sampling_rate: samplingRate, ecg_samples: ecgSamples, include_features: includeFeatures })
  return data
}

export async function getCurrentAnalysis(): Promise<RecordingAnalysisResponse> {
  await ensureVisitorSession()
  const { data } = await client.get<RecordingAnalysisResponse>('/session/analysis')
  return data
}

export async function getAnalysis(analysisRef: string): Promise<RecordingAnalysisResponse> {
  await ensureVisitorSession()
  const { data } = await client.get<RecordingAnalysisResponse>(`/analyses/${encodeURIComponent(analysisRef)}`)
  return data
}

export async function getAnalysisWindow(
  analysisRef: string,
  windowIndex: number,
): Promise<AnalysisWindowResponse> {
  await ensureVisitorSession()
  const { data } = await client.get<AnalysisWindowResponse>(
    `/analyses/${encodeURIComponent(analysisRef)}/windows/${windowIndex}`,
  )
  return data
}

export async function endVisitorSession(): Promise<void> {
  await client.delete('/session')
}