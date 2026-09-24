import { Activity } from 'lucide-react'

export function LoadingState() {
  return <div className="loading-state" role="status" aria-live="polite"><div className="loading-mark"><Activity size={22} /></div><div><strong>Analyzing ECG recording</strong><p>Processing consecutive 60-second windows. This can take a moment.</p></div><span className="loading-line" /></div>
}