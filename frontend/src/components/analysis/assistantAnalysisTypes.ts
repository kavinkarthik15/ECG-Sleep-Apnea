import type { AnalysisSelection } from './WaveformExplorer'

export interface ActiveAssistantAnalysis {
  analysisRef: string
  selection: AnalysisSelection
}

export interface AssistantAnalysisContextValue {
  activeAnalysis: ActiveAssistantAnalysis | null
  setActiveAnalysis: (analysis: ActiveAssistantAnalysis | null) => void
}
