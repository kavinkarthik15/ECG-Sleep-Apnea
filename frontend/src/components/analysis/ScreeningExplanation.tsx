import type { RecordingAnalysisResponse, WindowResult } from '../../types/api'

export function ScreeningExplanation({
  response,
  windows,
}: {
  response: RecordingAnalysisResponse
  windows: WindowResult[]
}) {
  const { summary } = response
  return (
    <section className="explorer-panel screening-explanation" aria-labelledby="explanation-heading">
      <p className="eyebrow">How to read this screening</p>
      <h2 id="explanation-heading">What the result represents</h2>
      <p>
        The frozen model maps each accepted 60-second window to class A (apnea-related pattern) or class N (the other model class). Rejected windows are not counted as either class. These are model outputs from an academic screening prototype, not a medical diagnosis.
      </p>
      <div className="explanation-facts">
        <div><strong>{summary.valid_windows} / {summary.total_windows}</strong><span>accepted windows</span></div>
        <div><strong>{summary.rejected_windows}</strong><span>rejected windows</span></div>
        <div><strong>{summary.apnea_window_percentage.toFixed(1)}%</strong><span>accepted windows mapped to class A</span></div>
        <div><strong>{summary.mean_apnea_class_score === null ? 'Unavailable' : summary.mean_apnea_class_score.toFixed(4)}</strong><span>mean score across accepted windows</span></div>
      </div>
      <p className="explanation-method">
        The displayed class-A percentage is calculated as class-A accepted windows divided by all accepted windows, multiplied by 100 (0% when no windows are accepted). The mean score is the arithmetic mean of accepted-window apnea-class scores and is unavailable when there are no accepted windows.
      </p>
      <div className="window-status-list" aria-label="Window acceptance and rejection details">
        {windows.map((window) => (
          <div className={`window-status-row ${window.status}`} key={window.window_index}>
            <strong>Window {window.window_index + 1}</strong>
            <span>{window.status === 'success' ? `Accepted · class ${window.result?.class}` : `Rejected · ${window.error?.code || 'reason unavailable'}`}</span>
          </div>
        ))}
      </div>
      <p className="explanation-limit">
        No AHI, severity category, treatment recommendation, or patient diagnosis is generated.
      </p>
    </section>
  )
}
