import axios from 'axios'

/**
 * 统一从错误对象中提取用户可读的消息。
 *
 * 优先级：
 * 1. Axios 错误：后端返回的 `response.data.message`
 * 2. Axios 错误：HTTP 状态码对应的通用提示
 * 3. 原生 Error 的 `message`
 * 4. 兜底默认消息
 */
export function getErrorMessage(err: unknown, fallback = '操作失败，请稍后重试'): string {
  if (axios.isAxiosError(err)) {
    const message = err.response?.data?.message
    if (message && typeof message === 'string') {
      return message
    }
    // 根据状态码给出通用提示
    const status = err.response?.status
    if (status === 401) return '登录已过期，请重新登录'
    if (status === 403) return '没有权限执行此操作'
    if (status === 404) return '请求的资源不存在'
    if (status === 429) return '请求过于频繁，请稍后再试'
    if (status && status >= 500) return '服务器内部错误，请稍后重试'
    if (err.code === 'ECONNABORTED') return '请求超时，请检查网络后重试'
    if (!err.response) return '网络连接失败，请检查网络设置'
    return fallback
  }
  if (err instanceof Error) {
    return err.message || fallback
  }
  return fallback
}
