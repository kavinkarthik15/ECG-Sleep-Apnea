import { useMemo, useRef, useState } from 'react'
import type { PointerEvent } from 'react'
import { ArrowLeft, ArrowRight, Minus, Plus, RotateCcw } from 'lucide-react'
import type { WaveformPoint, WindowResult } from '../../types/api'

export interface AnalysisSelection {
  windowIndex?: number
  intervalStartSample?: number
  intervalEndSample?: number
  peakSample?: number
  selectedFeature?: string
}

interface WaveformExplorerProps {
  window: WindowResult
  samplingRate: number
  onSelectionChange: (selection: AnalysisSelection) => void
}

const WIDTH = 1000
const HEIGHT = 240
const PADDING = 22
const EMPTY_WAVEFORM: WaveformPoint[] = []

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value))
}

export function WaveformExplorer({
  window,
  samplingRate,
  onSelectionChange,
}: WaveformExplorerProps) {
  const waveform = window.waveform || EMPTY_WAVEFORM
  const sampleCount = window.window?.samples || samplingRate * 60
  const [view, setView] = useState({ start: 0, end: sampleCount - 1 })
  const [selection, setSelection] = useState<{ start: number; end: number } | null>(null)
  const [selectedPeak, setSelectedPeak] = useState<number | null>(null)
  const [draftStart, setDraftStart] = useState('0')
  const [draftEnd, setDraftEnd] = useState(String(sampleCount - 1))
  const dragStart = useRef<number | null>(null)

  const visiblePoints = useMemo(
    () => waveform.filter((point) => point.sample_index >= view.start && point.sample_index <= view.end),
    [view.end, view.start, waveform],
  )
  const bounds = useMemo(() => {
    const values = visiblePoints.map((point) => point.value)
    const minimum = values.length ? Math.min(...values) : 0
    const maximum = values.length ? Math.max(...values) : 1
    return { minimum, range: maximum - minimum || 1 }
  }, [visiblePoints])
  const x = (sample: number) => PADDING + ((sample - view.start) / Math.max(1, view.end - view.start)) * (WIDTH - PADDING * 2)
  const y = (value: number) => HEIGHT - PADDING - ((value - bounds.minimum) / bounds.range) * (HEIGHT - PADDING * 2)
  const path = visiblePoints.map((point) => `${x(point.sample_index).toFixed(1)},${y(point.value).toFixed(1)}`).join(' ')
  const selectedWindowPeaks = window.rpeak_samples || []

  function getSampleFromPointer(event: PointerEvent<SVGSVGElement>) {
    const rectangle = event.currentTarget.getBoundingClientRect()
    const fraction = (event.clientX - rectangle.left) / Math.max(1, rectangle.width)
    const contentFraction = clamp(
      (fraction * WIDTH - PADDING) / (WIDTH - PADDING * 2),
      0,
      1,
    )
    return Math.round(view.start + contentFraction * (view.end - view.start))
  }

  function applySelection(start: number, end: number) {
    const left = clamp(Math.min(start, end), 0, sampleCount - 2)
    const right = clamp(Math.max(start, end), left + 1, sampleCount - 1)
    setSelection({ start: left, end: right })
    setDraftStart(String(left))
    setDraftEnd(String(right))
    setSelectedPeak(null)
    const padding = Math.max(1, Math.round((right - left) * 0.15))
    setView({ start: Math.max(0, left - padding), end: Math.min(sampleCount - 1, right + padding) })
    onSelectionChange({
      windowIndex: window.window_index,
      intervalStartSample: left,
      intervalEndSample: right,
    })
  }

  function pan(direction: -1 | 1) {
    const width = view.end - view.start
    const offset = Math.round(width * 0.65) * direction
    const start = clamp(view.start + offset, 0, Math.max(0, sampleCount - 2))
    const end = clamp(start + width, start + 1, sampleCount - 1)
    setView({ start: end === sampleCount - 1 ? Math.max(0, end - width) : start, end })
  }

  function zoom(factor: number) {
    const center = (view.start + view.end) / 2
    const width = clamp(Math.round((view.end - view.start) * factor), 20, sampleCount - 1)
    const start = clamp(Math.round(center - width / 2), 0, sampleCount - width - 1)
    setView({ start, end: start + width })
  }

  function selectPeak(sample: number) {
    setSelectedPeak(sample)
    setSelection(null)
    onSelectionChange({ windowIndex: window.window_index, peakSample: sample })
  }

  const intervalPosition = selection && {
    left: x(selection.start),
    width: Math.max(1, x(selection.end) - x(selection.start)),
  }

  return (
    <section className="explorer-panel waveform-explorer" aria-labelledby="waveform-heading">
      <div className="explorer-heading">
        <div>
          <p className="eyebrow">Signal inspection</p>
          <h2 id="waveform-heading">ECG waveform</h2>
        </div>
        <span className="explorer-subtitle">Window {window.window_index + 1} · {samplingRate} Hz</span>
      </div>
      {waveform.length === 0 ? (
        <p className="explorer-empty">Waveform detail is unavailable for this saved analysis.</p>
      ) : (
        <>
          <div className="waveform-controls" aria-label="Waveform controls">
            <button type="button" className="icon-button" aria-label="Pan waveform left" onClick={() => pan(-1)} disabled={view.start === 0}><ArrowLeft size={16} /></button>
            <button type="button" className="icon-button" aria-label="Zoom out" onClick={() => zoom(1.7)}><Minus size={16} /></button>
            <button type="button" className="icon-button" aria-label="Zoom in" onClick={() => zoom(0.6)}><Plus size={16} /></button>
            <button type="button" className="icon-button" aria-label="Pan waveform right" onClick={() => pan(1)} disabled={view.end >= sampleCount - 1}><ArrowRight size={16} /></button>
            <button type="button" className="icon-button" aria-label="Reset waveform view" onClick={() => { setView({ start: 0, end: sampleCount - 1 }); setSelection(null); setSelectedPeak(null); onSelectionChange({ windowIndex: window.window_index }) }}><RotateCcw size={15} /></button>
          </div>
          <svg
            className="ecg-waveform"
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            role="img"
            aria-label="Saved ECG waveform envelope. Drag to select a time interval."
            onPointerDown={(event) => { dragStart.current = getSampleFromPointer(event) }}
            onPointerUp={(event) => {
              if (dragStart.current !== null) {
                const end = getSampleFromPointer(event)
                if (Math.abs(end - dragStart.current) > 1) applySelection(dragStart.current, end)
                dragStart.current = null
              }
            }}
          >
            <line x1={PADDING} x2={WIDTH - PADDING} y1={HEIGHT / 2} y2={HEIGHT / 2} className="waveform-baseline" />
            {intervalPosition && <rect x={intervalPosition.left} y={PADDING} width={intervalPosition.width} height={HEIGHT - PADDING * 2} className="waveform-selection" />}
            <polyline points={path} className="waveform-path" />
            {selectedWindowPeaks.filter((sample) => sample >= view.start && sample <= view.end).map((sample) => {
              const nearest = visiblePoints.length
                ? visiblePoints.reduce((best, point) => Math.abs(point.sample_index - sample) < Math.abs(best.sample_index - sample) ? point : best, visiblePoints[0])
                : undefined
              return (
                <circle
                  key={sample}
                  cx={x(sample)}
                  cy={nearest ? y(nearest.value) : HEIGHT / 2}
                  r={selectedPeak === sample ? 5 : 3.5}
                  className={`rpeak-marker ${selectedPeak === sample ? 'selected' : ''}`}
                  role="button"
                  tabIndex={0}
                  aria-label={`Detected R-peak at sample ${sample}, recording time ${(window.start_second + sample / samplingRate).toFixed(2)} seconds`}
                  onClick={() => selectPeak(sample)}
                  onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') selectPeak(sample) }}
                />
              )
            })}
            <text x={PADDING} y={HEIGHT - 3}>{(window.start_second + view.start / samplingRate).toFixed(1)} s</text>
            <text x={WIDTH - PADDING} y={HEIGHT - 3} textAnchor="end">{(window.start_second + view.end / samplingRate).toFixed(1)} s</text>
          </svg>
          <p className="waveform-caption">Min/max envelope of uploaded samples · Raw ECG samples are not retained · Click a marker to inspect an R-peak</p>
          <div className="interval-controls">
            <label>Start sample
              <input aria-label="Interval start sample" type="number" min="0" max={sampleCount - 2} value={draftStart} onChange={(event) => setDraftStart(event.target.value)} />
            </label>
            <label>End sample
              <input aria-label="Interval end sample" type="number" min="1" max={sampleCount - 1} value={draftEnd} onChange={(event) => setDraftEnd(event.target.value)} />
            </label>
            <button
              type="button"
              className="button button-secondary"
              disabled={!Number.isInteger(Number(draftStart)) || !Number.isInteger(Number(draftEnd)) || Number(draftStart) < 0 || Number(draftEnd) >= sampleCount || Number(draftEnd) <= Number(draftStart)}
              onClick={() => applySelection(Number(draftStart), Number(draftEnd))}
            >
              Select interval
            </button>
          </div>
          {selectedPeak !== null && <p className="selection-readout">Selected R-peak: sample {selectedPeak} · recording time {(window.start_second + selectedPeak / samplingRate).toFixed(2)} s · window {window.window_index + 1}</p>}
          {selection && <p className="selection-readout">Selected interval: {(window.start_second + selection.start / samplingRate).toFixed(2)}–{(window.start_second + selection.end / samplingRate).toFixed(2)} s in the recording.</p>}
        </>
      )}
    </section>
  )
}
