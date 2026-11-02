import { createContext } from 'react'
import type { AssistantAnalysisContextValue } from './assistantAnalysisTypes'

export const AssistantAnalysisContext = createContext<AssistantAnalysisContextValue | null>(null)
