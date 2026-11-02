import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Bot, Check, ChevronDown, Minus, RotateCcw, Send, X } from 'lucide-react'
import { askAnalysisAssistant, getApiError } from '../../services/api'
import { useAssistantAnalysis } from './useAssistantAnalysis'
import type { AnalysisSelection } from './WaveformExplorer'

interface ChatMessage {
  role: 'visitor' | 'assistant'
  text: string
}

const GENERAL_SUGGESTIONS = [
  'How does the ECG screening workflow work?',
  'What file and sampling rate are required?',
  'What does HRV mean?',
]

const ANALYSIS_SUGGESTIONS = [
  'How was this screening summary constructed?',
  'What does the selected HRV value represent?',
  'What do rejected windows mean?',
]

export function AssistantPanel() {
  const { activeAnalysis } = useAssistantAnalysis()
  const [open, setOpen] = useState(false)
  const [minimized, setMinimized] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [failedQuestion, setFailedQuestion] = useState<string | null>(null)
  const panelRef = useRef<HTMLElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const previousAnalysisRef = useRef<string | null>(null)

  const analysisRef = activeAnalysis?.analysisRef
  const selection: AnalysisSelection = activeAnalysis?.selection || {}
  const contextLabel = selection.selectedFeature
    ? `Window ${(selection.windowIndex ?? 0) + 1} · ${selection.selectedFeature.replaceAll('_', ' ')}`
    : selection.peakSample !== undefined
      ? `Window ${(selection.windowIndex ?? 0) + 1} · R-peak at sample ${selection.peakSample}`
      : selection.intervalStartSample !== undefined
        ? `Window ${(selection.windowIndex ?? 0) + 1} · selected interval`
        : selection.windowIndex === undefined ? 'Website help' : `Window ${selection.windowIndex + 1}`
  const suggestions = analysisRef ? ANALYSIS_SUGGESTIONS : GENERAL_SUGGESTIONS

  useEffect(() => {
    const currentRef = analysisRef || null
    if (previousAnalysisRef.current !== null && previousAnalysisRef.current !== currentRef) {
      setMessages([])
      setError(null)
      setFailedQuestion(null)
    }
    previousAnalysisRef.current = currentRef
  }, [analysisRef])

  useEffect(() => {
    if (open && !minimized) inputRef.current?.focus()
  }, [open, minimized])

  function openPanel() {
    setOpen(true)
    setMinimized(false)
  }

  function closePanel() {
    setOpen(false)
    setMinimized(false)
  }

  function clearConversation() {
    setMessages([])
    setQuestion('')
    setError(null)
    setFailedQuestion(null)
    inputRef.current?.focus()
  }

  async function submitQuestion(nextQuestion: string) {
    const trimmed = nextQuestion.trim()
    if (!trimmed || busy) return

    setQuestion('')
    setError(null)
    setFailedQuestion(null)
    setMessages((current) => [...current, { role: 'visitor', text: trimmed }])
    setBusy(true)
    try {
      const response = await askAnalysisAssistant({
        ...(analysisRef ? { analysis_ref: analysisRef } : {}),
        question: trimmed,
        ...(messages.length > 0 && failedQuestion === null
          ? {
              history: messages.slice(-12).map((message) => ({
                role: message.role === 'visitor' ? 'user' : 'assistant',
                content: message.text,
              })),
            }
          : {}),
        ...(analysisRef && selection.windowIndex !== undefined
          ? { window_index: selection.windowIndex }
          : {}),
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
      setFailedQuestion(trimmed)
    } finally {
      setBusy(false)
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void submitQuestion(question)
  }

  return (
    <>
      {!open && (
        <button
          type="button"
          className="assistant-launcher"
          aria-label="Open ECG assistant"
          onClick={openPanel}
        >
          <Bot size={23} />
          <span>Ask the guide</span>
        </button>
      )}
      {open && (
        <aside
          ref={panelRef}
          className={`assistant-shell ${minimized ? 'is-minimized' : ''}`}
          aria-label="ECG assistant"
        >
          <div className="assistant-shell-header">
            <div className="assistant-title">
              <span className="assistant-icon"><Bot size={19} /></span>
              <div>
                <strong>ECG assistant</strong>
                <span>Educational AI assistant</span>
              </div>
            </div>
            <div className="assistant-actions">
              <button type="button" className="assistant-icon-button" aria-label="Clear conversation" onClick={clearConversation} disabled={busy}><RotateCcw size={15} /></button>
              <button type="button" className="assistant-icon-button" aria-label={minimized ? 'Reopen assistant panel' : 'Minimize assistant panel'} onClick={() => setMinimized((value) => !value)}>{minimized ? <ChevronDown size={17} /> : <Minus size={17} />}</button>
              <button type="button" className="assistant-icon-button" aria-label="Close assistant" onClick={closePanel}><X size={17} /></button>
            </div>
          </div>
          {!minimized && (
            <div className="assistant-shell-body">
              <p className="assistant-context">Context: <strong>{contextLabel}</strong></p>
              <p className="assistant-disclosure">
                Questions use the configured assistant provider (local Ollama by default; optional external OpenRouter). Answers use general website information or your authorized saved analysis; chat is not saved.
              </p>
              <div className="assistant-messages" aria-live="polite" aria-label="Conversation">
                {messages.length === 0 && (
                  <p className="assistant-empty">
                    Welcome. Ask about this website, ECG screening, HRV, signal quality, or your saved analysis.
                  </p>
                )}
                {messages.map((message, index) => (
                  <div className={`assistant-message ${message.role}`} key={`${message.role}-${index}`}>
                    <strong>{message.role === 'visitor' ? 'You' : 'Guide'}</strong>
                    <p>{message.text}</p>
                  </div>
                ))}
                {busy && <p className="assistant-loading" role="status">Generating a response…</p>}
              </div>
              <div className="assistant-suggestions" aria-label="Suggested questions">
                {suggestions.map((suggestion) => (
                  <button type="button" key={suggestion} onClick={() => void submitQuestion(suggestion)} disabled={busy}>
                    {suggestion}
                  </button>
                ))}
              </div>
              {error && (
                <div className="assistant-error" role="alert">
                  <span>{error}</span>
                  {failedQuestion && <button type="button" onClick={() => void submitQuestion(failedQuestion)} disabled={busy}><RotateCcw size={13} /> Retry</button>}
                </div>
              )}
              <form className="assistant-form" onSubmit={submit}>
                <label className="sr-only" htmlFor="assistant-question">Ask a question</label>
                <textarea
                  ref={inputRef}
                  id="assistant-question"
                  rows={2}
                  maxLength={1000}
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder={analysisRef ? 'Ask about this saved analysis…' : 'Ask about the website or ECG screening…'}
                  disabled={busy}
                />
                <button type="submit" className="button button-primary" disabled={busy || !question.trim()}>
                  Ask <Send size={15} />
                </button>
              </form>
              <p className="assistant-safety-note"><Check size={12} /> Educational information only. Not diagnosis or treatment advice.</p>
            </div>
          )}
        </aside>
      )}
    </>
  )
}
