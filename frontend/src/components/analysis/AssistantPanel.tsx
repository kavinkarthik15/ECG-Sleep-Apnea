import { useState } from 'react'
import type { FormEvent } from 'react'
import { Bot, Send } from 'lucide-react'
import { askAnalysisAssistant, getApiError } from '../../services/api'
import type { AnalysisSelection } from './WaveformExplorer'

interface AssistantPanelProps {
  analysisRef?: string
  selection: AnalysisSelection
}

interface ChatMessage {
  role: 'visitor' | 'assistant'
  text: string
}

export function AssistantPanel({ analysisRef, selection }: AssistantPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = question.trim()
    if (!analysisRef || !trimmed || busy) return

    setQuestion('')
    setError(null)
    setMessages((current) => [...current, { role: 'visitor', text: trimmed }])
    setBusy(true)
    try {
      const response = await askAnalysisAssistant({
        analysis_ref: analysisRef,
        question: trimmed,
        ...(selection.windowIndex === undefined ? {} : { window_index: selection.windowIndex }),
        ...(selection.intervalStartSample === undefined ? {} : {
          interval_start_sample: selection.intervalStartSample,
          interval_end_sample: selection.intervalEndSample,
        }),
        ...(selection.peakSample === undefined ? {} : { peak_sample: selection.peakSample }),
        ...(selection.selectedFeature === undefined ? {} : { selected_feature: selection.selectedFeature }),
      })
      setMessages((current) => [...current, { role: 'assistant', text: response.reply }])
    } catch (requestError) {
      setError(getApiError(requestError).message)
    } finally {
      setBusy(false)
    }
  }

  const contextLabel = selection.selectedFeature
    ? `Window ${(selection.windowIndex ?? 0) + 1} · ${selection.selectedFeature.replaceAll('_', ' ')}`
    : selection.peakSample !== undefined
      ? `Window ${(selection.windowIndex ?? 0) + 1} · R-peak at sample ${selection.peakSample}`
      : selection.intervalStartSample !== undefined
        ? `Window ${(selection.windowIndex ?? 0) + 1} · selected interval`
        : selection.windowIndex === undefined ? 'Whole analysis' : `Window ${selection.windowIndex + 1}`

  return (
    <section className="explorer-panel assistant-panel" aria-labelledby="assistant-heading">
      <div className="explorer-heading">
        <div>
          <p className="eyebrow">Context-aware guide</p>
          <h2 id="assistant-heading"><Bot size={23} /> Ask about this analysis</h2>
        </div>
        <span className="local-guide-badge">Local · no external AI</span>
      </div>
      <p className="assistant-context">Current context: <strong>{contextLabel}</strong></p>
      <p className="assistant-disclosure">
        This is a local rule-based guide, not a generative AI model. It uses only the visitor-owned saved analysis and the current selection. Chat text stays in page memory and is not saved.
      </p>
      <div className="assistant-messages" aria-live="polite" aria-label="Conversation">
        {messages.length === 0 && <p className="assistant-empty">Ask about saved HRV values, R-peaks, signal quality, a selected waveform interval, or the screening summary.</p>}
        {messages.map((message, index) => (
          <div className={`assistant-message ${message.role}`} key={`${message.role}-${index}`}>
            <strong>{message.role === 'visitor' ? 'You' : 'Guide'}</strong>
            <p>{message.text}</p>
          </div>
        ))}
        {busy && <p className="assistant-loading" role="status">Checking the authorized saved context…</p>}
      </div>
      {error && <p className="assistant-error" role="alert">{error}</p>}
      <form className="assistant-form" onSubmit={submit}>
        <label className="sr-only" htmlFor="assistant-question">Ask a question about this analysis</label>
        <textarea
          id="assistant-question"
          rows={2}
          maxLength={1000}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="For example: What does the selected RMSSD value represent?"
          disabled={busy || !analysisRef}
        />
        <button type="submit" className="button button-primary" disabled={busy || !question.trim() || !analysisRef}>
          Ask <Send size={15} />
        </button>
      </form>
      <p className="assistant-safety-note">Educational screening information only. Not a diagnosis or treatment advice.</p>
    </section>
  )
}
