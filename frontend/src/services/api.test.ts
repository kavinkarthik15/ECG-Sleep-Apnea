import { describe, expect, it } from 'vitest'
import { resolveApiBaseUrl, resolveApiRootUrl } from './api'

describe('API URL configuration', () => {
  it('uses the same-origin API path by default', () => {
    expect(resolveApiBaseUrl(undefined)).toBe('/api/v1')
    expect(resolveApiRootUrl(undefined)).toBe('/')
  })

  it('keeps an explicitly configured local backend compatible', () => {
    expect(resolveApiBaseUrl('http://127.0.0.1:8000')).toBe('http://127.0.0.1:8000/api/v1')
    expect(resolveApiRootUrl('http://127.0.0.1:8000')).toBe('http://127.0.0.1:8000')
  })

  it('does not duplicate the API path', () => {
    expect(resolveApiBaseUrl('/api/v1/')).toBe('/api/v1')
    expect(resolveApiRootUrl('/api/v1')).toBe('/')
  })
})
