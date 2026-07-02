import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { api } from '../client'

describe('api client', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  const getRequestHandler = () => {
    const handlers = (api.interceptors.request as unknown as { handlers?: Array<{ fulfilled: (config: unknown) => unknown }> }).handlers
    return handlers?.[0]
  }

  const getResponseHandler = () => {
    const handlers = (api.interceptors.response as unknown as { handlers?: Array<{ fulfilled: (response: unknown) => unknown; rejected: (error: unknown) => Promise<unknown> }> }).handlers
    return handlers?.[0]
  }

  it('adds Authorization header when token exists', async () => {
    localStorage.setItem('token', 'test-token')
    const handler = getRequestHandler()
    if (!handler) return
    const request = { headers: {} as Record<string, string>, url: '/documents' }
    const result = await handler.fulfilled(request)
    expect((result as typeof request).headers.Authorization).toBe('Bearer test-token')
  })

  it('does not add Authorization header when token missing', async () => {
    const handler = getRequestHandler()
    if (!handler) return
    const request = { headers: {} as Record<string, string>, url: '/documents' }
    const result = await handler.fulfilled(request)
    expect((result as typeof request).headers.Authorization).toBeUndefined()
  })

  it('returns response unchanged', () => {
    const handler = getResponseHandler()
    if (!handler) return
    const response = { data: 'ok' }
    expect(handler.fulfilled(response)).toBe(response)
  })

  it('removes token and redirects on 401 for non-login requests', () => {
    const originalHref = window.location.href
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { href: originalHref },
    })
    localStorage.setItem('token', 'old-token')
    const handler = getResponseHandler()
    if (!handler) return
    const error = {
      ...new Error('Unauthorized'),
      isAxiosError: true,
      config: { url: '/documents' },
      response: { status: 401 },
    }
    handler.rejected(error).catch(() => {})
    expect(localStorage.getItem('token')).toBeNull()
    expect(window.location.href).toBe('/login')
  })

  it('does not redirect or clear token on 401 for login endpoint', () => {
    const originalHref = window.location.href
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { href: originalHref },
    })
    localStorage.setItem('token', 'old-token')
    const handler = getResponseHandler()
    if (!handler) return
    const error = {
      ...new Error('Unauthorized'),
      isAxiosError: true,
      config: { url: '/auth/login' },
      response: { status: 401 },
    }
    handler.rejected(error).catch(() => {})
    expect(localStorage.getItem('token')).toBe('old-token')
    expect(window.location.href).toBe(originalHref)
  })
})
