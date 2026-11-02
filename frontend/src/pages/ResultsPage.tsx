import { ArrowLeft, Download, Info } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { AnalysisDisclaimer } from '../components/analysis/AnalysisDisclaimer'
import { HrvExplorer } from '../components/analysis/HrvExplorer'
import { ScreeningExplanation } from '../components/analysis/ScreeningExplanation'
import { AnalysisSummary } from '../components/analysis/AnalysisSummary'
import { WindowDetails } from '../components/analysis/WindowDetails'
import { WindowTimeline } from '../components/analysis/WindowTimeline'
import { WaveformExplorer, type AnalysisSelection } from '../components/analysis/WaveformExplorer'
import { Badge } from '../components/common/Badge'
import { getAnalysis, getAnalysisWindow, getApiError, getCurrentAnalysis } from '../services/api'
import type { AnalysisState, AnalysisWindowResponse } from '../types/api'

export function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const analysisRef = new URLSearchParams(location.search).get('analysis')
  const requestKey = `${location.key}:${analysisRef ?? ''}`
  const [loaded, setLoaded] = useState<{ key: string; analysis?: AnalysisState; error?: string } | null>(null)
  const analysis = loaded?.key === requestKey ? loaded.analysis || null : null
  const loading = !loaded || loaded.key !== requestKey
  const loadError = loaded?.key === requestKey ? loaded.error || null : null
  const [selected, setSelected] = useState(0)
  const [selection, setSelection] = useState<AnalysisSelection>({})

  useEffect(() => {
    let active = true
    const request = analysisRef ? getAnalysis(analysisRef) : getCurrentAnalysis()
    request
      .then((response) => {
        if (active) {
          setSelected(0)
          setSelection({})
          setLoaded({ key: requestKey, analysis: { response } })
        }
      })
      .catch((error: unknown) => {
        if (active) setLoaded({ key: requestKey, error: getApiError(error).message })
      })

    return () => { active = false }
  }, [analysisRef, location.key, requestKey])

  const selectedWindow = useMemo(() => analysis?.response.windows.find((window) => window.window_index === selected), [analysis, selected])
  const activeAnalysisRef = analysis?.response.analysis_ref
  const detailKey = `${activeAnalysisRef || ''}:${selected}`
  const [detail, setDetail] = useState<{ key: string; value?: AnalysisWindowResponse; error?: string } | null>(null)
  const selectedWindowDetail = detail?.key === detailKey ? detail.value || null : null
  const detailLoading = Boolean(selectedWindow && activeAnalysisRef && detail?.key !== detailKey)
  const detailError = detail?.key === detailKey ? detail.error || null : null

  useEffect(() => {
    if (!selectedWindow || !activeAnalysisRef) return
    let active = true
    getAnalysisWindow(activeAnalysisRef, selected)
      .then((value) => {
        if (active) setDetail({ key: detailKey, value })
      })
      .catch((error: unknown) => {
        if (active) {
          const apiError = getApiError(error)
          if (apiError.code === 'VISITOR_SESSION_EXPIRED' || apiError.code === 'ANALYSIS_NOT_FOUND') {
            setLoaded({ key: requestKey, error: apiError.message })
          } else {
            setDetail({ key: detailKey, error: apiError.message })
          }
        }
      })
    return () => { active = false }
  }, [activeAnalysisRef, detailKey, requestKey, selected, selectedWindow])

  function selectWindow(windowIndex: number) {
    setSelected(windowIndex)
    setSelection({ windowIndex })
  }
  function selectFeature(feature: string) {
    setSelection({ windowIndex: selected, selectedFeature: feature })
  }
  if (loading) return <div className="page centered-empty" role="status">Loading saved analysis…</div>
  if (!analysis) return <div className="page centered-empty"><div className="empty-illustration"><Info size={25} /></div><h1>No analysis to show</h1><p>{loadError || 'There is no saved analysis in this visitor session.'}</p><Link to="/analyze" className="button button-primary">Analyze an ECG</Link></div>
  const { response, fileName, fileSize } = analysis
  return (
    <div className="page results-page">
      <div className="results-heading">
        <div>
          <Link className="back-link" to="/analyze"><ArrowLeft size={15} /> New analysis</Link>
          <p className="eyebrow">Recording analysis</p>
          <h1>{fileName || 'ECG analysis'}</h1>
          <p className="results-meta">
            {fileSize === undefined ? null : `${(fileSize / 1024).toFixed(1)} KB`}
            {fileSize === undefined ? null : <span />}
            {analysis.samplingRate || response.windows[0]?.window?.sampling_rate || 100} Hz
            <span /> {response.model_version}
          </p>
        </div>
        <Badge tone="green">Analysis complete</Badge>
      </div>
      <AnalysisSummary summary={response.summary} />
      <div className="result-callout-wide">
        <div>
          <strong>{response.summary.apnea_pattern_windows > 0
            ? `Apnea-related patterns detected in ${response.summary.apnea_pattern_windows} of ${response.summary.valid_windows} successfully analyzed windows.`
            : 'No apnea-related patterns were detected by the model in the successfully analyzed windows.'}</strong>
          <p>These are model-estimated window patterns, not a clinical diagnosis.</p>
        </div>
        <div className="mean-score">
          <span>Mean apnea-class score</span>
          <b>{response.summary.mean_apnea_class_score === null ? '—' : response.summary.mean_apnea_class_score.toFixed(4)}</b>
        </div>
      </div>
      <div className="results-grid">
        <div>
          <WindowTimeline windows={response.windows} selected={selected} onSelect={selectWindow} />
          {response.ignored_samples > 0 && (
            <p className="ignored-note"><Info size={15} /> {response.ignored_samples} trailing samples ({response.ignored_seconds.toFixed(1)} s) were not analyzed because they did not form a complete window.</p>
          )}
        </div>
        <WindowDetails window={selectedWindow} />
      </div>
      {selectedWindow && (
        <>
          {selectedWindowDetail ? (
            <WaveformExplorer
              key={`${response.analysis_ref}:${selectedWindow.window_index}`}
              window={selectedWindowDetail.window}
              samplingRate={selectedWindowDetail.sampling_rate}
              onSelectionChange={setSelection}
            />
          ) : detailLoading ? (
            <div className="explorer-panel" role="status">Loading selected waveform window…</div>
          ) : detailError ? (
            <div className="explorer-panel" role="alert">{detailError}</div>
          ) : null}
          <HrvExplorer
            window={selectedWindow}
            selectedFeature={selection.windowIndex === selected ? selection.selectedFeature : undefined}
            onSelectFeature={selectFeature}
          />
        </>
      )}
      <ScreeningExplanation response={response} windows={response.windows} />
      <AnalysisDisclaimer />
      <button className="text-link export-link" onClick={() => navigate('/analyze')}><Download size={15} /> Return to upload</button>
    </div>
  )
}