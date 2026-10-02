export const DEMO_SAMPLE_RATE = 100
export const DEMO_WINDOW_SAMPLES = 60 * DEMO_SAMPLE_RATE
export const DEMO_ECG_URL = '/demo/sample_ecg.csv'

export async function loadDemoSignal(): Promise<number[]> {
  let response: Response
  try {
    response = await fetch(DEMO_ECG_URL)
  } catch {
    throw new Error(`Demo ECG file could not be loaded from ${DEMO_ECG_URL}.`)
  }

  if (!response.ok) {
    throw new Error(`Demo ECG file could not be loaded (${response.status} ${response.statusText}).`)
  }

  const text = await response.text()
  const rows = text.trim().split(/\r?\n/)
  if (rows[0]?.trim().toLowerCase() === 'ecg') {
    rows.shift()
  }

  const values = rows.map((row, index) => {
    const value = row.trim()
    if (!value) {
      throw new Error(`Demo ECG file contains an empty value at data row ${index + 1}.`)
    }

    const sample = Number(value)
    if (!Number.isFinite(sample)) {
      throw new Error(`Demo ECG file contains a non-numeric value at data row ${index + 1}.`)
    }
    return sample
  })

  if (values.length < DEMO_WINDOW_SAMPLES) {
    throw new Error(`Demo ECG file must contain at least ${DEMO_WINDOW_SAMPLES} samples; found ${values.length}.`)
  }

  console.info(`Loaded demo ECG: ${values.length} samples`)
  return values
}

export function buildWaveformPath(signal: number[], width = 680, height = 180, padding = 16) {
  if (!signal.length) return ''
  const min = Math.min(...signal)
  const max = Math.max(...signal)
  const range = Math.max(max - min, Number.EPSILON)
  const center = (max + min) / 2

  return signal
    .map((value, index) => {
      const x = padding + (index / Math.max(signal.length - 1, 1)) * (width - padding * 2)
      const normalized = (value - center) / range
      const y = height / 2 - normalized * (height * 0.5 - 10)
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
}
