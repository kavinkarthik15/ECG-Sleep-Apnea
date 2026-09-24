import { useState } from 'react'
import { analyzeECGFile, getApiError } from '../services/api'
import type { AnalysisState, ApiError } from '../types/api'

export function useECGAnalysis() {
  const [state, setState] = useState<AnalysisState | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(false)

  async function analyze(file: File) {
    setLoading(true)
    setError(null)
    try {
      const response = await analyzeECGFile(file)
      setState({ response, fileName: file.name, fileSize: file.size, samplingRate: 100 })
      return response
    } catch (requestError) {
      const apiError = getApiError(requestError)
      setError(apiError)
      return null
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setState(null)
    setError(null)
  }

  return { state, error, loading, analyze, reset }
}