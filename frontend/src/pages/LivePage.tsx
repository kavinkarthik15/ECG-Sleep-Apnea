import { Activity, Gauge, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { SectionHeading } from '../components/layout/SectionHeading'
import { getApiError } from '../services/api'
import { analyzeECGSamples } from '../services/api'
import { DEMO_SAMPLE_RATE, DEMO_WINDOW_SAMPLES, buildWaveformPath, loadDemoSignal } from '../services/liveDemo'
import type { WindowResult } from '../types/api'

type DemoStatus = 'Ready' | 'Streaming' | 'Analyzing' | 'Result Available' | 'Stopped' | 'Error'
type DemoSourceState = 'loading' | 'ready' | 'error'

export function LivePage() {
  const [status, setStatus] = useState<DemoStatus>('Ready')
  const [sourceState, setSourceState] = useState<DemoSourceState>('loading')
  const [demoSignal, setDemoSignal] = useState<number[]>([])
  const [waveformSamples, setWaveformSamples] = useState<number[]>([])
  const [receivedSamples, setReceivedSamples] = useState(0)
  const [progress, setProgress] = useState(0)
  const [analysisPending, setAnalysisPending] = useState(false)
  const [isMonitoring, setIsMonitoring] = useState(false)
  const [sourceEnded, setSourceEnded] = useState(false)
  const [playbackSpeed, setPlaybackSpeed] = useState<1 | 10>(1)
  const [completedWindows, setCompletedWindows] = useState<WindowResult[]>([])
  const [selectedWindowIndex, setSelectedWindowIndex] = useState<number | null>(null)
  const [modelVersion, setModelVersion] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<number | null>(null)
  const sourcePositionRef = useRef(0)
  const receivedSamplesRef = useRef(0)
  const nextWindowIndexRef = useRef(0)
  const windowRef = useRef<number[]>([])
  const waveformRef = useRef<number[]>([])
  const monitoringRef = useRef(false)
  const analysisInProgressRef = useRef(false)
  const sessionGenerationRef = useRef(0)

  useEffect(() => {
    void loadDemoSignal()
      .then((signal) => {
        setDemoSignal(signal)
        setSourceState('ready')
        setStatus('Ready')
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'The demo signal could not be loaded.')
        setSourceState('error')
        setStatus('Error')
      })

    return () => {
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current)
      }
    }
  }, [])

  const stopMonitoring = () => {
    monitoringRef.current = false
    setIsMonitoring(false)
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
    setStatus('Stopped')
  }

  const analyzeCurrentWindow = async (buffer: number[], windowIndex: number) => {
    if (analysisInProgressRef.current) return
    analysisInProgressRef.current = true
    setAnalysisPending(true)
    const sessionGeneration = sessionGenerationRef.current
    setStatus('Analyzing')
    try {
      const result = await analyzeECGSamples(buffer, DEMO_SAMPLE_RATE)
      if (sessionGeneration !== sessionGenerationRef.current) return
      const analyzedWindow = result.windows[0]
      if (!analyzedWindow) {
        throw new Error('The analysis service returned no result for the completed ECG window.')
      }
      const completedWindow: WindowResult = {
        ...analyzedWindow,
        window_index: windowIndex,
        start_second: windowIndex * (DEMO_WINDOW_SAMPLES / DEMO_SAMPLE_RATE),
        end_second: (windowIndex + 1) * (DEMO_WINDOW_SAMPLES / DEMO_SAMPLE_RATE),
      }
      setCompletedWindows((windows) => [...windows, completedWindow])
      setSelectedWindowIndex(windowIndex)
      setModelVersion(result.model_version)
      setStatus(monitoringRef.current ? 'Result Available' : 'Stopped')
      setError(null)
    } catch (requestError) {
      if (sessionGeneration !== sessionGenerationRef.current) return
      const apiError = getApiError(requestError)
      setCompletedWindows((windows) => [...windows, {
        window_index: windowIndex,
        start_second: windowIndex * (DEMO_WINDOW_SAMPLES / DEMO_SAMPLE_RATE),
        end_second: (windowIndex + 1) * (DEMO_WINDOW_SAMPLES / DEMO_SAMPLE_RATE),
        status: 'rejected',
        window: {
          duration_seconds: DEMO_WINDOW_SAMPLES / DEMO_SAMPLE_RATE,
          sampling_rate: DEMO_SAMPLE_RATE,
          samples: buffer.length,
        },
        error: apiError,
      }])
      setSelectedWindowIndex(windowIndex)
      setError(apiError.message)
      setStatus('Error')
      monitoringRef.current = false
      setIsMonitoring(false)
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current)
        timerRef.current = null
      }
    } finally {
      if (sessionGeneration === sessionGenerationRef.current) {
        analysisInProgressRef.current = false
        setAnalysisPending(false)
      }
    }
  }

  const resetSession = () => {
    stopMonitoring()
    sessionGenerationRef.current += 1
    sourcePositionRef.current = 0
    setSourceEnded(false)
    receivedSamplesRef.current = 0
    nextWindowIndexRef.current = 0
    windowRef.current = []
    waveformRef.current = []
    analysisInProgressRef.current = false
    setAnalysisPending(false)
    setWaveformSamples([])
    setReceivedSamples(0)
    setProgress(0)
    setCompletedWindows([])
    setSelectedWindowIndex(null)
    setModelVersion(null)
    setError(sourceState === 'error' ? error : null)
    setStatus(sourceState === 'error' ? 'Error' : 'Ready')
  }

  const startMonitoring = () => {
    if (sourceState !== 'ready' || demoSignal.length < DEMO_WINDOW_SAMPLES) return
    if (sourcePositionRef.current >= demoSignal.length || analysisInProgressRef.current || monitoringRef.current) return

    monitoringRef.current = true
    setIsMonitoring(true)
    setError(null)
    setStatus('Streaming')

    timerRef.current = window.setInterval(() => {
      if (analysisInProgressRef.current) return
      const chunkSize = 6 * playbackSpeed
      const samplesAvailable = demoSignal.length - sourcePositionRef.current
      const samplesToRead = Math.min(chunkSize, samplesAvailable)
      const receivedChunk: number[] = []
      let completedBuffer: number[] | null = null
      let completedWindowIndex = -1

      for (let index = 0; index < samplesToRead; index += 1) {
        const sample = demoSignal[sourcePositionRef.current]
        windowRef.current.push(sample)
        receivedChunk.push(sample)
        sourcePositionRef.current += 1
        receivedSamplesRef.current += 1

        if (windowRef.current.length === DEMO_WINDOW_SAMPLES) {
          completedBuffer = windowRef.current
          windowRef.current = []
          completedWindowIndex = nextWindowIndexRef.current
          nextWindowIndexRef.current += 1
          break
        }
      }

      waveformRef.current = [...waveformRef.current, ...receivedChunk].slice(-600)
      setWaveformSamples(waveformRef.current)
      setReceivedSamples(receivedSamplesRef.current)
      setProgress(windowRef.current.length)

      const sourceEnded = sourcePositionRef.current >= demoSignal.length
      if (sourceEnded) {
        monitoringRef.current = false
        setIsMonitoring(false)
        setSourceEnded(true)
        if (timerRef.current !== null) {
          window.clearInterval(timerRef.current)
          timerRef.current = null
        }
        if (!completedBuffer) setStatus('Stopped')
      } else if (!completedBuffer) {
        setStatus('Streaming')
      }

      if (completedBuffer) {
        void analyzeCurrentWindow(completedBuffer, completedWindowIndex)
      }
    }, 60)
  }

  const waveformPath = buildWaveformPath(waveformSamples)
  const latestWindow = completedWindows.find((window) => window.window_index === selectedWindowIndex)
  const displayStatus = sourceState === 'loading' ? 'Loading ECG demo...' : status
  const recordingDurationSeconds = (receivedSamples / DEMO_SAMPLE_RATE).toFixed(1)
  const windowProgressSeconds = (progress / DEMO_SAMPLE_RATE).toFixed(1)
  const strongResult = latestWindow?.result?.label ?? latestWindow?.error?.message ?? (status === 'Analyzing' ? 'Analyzing completed window.' : status === 'Streaming' ? 'Collecting ECG window.' : status === 'Error' ? 'Analysis failed.' : 'Awaiting live analysis.')
  const strongScore = latestWindow?.result?.apnea_class_score
  const formatTime = (seconds: number) => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`

  return (
    <div className="page live-page">
      <SectionHeading
        eyebrow="Live demonstration"
        title="Monitor a replayed ECG stream"
        description="Prepared ECG samples are replayed progressively to simulate a live monitoring session while the frozen model still evaluates the real 60-second analysis window."
      />

      <div className="live-layout">
        <section className="panel live-panel">
          <div className="live-panel-header">
            <div>
              <p className="eyebrow">ECG Stream</p>
              <h2>Prototype Demo Stream</h2>
            </div>
            <span className={`status-pill status-${displayStatus.toLowerCase().replace(/\s+/g, '-')}`}>{displayStatus}</span>
          </div>

          <div className="live-stat-grid">
            <div className="live-stat-card">
              <span>Status</span>
              <strong>{displayStatus}</strong>
            </div>
            <div className="live-stat-card">
              <span>Sampling Rate</span>
              <strong>{DEMO_SAMPLE_RATE} Hz</strong>
            </div>
            <div className="live-stat-card">
              <span>Samples Received</span>
              <strong>{receivedSamples}</strong>
            </div>
            <div className="live-stat-card">
              <span>Recording Duration</span>
              <strong>{recordingDurationSeconds}s</strong>
            </div>
            <div className="live-stat-card">
              <span>Current Window Progress</span>
              <strong>{progress}/{DEMO_WINDOW_SAMPLES}</strong>
            </div>
          </div>

          <div className="live-actions">
            <button className="button button-primary" onClick={startMonitoring} disabled={sourceState !== 'ready' || isMonitoring || analysisPending || status === 'Streaming' || status === 'Analyzing' || status === 'Error' || sourceEnded}>
              Start Monitoring
            </button>
            <button className="button button-secondary" onClick={stopMonitoring} disabled={sourceState !== 'ready' || !isMonitoring}>
              Stop Monitoring
            </button>
            <button className="button button-secondary" onClick={resetSession}>
              <RotateCcw size={16} />Reset Session
            </button>
            <button className="button button-secondary" onClick={() => setPlaybackSpeed(1)} disabled={sourceState !== 'ready' || isMonitoring}>1×</button>
            <button className="button button-secondary" onClick={() => setPlaybackSpeed(10)} disabled={sourceState !== 'ready' || isMonitoring}>10×</button>
          </div>
          {playbackSpeed === 10 && <p className="live-speed-note" role="status">Accelerated Demo — 10×</p>}

          {error && (
            <div className="error-state" role="alert">
              <div className="error-icon"><Activity size={18} /></div>
              <div>
                <strong>Stream error</strong>
                <p>{error}</p>
              </div>
            </div>
          )}

          <div className="live-waveform-panel">
            <div className="live-waveform-header">
              <span>Signal trace</span>
              <span>Prototype Demo Stream</span>
            </div>
            <svg viewBox="0 0 680 180" role="img" aria-label="Live ECG waveform preview">
              <path className="grid-line" d="M0 30H680M0 60H680M0 90H680M0 120H680M0 150H680M34 0V180M110 0V180M186 0V180M262 0V180M338 0V180M414 0V180M490 0V180M566 0V180M642 0V180" />
              <path className="signal-line live-signal-line" d={waveformPath} />
            </svg>
          </div>
        </section>

        <aside className="panel live-result-panel">
          <div className="live-result-header">
            <div>
              <p className="eyebrow">Analysis result</p>
              <h2>{latestWindow ? `Window ${latestWindow.window_index + 1} details` : 'Latest window state'}</h2>
            </div>
            <div className="live-dot-wrap"><span className="live-dot" />{displayStatus}</div>
          </div>

          <div className="result-pill"><Gauge size={16} />{strongResult}</div>

          {latestWindow?.result && <div className="score-card">
              <span>Apnea-class score</span>
              <strong>{strongScore?.toFixed(4)}</strong>
              <small>Threshold: {latestWindow.result.threshold.toFixed(2)}</small>
            </div>}
          {latestWindow && <p className="live-selected-window-time">{formatTime(latestWindow.start_second)} – {formatTime(latestWindow.end_second)}</p>}

          <div className="result-meta-grid">
            <div>
              <span>Window progress</span>
              <strong>{windowProgressSeconds}s</strong>
            </div>
            <div>
              <span>Model</span>
              <strong>{modelVersion ?? 'Pending'}</strong>
            </div>
          </div>

          <div className="live-status-box">
            <div className="live-status-row">
              <span>Playback</span>
              <strong>{receivedSamples} samples</strong>
            </div>
            <div className="live-status-row">
              <span>Buffer state</span>
              <strong>{progress}/{DEMO_WINDOW_SAMPLES}</strong>
            </div>
            <div className="live-status-row">
              <span>Label</span>
              <strong>{strongResult}</strong>
            </div>
          </div>

          <section className="live-window-history" aria-live="polite">
            <h3>Window history</h3>
            {completedWindows.length
              ? completedWindows.map((completedWindow) => (
                <button
                  type="button"
                  key={completedWindow.window_index}
                  className={`live-window-history-item ${completedWindow.window_index === selectedWindowIndex ? 'selected' : ''}`}
                  onClick={() => setSelectedWindowIndex(completedWindow.window_index)}
                  aria-pressed={completedWindow.window_index === selectedWindowIndex}
                >
                  <strong>Window {completedWindow.window_index + 1}</strong>
                  <span>{formatTime(completedWindow.start_second)} – {formatTime(completedWindow.end_second)}</span>
                  <span>{completedWindow.result?.label ?? completedWindow.error?.message ?? 'Analysis unavailable'}</span>
                  {completedWindow.result && <small>Score: {completedWindow.result.apnea_class_score.toFixed(4)}</small>}
                </button>
              ))
              : <span>{error ? 'No completed windows. Resolve the error before continuing.' : status === 'Analyzing' ? 'Analyzing completed window…' : status === 'Streaming' ? 'Collecting ECG window…' : 'No completed windows'}</span>}
          </section>
        </aside>
      </div>
    </div>
  )
}
