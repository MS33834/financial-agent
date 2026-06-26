import { useEffect, useState } from 'react'
import NavBar from '../components/NavBar.tsx'
import Modal from '../components/ui/Modal.tsx'
import Loading from '../components/ui/Loading.tsx'
import EmptyState from '../components/ui/EmptyState.tsx'
import { api } from '../api/client.ts'
import { getErrorMessage } from '../utils/errors.ts'
import type { DataResponse, PaginatedResponse } from '../types/report.ts'
import type { ApiKey, ApiKeyWithPlain } from '../types/apiKey.ts'

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState({ name: '', scopes: '', expires_at: '' })
  const [submitting, setSubmitting] = useState(false)
  // 创建 / 轮换后展示的一次性明文 key
  const [plainKey, setPlainKey] = useState<{ name: string; key: string } | null>(null)
  const [actingId, setActingId] = useState<string | null>(null)

  const fetchKeys = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get<DataResponse<PaginatedResponse<ApiKey>>>('/api-keys', {
        params: { page: 1, page_size: 50 },
      })
      setKeys(response.data.data?.items || [])
    } catch (err) {
      setError(getErrorMessage(err, '加载 API Key 列表失败'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchKeys()
  }, [])

  const handleCreate = async () => {
    setSubmitting(true)
    setError('')
    try {
      // 逗号分隔的 scopes 解析为数组
      const scopes = form.scopes
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
      const payload: Record<string, unknown> = { name: form.name, scopes }
      if (form.expires_at) {
        payload.expires_at = new Date(form.expires_at).toISOString()
      }
      const response = await api.post<DataResponse<ApiKeyWithPlain>>('/api-keys', payload)
      const created = response.data.data
      if (created) {
        setKeys((prev) => [created, ...prev])
        setPlainKey({ name: created.name, key: created.key })
      }
      setCreateOpen(false)
      setForm({ name: '', scopes: '', expires_at: '' })
    } catch (err) {
      setError(getErrorMessage(err, '创建 API Key 失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleRotate = async (key: ApiKey) => {
    if (!window.confirm(`确认轮换 Key「${key.name}」？旧 Key 将被吊销，仅返回一次新明文。`)) {
      return
    }
    setActingId(key.id)
    setError('')
    try {
      const response = await api.post<DataResponse<ApiKeyWithPlain>>(
        `/api-keys/${key.id}/rotate`,
      )
      const rotated = response.data.data
      if (rotated) {
        // 旧 Key 置为禁用，新 Key 加入列表顶部
        setKeys((prev) => [
          rotated,
          ...prev.map((k) => (k.id === key.id ? { ...k, is_active: 'N' } : k)),
        ])
        setPlainKey({ name: rotated.name, key: rotated.key })
      }
    } catch (err) {
      setError(getErrorMessage(err, '轮换 API Key 失败'))
    } finally {
      setActingId(null)
    }
  }

  const handleRevoke = async (key: ApiKey) => {
    if (!window.confirm(`确认吊销 Key「${key.name}」？吊销后该 Key 将立即失效。`)) {
      return
    }
    setActingId(key.id)
    setError('')
    try {
      await api.post(`/api-keys/${key.id}/revoke`)
      setKeys((prev) =>
        prev.map((k) => (k.id === key.id ? { ...k, is_active: 'N' } : k)),
      )
    } catch (err) {
      setError(getErrorMessage(err, '吊销 API Key 失败'))
    } finally {
      setActingId(null)
    }
  }

  const handleDelete = async (key: ApiKey) => {
    if (!window.confirm(`确认删除 Key「${key.name}」？此操作不可恢复。`)) {
      return
    }
    setActingId(key.id)
    setError('')
    try {
      await api.delete(`/api-keys/${key.id}`)
      setKeys((prev) => prev.filter((k) => k.id !== key.id))
    } catch (err) {
      setError(getErrorMessage(err, '删除 API Key 失败'))
    } finally {
      setActingId(null)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard?.writeText(text).catch(() => {})
  }

  return (
    <div className="container">
      <div className="page-header">
        <h1>API Key 管理</h1>
        <div className="actions">
          <NavBar />
          <button onClick={() => setCreateOpen(true)}>新建 Key</button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error mb-4" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <Loading text="加载 API Key 中..." />
      ) : keys.length === 0 ? (
        <EmptyState title="暂无 API Key" description="点击「新建 Key」创建第一个 API Key。" />
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>权限范围</th>
                <th>状态</th>
                <th>调用次数</th>
                <th>最后使用</th>
                <th>过期时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id}>
                  <td>{key.name}</td>
                  <td>
                    {key.scopes.length > 0 ? (
                      key.scopes.join(', ')
                    ) : (
                      <span className="text-muted">全部权限</span>
                    )}
                  </td>
                  <td>
                    {key.is_active === 'Y' ? (
                      <span className="badge success">启用</span>
                    ) : (
                      <span className="badge rejected">已吊销</span>
                    )}
                  </td>
                  <td>{key.usage_count}</td>
                  <td>
                    {key.last_used_at ? (
                      new Date(key.last_used_at).toLocaleString()
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td>
                    {key.expires_at ? (
                      new Date(key.expires_at).toLocaleString()
                    ) : (
                      <span className="text-muted">永不过期</span>
                    )}
                  </td>
                  <td>
                    <div className="action-group">
                      <button
                        className="secondary"
                        onClick={() => handleRotate(key)}
                        disabled={actingId === key.id || key.is_active !== 'Y'}
                      >
                        轮换
                      </button>
                      <button
                        className="secondary"
                        onClick={() => handleRevoke(key)}
                        disabled={actingId === key.id || key.is_active !== 'Y'}
                      >
                        吊销
                      </button>
                      <button
                        className="danger"
                        onClick={() => handleDelete(key)}
                        disabled={actingId === key.id}
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {createOpen && (
        <Modal
          title="新建 API Key"
          onClose={() => setCreateOpen(false)}
          footer={
            <>
              <button className="secondary" onClick={() => setCreateOpen(false)}>
                取消
              </button>
              <button onClick={handleCreate} disabled={submitting || !form.name}>
                {submitting ? '创建中...' : '创建'}
              </button>
            </>
          }
        >
          <div className="form-group">
            <label htmlFor="key-name">名称</label>
            <input
              id="key-name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="便于识别用途，如「数据看板」"
            />
          </div>
          <div className="form-group">
            <label htmlFor="key-scopes">权限范围</label>
            <input
              id="key-scopes"
              value={form.scopes}
              onChange={(e) => setForm({ ...form, scopes: e.target.value })}
              placeholder="逗号分隔，留空表示全部，如 queries:nl2sql,reports:read"
            />
          </div>
          <div className="form-group">
            <label htmlFor="key-expires">过期时间（可选）</label>
            <input
              id="key-expires"
              type="datetime-local"
              value={form.expires_at}
              onChange={(e) => setForm({ ...form, expires_at: e.target.value })}
            />
          </div>
        </Modal>
      )}

      {plainKey && (
        <Modal
          title="API Key 明文（仅显示一次）"
          onClose={() => setPlainKey(null)}
          footer={
            <>
              <button className="secondary" onClick={() => copyToClipboard(plainKey.key)}>
                复制
              </button>
              <button onClick={() => setPlainKey(null)}>我已保存</button>
            </>
          }
        >
          <div className="alert alert-warning mb-4">
            请立即保存以下明文 Key，关闭后将无法再次查看。
          </div>
          <div className="code-block" style={{ wordBreak: 'break-all' }}>
            {plainKey.key}
          </div>
          <p className="text-muted text-sm mt-4">名称：{plainKey.name}</p>
        </Modal>
      )}
    </div>
  )
}
