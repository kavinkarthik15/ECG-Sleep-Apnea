import { ArrowLeft, Download, Info } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { AnalysisDisclaimer } from '../components/analysis/AnalysisDisclaimer'
import { AnalysisSummary } from '../components/analysis/AnalysisSummary'
import { WindowDetails } from '../components/analysis/WindowDetails'
import { WindowTimeline } from '../components/analysis/WindowTimeline'
import { Badge } from '../components/common/Badge'
import type { AnalysisState } from '../types/api'

export function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const analysis = location.state as AnalysisState | null
  const [selected, setSelected] = useState(0)
  const selectedWindow = useMemo(() => analysis?.response.windows.find((window) => window.window_index === selected), [analysis, selected])
  if (!analysis) return <div className="page centered-empty"><div className="empty-illustration"><Info size={25} /></div><h1>No analysis to show</h1><p>Analysis results are kept in the current session and are not persisted in the browser.</p><Link to="/analyze" className="button button-primary">Analyze an ECG</Link></div>
  const { response, fileName, fileSize } = analysis
  return <div className="page results-page"><div className="results-heading"><div><Link className="back-link" to="/analyze"><ArrowLeft size={15} /> New analysis</Link><p className="eyebrow">Recording analysis</p><h1>{fileName}</h1><p className="results-meta">{(fileSize / 1024).toFixed(1)} KB <span /> 100 Hz <span /> {response.model_version}</p></div><Badge tone="green">Analysis complete</Badge></div><AnalysisSummary summary={response.summary} /><div className="result-callout-wide"><div><strong>{response.summary.apnea_pattern_windows > 0 ? `Apnea-related patterns detected in ${response.summary.apnea_pattern_windows} of ${response.summary.valid_windows} successfully analyzed windows.` : 'No apnea-related patterns were detected by the model in the successfully analyzed windows.'}</strong><p>These are model-estimated window patterns, not a clinical diagnosis.</p></div><div className="mean-score"><span>Mean apnea-class score</span><b>{response.summary.mean_apnea_class_score === null ? '—' : response.summary.mean_apnea_class_score.toFixed(4)}</b></div></div><div className="results-grid"><div><WindowTimeline windows={response.windows} selected={selected} onSelect={setSelected} />{response.ignored_samples > 0 && <p className="ignored-note"><Info size={15} /> {response.ignored_samples} trailing samples ({response.ignored_seconds.toFixed(1)} s) were not analyzed because they did not form a complete window.</p>}</div><WindowDetails window={selectedWindow} /></div><AnalysisDisclaimer /><button className="text-link export-link" onClick={() => navigate('/analyze')}><Download size={15} /> Return to upload</button></div>
}