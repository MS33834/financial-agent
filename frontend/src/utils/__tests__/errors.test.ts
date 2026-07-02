import { describe, it, expect, vi, afterEach } from 'vitest'
import axios from 'axios'
import { getErrorMessage } from '../errors'

describe('getErrorMessage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns backend message for axios error with response.data.message', () => {
    const err = new Error('network')
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    Object.assign(err, { response: { data: { message: '后端错误' }, status: 400 } })
    expect(getErrorMessage(err)).toBe('后端错误')
  })

  it('returns status-specific messages', () => {
    const cases = [
      { status: 401, expected: '登录已过期，请重新登录' },
      { status: 403, expected: '没有权限执行此操作' },
      { status: 404, expected: '请求的资源不存在' },
      { status: 429, expected: '请求过于频繁，请稍后再试' },
      { status: 500, expected: '服务器内部错误，请稍后重试' },
      { status: 502, expected: '服务器内部错误，请稍后重试' },
    ]

    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    for (const { status, expected } of cases) {
      const err = new Error('fail')
      Object.assign(err, { response: { status, data: {} } })
      expect(getErrorMessage(err)).toBe(expected)
    }
  })

  it('returns timeout message for ECONNABORTED', () => {
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    const err = new Error('timeout')
    Object.assign(err, { code: 'ECONNABORTED', response: undefined })
    expect(getErrorMessage(err)).toBe('请求超时，请检查网络后重试')
  })

  it('returns network message when no response', () => {
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    const err = new Error('network')
    Object.assign(err, { response: undefined })
    expect(getErrorMessage(err)).toBe('网络连接失败，请检查网络设置')
  })

  it('returns fallback for other axios errors', () => {
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)
    const err = new Error('other')
    Object.assign(err, { response: { status: 418, data: {} } })
    expect(getErrorMessage(err, '自定义兜底')).toBe('自定义兜底')
  })

  it('returns Error message for native errors', () => {
    expect(getErrorMessage(new Error('出错了'), '兜底')).toBe('出错了')
  })

  it('returns fallback for empty Error message', () => {
    expect(getErrorMessage(new Error(''), '兜底')).toBe('兜底')
  })

  it('returns fallback for non-error values', () => {
    expect(getErrorMessage(null, '兜底')).toBe('兜底')
    expect(getErrorMessage(undefined, '兜底')).toBe('兜底')
    expect(getErrorMessage(42, '兜底')).toBe('兜底')
  })
})
