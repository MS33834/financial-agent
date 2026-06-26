import { useEffect, useState } from 'react'
import NavBar from '../components/NavBar.tsx'
import Modal from '../components/ui/Modal.tsx'
import Loading from '../components/ui/Loading.tsx'
import EmptyState from '../components/ui/EmptyState.tsx'
import { api } from '../api/client.ts'
import { getErrorMessage } from '../utils/errors.ts'
import type { DataResponse, PaginatedResponse } from '../types/report.ts'

// IM 用户映射
interface IMUserMapping {
  id: string
  user_id: string
  platform: string
  im_user_id: string
  created_at: string | null
  updated_at: string | null
}

// 支持的 IM 平台
const PLATFORM_OPTIONS = [
  { value: 'dingtalk', label: '钉钉' },
  { value: 'feishu', label: '飞书' },
  { value: 'wecom', label: '企业微信' },
]

const PLATFORM_LABELS: Record<string, string> = Object.fromEntries(
  PLATFORM_OPTIONS.map((o) => [o.value, o.label]),
)

export default function IMUserMappingsPage() {
  const [mappings, setMappings] = useState<IMUserMapping[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState({ platform: 'dingtalk', im_user_id: '', user_id: '' })
  const [submitting, setSubmitting] = useState(false)
  const [actingId, setActingId] = useState<string | null>(null)

  const fetchMappings = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get<DataResponse<PaginatedResponse<IMUserMapping>>>(
        '/im-user-mappings',
        { params: { page: 1, page_size: 50 } },
      )
      setMappings(response.data.data?.items || [])
    } catch (err) {
      setError(getErrorMessage(err, '加载 IM 用户映射失败'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMappings()
  }, [])

  const handleCreate = async () => {
    setSubmitting(true)
    setError('')
    try {
      // 创建接口直接返回映射对象（无 DataResponse 包裹）
      const response = await api.post<IMUserMapping>('/im-user-mappings', {
        platform: form.platform,
        im_user_id: form.im_user_id,
        user_id: form.user_id,
      })
      const created = response.data
      if (created) {
        setMappings((prev) => [created, ...prev])
      }
      setCreateOpen(false)
      setForm({ platform: 'dingtalk', im_user_id: '', user_id: '' })
    } catch (err) {
      setError(getErrorMessage(err, '创建 IM 用户映射失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (mapping: IMUserMapping) => {
    if (
      !window.confirm(
        `确认删除「${PLATFORM_LABELS[mapping.platform] || mapping.platform}」映射「${mapping.im_user_id}」？`,
      )
    ) {
      return
    }
    setActingId(mapping.id)
    setError('')
    try {
      await api.delete(`/im-user-mappings/${mapping.id}`)
      setMappings((prev) => prev.filter((m) => m.id !== mapping.id))
    } catch (err) {
      setError(getErrorMessage(err, '删除 IM 用户映射失败'))
    } finally {
      setActingId(null)
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <h1>IM 用户映射</h1>
        <div className="actions">
          <NavBar />
          <button onClick={() => setCreateOpen(true)}>新建映射</button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error mb-4" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <Loading text="加载映射中..." />
      ) : mappings.length === 0 ? (
        <EmptyState
          title="暂无 IM 用户映射"
          description="点击「新建映射」绑定 IM 平台用户与系统用户。"
        />
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>平台</th>
                <th>IM 用户 ID</th>
                <th>系统用户 ID</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {mappings.map((mapping) => (
                <tr key={mapping.id}>
                  <td>{PLATFORM_LABELS[mapping.platform] || mapping.platform}</td>
                  <td>{mapping.im_user_id}</td>
                  <td className="text-muted">{mapping.user_id}</td>
                  <td>
                    {mapping.created_at ? new Date(mapping.created_at).toLocaleString() : '—'}
                  </td>
                  <td>
                    <button
                      className="danger"
                      onClick={() => handleDelete(mapping)}
                      disabled={actingId === mapping.id}
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {createOpen && (
        <Modal
          title="新建 IM 用户映射"
          onClose={() => setCreateOpen(false)}
          footer={
            <>
              <button className="secondary" onClick={() => setCreateOpen(false)}>
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={submitting || !form.im_user_id || !form.user_id}
              >
                {submitting ? '创建中...' : '创建'}
              </button>
            </>
          }
        >
          <div className="form-group">
            <label htmlFor="im-platform">平台</label>
            <select
              id="im-platform"
              value={form.platform}
              onChange={(e) => setForm({ ...form, platform: e.target.value })}
            >
              {PLATFORM_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="im-user-id">IM 用户 ID</label>
            <input
              id="im-user-id"
              value={form.im_user_id}
              onChange={(e) => setForm({ ...form, im_user_id: e.target.value })}
              placeholder="IM 平台用户唯一标识"
            />
          </div>
          <div className="form-group">
            <label htmlFor="im-system-user">系统用户 ID</label>
            <input
              id="im-system-user"
              value={form.user_id}
              onChange={(e) => setForm({ ...form, user_id: e.target.value })}
              placeholder="对应的系统用户 UUID"
            />
          </div>
        </Modal>
      )}
    </div>
  )
}
