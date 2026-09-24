import { AlertCircle, RotateCcw } from 'lucide-react'
import type { ApiError } from '../../types/api'

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return <div className="error-state" role="alert">
    <div className="error-icon"><AlertCircle size={20} /></div>
    <div><strong>{error.code === 'NETWORK_ERROR' ? 'Analysis service unavailable' : 'Analysis could not be completed'}</strong><p>{error.message}</p></div>
    {onRetry && <button className="icon-button" onClick={onRetry} aria-label="Try again" title="Try again"><RotateCcw size={17} /></button>}
  </div>
}