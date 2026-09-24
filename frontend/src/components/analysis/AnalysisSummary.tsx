import { BarChart3, CheckCircle2, CircleDashed, Gauge, XCircle } from 'lucide-react'
import type { RecordingSummary } from '../../types/api'

export function AnalysisSummary({ summary }: { summary: RecordingSummary }) {
  const items = [
    ['Total windows', summary.total_windows, CircleDashed, 'neutral'],
    ['Successfully analyzed', summary.valid_windows, CheckCircle2, 'green'],
    ['Rejected windows', summary.rejected_windows, XCircle, 'red'],
    ['Apnea-pattern windows', summary.apnea_pattern_windows, BarChart3, 'amber'],
  ] as const
  return <section className="summary-grid">{items.map(([label, value, Icon, tone]) => <div className="metric-card" key={label}><div className={`metric-icon ${tone}`}><Icon size={18} /></div><span>{label}</span><strong>{value}</strong></div>)}<div className="metric-card score-card"><div className="metric-icon blue"><Gauge size={18} /></div><span>Apnea-pattern window percentage</span><strong>{summary.apnea_window_percentage.toFixed(1)}%</strong><small>of successfully analyzed windows</small></div></section>
}