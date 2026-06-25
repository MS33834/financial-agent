import { useEffect, useState } from 'react'
import { api } from '../api/client'
import NavBar from '../components/NavBar.tsx'
import Loading from '../components/ui/Loading.tsx'
import EmptyState from '../components/ui/EmptyState.tsx'
import { getErrorMessage } from '../utils/errors.ts'
import type { PendingApproval } from '../types/approval'
import type { DataResponse, PaginatedResponse, Report } from '../types/report'

function toPendingApproval(report: Report): PendingApproval {
  return {
    id: report.id,
    report_id: report.id,
    report_title: report.title,
    status: 'reviewing',
    created_at: report.created_at,
  }
}

export default function ApprovalsPage() {
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [comments, setComments] = useState<Record<string, string>>({})
  const [acting, setActing] = useState<Record<string, boolean>>({})

  const fetchPendingApprovals = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get<DataResponse<PaginatedResponse<Report>>>('/reports', {
        params: { status: 'reviewing' },
      })
      const payload = response.data?.data
      const reports = Array.isArray(payload) ? payload : payload?.items || []
      setPendingApprovals(reports.map(toPendingApproval))
    } catch (err) {
      setError(getErrorMessage(err, '加载待审批报告失败'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPendingApprovals()
  }, [])

  const handleAction = async (reportId: string, action: 'approve' | 'reject') => {
    setActing((prev) => ({ ...prev, [reportId]: true }))
    try {
      await api.post(`/approvals/${reportId}/action`, {
        action,
        comments: comments[reportId] || undefined,
      })
      setComments((prev) => ({ ...prev, [reportId]: '' }))
      await fetchPendingApprovals()
    } catch (err) {
      setError(getErrorMessage(err, '审批操作失败'))
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
          <button className="secondary" onClick={fetchPendingApprovals}>
            刷新
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error mb-4" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <Loading text="加载待审批报告中..." />
      ) : pendingApprovals.length === 0 ? (
        <EmptyState title="暂无待审批报告" description="当有报告进入待审批状态时，将显示在这里。" />
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>报告</th>
                <th>状态</th>
                <th>提交时间</th>
                <th>备注</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {pendingApprovals.map((approval) => (
                <tr key={approval.id}>
                  <td>{approval.report_title}</td>
                  <td>待审批</td>
                  <td>{new Date(approval.created_at).toLocaleString()}</td>
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
                      disabled={acting[approval.report_id]}
                      className="full-width"
                    />
                  </td>
                  <td>
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
