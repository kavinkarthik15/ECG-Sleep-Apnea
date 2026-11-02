import { useContext } from 'react'
import { AssistantAnalysisContext } from './AssistantAnalysisContext'

export function useAssistantAnalysis() {
  const context = useContext(AssistantAnalysisContext)
  if (!context) {
    throw new Error('useAssistantAnalysis must be used inside AssistantAnalysisProvider.')
  }
  return context
}
