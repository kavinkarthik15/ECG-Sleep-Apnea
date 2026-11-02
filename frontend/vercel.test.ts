import { describe, expect, it } from 'vitest'
import config from './vercel.json'

describe('Vercel API proxy', () => {
  it('rewrites API and health requests to the fixed backend', () => {
    expect(config.rewrites).toEqual([
      {
        source: '/api/:path*',
        destination: 'https://ecg-sleep-apnea-screening.vercel.app/api/:path*',
      },
      {
        source: '/health',
        destination: 'https://ecg-sleep-apnea-screening.vercel.app/health',
      },
    ])
  })
})
