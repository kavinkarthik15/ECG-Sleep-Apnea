import { Activity } from 'lucide-react'
import type { WindowResult } from '../../types/api'

const FEATURES = [
  { key: 'mean_rr', label: 'Mean RR', unit: 'ms', description: 'Arithmetic mean of valid RR intervals.' },
  { key: 'median_rr', label: 'Median RR', unit: 'ms', description: 'Median of valid RR intervals.' },
  { key: 'mean_hr', label: 'Mean heart rate', unit: 'bpm', description: 'Mean of rates calculated from valid RR intervals.' },
  { key: 'min_hr', label: 'Minimum heart rate', unit: 'bpm', description: 'Minimum rate calculated from valid RR intervals.' },
  { key: 'max_hr', label: 'Maximum heart rate', unit: 'bpm', description: 'Maximum rate calculated from valid RR intervals.' },
  { key: 'sdnn', label: 'SDNN', unit: 'ms', description: 'Sample standard deviation of valid RR intervals.' },
  { key: 'rmssd', label: 'RMSSD', unit: 'ms', description: 'Root mean square of valid successive RR differences.' },
  { key: 'pnn50', label: 'pNN50', unit: '%', description: 'Percentage of valid successive RR differences over 50 ms.' },
  { key: 'rr_range', label: 'RR range', unit: 'ms', description: 'Largest minus smallest valid RR interval.' },
  { key: 'rr_cv', label: 'RR coefficient of variation', unit: 'ratio', description: 'SDNN divided by mean RR.' },
  { key: 'mean_abs_rr_diff', label: 'Mean absolute RR difference', unit: 'ms', description: 'Mean absolute valid successive RR difference.' },
  { key: 'std_rr_diff', label: 'RR-difference standard deviation', unit: 'ms', description: 'Sample standard deviation of valid successive RR differences.' },
  { key: 'hr_std', label: 'Heart-rate standard deviation', unit: 'bpm', description: 'Sample standard deviation of rates calculated from valid RR intervals.' },
] as const

interface HrvExplorerProps {
  window: WindowResult
  onSelectFeature: (feature: string) => void
  selectedFeature?: string
}

export function HrvExplorer({ window, onSelectFeature, selectedFeature }: HrvExplorerProps) {
  const available = window.status === 'success' ? window.features : undefined
  return (
    <section className="explorer-panel" aria-labelledby="hrv-heading">
      <div className="explorer-heading">
        <div>
          <p className="eyebrow">Measured features</p>
          <h2 id="hrv-heading">HRV feature explorer</h2>
        </div>
        <span className="explorer-subtitle">Window {window.window_index + 1}</span>
      </div>
      <p className="explorer-intro">
        Values below are the saved output of the existing feature pipeline. Select a metric to discuss it with the local guide.
      </p>
      {!available && (
        <p className="explorer-empty">
          {window.status === 'rejected'
            ? 'Features are unavailable because this window was rejected.'
            : 'HRV features were not included in this saved analysis.'}
        </p>
      )}
      <div className="hrv-grid">
        {FEATURES.map((feature) => {
          const value = available?.[feature.key]
          const isAvailable = typeof value === 'number' && Number.isFinite(value)
          return (
            <button
              type="button"
              key={feature.key}
              className={`hrv-card ${selectedFeature === feature.key ? 'selected' : ''}`}
              disabled={!isAvailable}
              onClick={() => onSelectFeature(feature.key)}
              aria-pressed={selectedFeature === feature.key}
              aria-label={`${feature.label}: ${isAvailable ? `${String(value)} ${feature.unit}` : 'unavailable'}. Ask about ${feature.label}.`}
            >
              <span className="hrv-card-icon"><Activity size={15} /></span>
              <strong>{feature.label}</strong>
              <b>{isAvailable ? `${String(value)} ${feature.unit}` : 'Unavailable'}</b>
              <small>{isAvailable ? feature.description : 'No saved measurement for this window.'}</small>
            </button>
          )
        })}
      </div>
      {window.signal_quality && (
        <p className="explorer-quality-note">
          Feature availability is shown alongside signal quality: {window.signal_quality.n_rr_valid} of {window.signal_quality.n_rr_total} RR intervals were valid ({(window.signal_quality.rr_valid_ratio * 100).toFixed(1)}%).
        </p>
      )}
    </section>
  )
}
