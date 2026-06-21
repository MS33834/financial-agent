import { useEffect, useState } from 'react'
import axios from 'axios'
import { api } from '../api/client'
import NavBar from '../components/NavBar.tsx'
import Loading from '../components/ui/Loading.tsx'
import EmptyState from '../components/ui/EmptyState.tsx'
import type { Approval } from '../types/approval'

const statusMap: Record<string, string> = {
  pending: '待审批',
  approved: '已通过',
  rejected: '已驳回',
}

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [comments, setComments] = useState<Record<string, string>>({})
  const [acting, setActing] = useState<Record<string, boolean>>({})

  const fetchApprovals = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get('/approvals?report_id=')
      setApprovals(response.data.data.items)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 403) {
        setError('无权限访问审批记录')
      } else {
        setError('加载审批记录失败')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchApprovals()
  }, [])

  const handleAction = async (reportId: string, action: 'approve' | 'reject') => {
    setActing((prev) => ({ ...prev, [reportId]: true }))
    try {
      await api.post(`/approvals/${reportId}/action`, {
        action,
        comments: comments[reportId] || undefined,
      })
      setComments((prev) => ({ ...prev, [reportId]: '' }))
      await fetchApprovals()
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 403) {
        setError('无权限执行该操作')
      } else {
        setError('操作失败')
      }
    } finally {
      setActing((prev) => ({ ...prev, [reportId]: false }))
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <h1>人工审批</h1>
        <div className="actions">
          <NavBar />
          <button className="secondary" onClick={fetchApprovals}>
            刷新
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error mb-4">{error}</div>}

      {loading ? (
        <Loading text="加载审批记录中..." />
      ) : approvals.length === 0 ? (
        <EmptyState title="暂无审批记录" description="当有报告需要审批时，将显示在这里。" />
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>报告</th>
                <th>状态</th>
                <th>审批人</th>
                <th>备注</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {approvals.map((approval) => (
                <tr key={approval.id}>
                  <td>{approval.report_title}</td>
                  <td>{statusMap[approval.status] || approval.status}</td>
                  <td>{approval.reviewer_name || '-'}</td>
                  <td>
                    <input
                      value={comments[approval.report_id] || ''}
                      onChange={(e) =>
                        setComments((prev) => ({
                          ...prev,
                          [approval.report_id]: e.target.value,
                        }))
                      }
                      placeholder="审批备注（可选）"
                      disabled={acting[approval.report_id] || approval.status !== 'pending'}
                      className="full-width"
                    />
                  </td>
                  <td>
                    {approval.status === 'pending' ? (
                      <div className="action-group">
                        <button
                          onClick={() => handleAction(approval.report_id, 'approve')}
                          disabled={acting[approval.report_id]}
                        >
                          通过
                        </button>
                        <button
                          className="secondary"
                          onClick={() => handleAction(approval.report_id, 'reject')}
                          disabled={acting[approval.report_id]}
                        >
                          驳回
                        </button>
                      </div>
                    ) : (
                      '-'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
