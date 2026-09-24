import { FileText, UploadCloud } from 'lucide-react'
import { useRef } from 'react'

export function DropZone({ onSelect, disabled }: { onSelect: (file: File) => void; disabled?: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null)
  function choose(file?: File) { if (file) onSelect(file) }
  return <div className="drop-zone" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); choose(event.dataTransfer.files[0]) }}>
    <div className="upload-icon"><UploadCloud size={26} /></div><h2>Drop an ECG recording here</h2><p>or browse for a CSV or TXT file</p>
    <button className="button button-secondary" disabled={disabled} onClick={() => inputRef.current?.click()}><FileText size={17} /> Browse files</button>
    <input ref={inputRef} hidden type="file" accept=".csv,.txt,text/csv,text/plain" onChange={(event) => choose(event.target.files?.[0])} />
    <small>Single-channel ECG · 100 Hz · maximum 10 MB</small>
  </div>
}