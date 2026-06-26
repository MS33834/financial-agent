import { useEffect, useState } from 'react'
import NavBar from '../components/NavBar.tsx'
import Modal from '../components/ui/Modal.tsx'
import Loading from '../components/ui/Loading.tsx'
import EmptyState from '../components/ui/EmptyState.tsx'
import { api } from '../api/client.ts'
import { getErrorMessage } from '../utils/errors.ts'
import type { DataResponse, PaginatedResponse } from '../types/report.ts'
import type { User } from '../types/user.ts'

// 用户角色中文标签
const ROLE_LABELS: Record<string, string> = {
  admin: '管理员',
  finance_manager: '财务经理',
  auditor: '审计员',
  viewer: '查看者',
}

// 表单初始值
const EMPTY_FORM = {
  username: '',
  email: '',
  password: '',
  role: 'viewer',
  is_active: 'Y',
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<User | null>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [submitting, setSubmitting] = useState(false)
  const [resetTarget, setResetTarget] = useState<User | null>(null)
  const [resetPassword, setResetPassword] = useState('')
  const [resetSubmitting, setResetSubmitting] = useState(false)

  const fetchUsers = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get<DataResponse<PaginatedResponse<User>>>('/users', {
        params: { page: 1, page_size: 50 },
      })
      setUsers(response.data.data?.items || [])
    } catch (err) {
      setError(getErrorMessage(err, '加载用户列表失败'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [])

  const openCreate = () => {
    setEditing(null)
    setForm({ ...EMPTY_FORM })
    setModalOpen(true)
  }

  const openEdit = (user: User) => {
    setEditing(user)
    setForm({
      username: user.username,
      email: user.email || '',
      password: '',
      role: user.role,
      is_active: user.is_active,
    })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      if (editing) {
        // 更新用户：密码留空则不修改
        const payload: Record<string, string> = {
          email: form.email,
          role: form.role,
          is_active: form.is_active,
        }
        if (form.password) {
          payload.password = form.password
        }
        const response = await api.put<DataResponse<User>>(`/users/${editing.id}`, payload)
        const updated = response.data.data
        if (updated) {
          setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
        }
      } else {
        // 创建用户
        const response = await api.post<DataResponse<User>>('/users', {
          username: form.username,
          email: form.email || null,
          password: form.password,
          role: form.role,
          is_active: form.is_active,
        })
        const created = response.data.data
        if (created) {
          setUsers((prev) => [created, ...prev])
        }
      }
      setModalOpen(false)
    } catch (err) {
      setError(getErrorMessage(err, '保存用户失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (user: User) => {
    if (!window.confirm(`确认删除用户「${user.username}」？此操作不可恢复。`)) {
      return
    }
    try {
      await api.delete(`/users/${user.id}`)
      setUsers((prev) => prev.filter((u) => u.id !== user.id))
    } catch (err) {
      setError(getErrorMessage(err, '删除用户失败'))
    }
  }

  const handleResetPassword = async () => {
    if (!resetTarget) return
    setResetSubmitting(true)
    setError('')
    try {
      await api.post(`/users/${resetTarget.id}/reset-password`, {
        password: resetPassword,
      })
      setResetTarget(null)
      setResetPassword('')
    } catch (err) {
      setError(getErrorMessage(err, '重置密码失败'))
    } finally {
      setResetSubmitting(false)
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <h1>用户管理</h1>
        <div className="actions">
          <NavBar />
          <button onClick={openCreate}>新建用户</button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error mb-4" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <Loading text="加载用户中..." />
      ) : users.length === 0 ? (
        <EmptyState title="暂无用户" description="点击「新建用户」创建第一个用户。" />
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>用户名</th>
                <th>邮箱</th>
                <th>角色</th>
                <th>状态</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.username}</td>
                  <td>{user.email || <span className="text-muted">—</span>}</td>
                  <td>{ROLE_LABELS[user.role] || user.role}</td>
                  <td>
                    {user.is_active === 'Y' ? (
                      <span className="badge success">启用</span>
                    ) : (
                      <span className="badge rejected">禁用</span>
                    )}
                  </td>
                  <td>
                    {user.created_at ? new Date(user.created_at).toLocaleString() : '—'}
                  </td>
                  <td>
                    <div className="action-group">
                      <button className="secondary" onClick={() => openEdit(user)}>
                        编辑
                      </button>
                      <button
                        className="secondary"
                        onClick={() => {
                          setResetTarget(user)
                          setResetPassword('')
                        }}
                      >
                        重置密码
                      </button>
                      <button className="danger" onClick={() => handleDelete(user)}>
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

      {modalOpen && (
        <Modal
          title={editing ? '编辑用户' : '新建用户'}
          onClose={() => setModalOpen(false)}
          footer={
            <>
              <button className="secondary" onClick={() => setModalOpen(false)}>
                取消
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting || (!editing && (!form.username || !form.password))}
              >
                {submitting ? '保存中...' : '保存'}
              </button>
            </>
          }
        >
          <div className="form-group">
            <label htmlFor="user-username">用户名</label>
            <input
              id="user-username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              disabled={!!editing}
              placeholder="登录用户名"
            />
          </div>
          <div className="form-group">
            <label htmlFor="user-email">邮箱</label>
            <input
              id="user-email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="可选"
            />
          </div>
          <div className="form-group">
            <label htmlFor="user-password">
              {editing ? '新密码（留空保持不变）' : '密码'}
            </label>
            <input
              id="user-password"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder={editing ? '留空则不修改' : '至少 6 位'}
            />
          </div>
          <div className="form-group">
            <label htmlFor="user-role">角色</label>
            <select
              id="user-role"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              {Object.entries(ROLE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="user-active">状态</label>
            <select
              id="user-active"
              value={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.value })}
            >
              <option value="Y">启用</option>
              <option value="N">禁用</option>
            </select>
          </div>
        </Modal>
      )}

      {resetTarget && (
        <Modal
          title={`重置密码 - ${resetTarget.username}`}
          onClose={() => setResetTarget(null)}
          footer={
            <>
              <button className="secondary" onClick={() => setResetTarget(null)}>
                取消
              </button>
              <button
                onClick={handleResetPassword}
                disabled={resetSubmitting || resetPassword.length < 6}
              >
                {resetSubmitting ? '重置中...' : '确认重置'}
              </button>
            </>
          }
        >
          <div className="form-group">
            <label htmlFor="reset-password-input">新密码</label>
            <input
              id="reset-password-input"
              type="password"
              value={resetPassword}
              onChange={(e) => setResetPassword(e.target.value)}
              placeholder="至少 6 位"
            />
          </div>
        </Modal>
      )}
    </div>
  )
}
