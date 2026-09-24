import { AlertTriangle, Clock3, Gauge, HeartPulse } from 'lucide-react'
import { Badge } from '../common/Badge'
import type { WindowResult } from '../../types/api'

function formatTime(seconds: number) { const minutes = Math.floor(seconds / 60); const remainder = seconds % 60; return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}` }

export function WindowDetails({ window }: { window?: WindowResult }) {
  if (!window) return <aside className="detail-panel empty-detail"><CirclePlaceholder /><p>Select a timeline window to inspect its result.</p></aside>
  const rejected = window.status === 'rejected'
  return <aside className={`detail-panel ${rejected ? 'detail-rejected' : ''}`}><div className="detail-top"><div><p className="eyebrow">Selected window</p><h2>Window {window.window_index + 1}</h2></div><Badge tone={rejected ? 'red' : window.result?.class === 'A' ? 'amber' : 'green'}>{rejected ? 'Rejected' : window.result?.class === 'A' ? 'Class A' : 'Class N'}</Badge></div><div className="time-range"><Clock3 size={15} />{formatTime(window.start_second)} – {formatTime(window.end_second)}</div>{rejected ? <div className="rejection-copy"><AlertTriangle size={20} /><strong>Unable to analyze this window</strong><p>{window.error?.message || 'The backend rejected this window.'}</p></div> : <><div className="result-callout"><span>{window.result?.label}</span><strong>{window.result?.apnea_class_score.toFixed(4)}</strong><small>Apnea-Class Score</small></div><div className="detail-row"><span><Gauge size={15} />Classification threshold</span><b>{window.result?.threshold.toFixed(2)}</b></div><div className="quality-title"><HeartPulse size={16} />Signal quality</div><div className="quality-grid"><div><b>{window.signal_quality?.n_rpeaks}</b><span>R-peaks</span></div><div><b>{window.signal_quality?.n_rr_total}</b><span>Total RR</span></div><div><b>{window.signal_quality?.n_rr_valid}</b><span>Valid RR</span></div><div><b>{((window.signal_quality?.rr_valid_ratio || 0) * 100).toFixed(0)}%</b><span>RR validity</span></div></div></>}</aside>
}

function CirclePlaceholder() { return <div className="detail-placeholder"><HeartPulse size={22} /></div> }