import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { AssistantAnalysisContext } from './AssistantAnalysisContext'
import type { ActiveAssistantAnalysis } from './assistantAnalysisTypes'

export function AssistantAnalysisProvider({ children }: { children: ReactNode }) {
  const [activeAnalysis, updateActiveAnalysis] = useState<ActiveAssistantAnalysis | null>(null)
  const setActiveAnalysis = useCallback((analysis: ActiveAssistantAnalysis | null) => {
    updateActiveAnalysis(analysis)
  }, [])
  const value = useMemo(
    () => ({ activeAnalysis, setActiveAnalysis }),
    [activeAnalysis, setActiveAnalysis],
  )

  return (
    <AssistantAnalysisContext.Provider value={value}>
      {children}
    </AssistantAnalysisContext.Provider>
  )
}
