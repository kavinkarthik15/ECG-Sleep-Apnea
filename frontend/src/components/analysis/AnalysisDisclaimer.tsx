import { ShieldCheck } from 'lucide-react'

export function AnalysisDisclaimer() {
  return <div className="disclaimer"><ShieldCheck size={18} /><p>This is an academic ECG-based screening prototype. Its output indicates model-estimated apnea-related patterns in ECG windows and is <strong>not a medical diagnosis.</strong></p></div>
}