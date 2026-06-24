import { useEffect, useMemo, useState } from 'react'
import NavBar from '../components/NavBar.tsx'
import { api } from '../api/client.ts'
import type { Report } from '../types/report.ts'
import ReportList from '../components/ReportList.tsx'
import ReportDetail from '../components/ReportDetail.tsx'
import ReportCreate from '../components/ReportCreate.tsx'
import Loading from '../components/ui/Loading.tsx'
import Badge from '../components/ui/Badge.tsx'

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  pending: '待处理',
  processing: '生成中',
  reviewing: '待复核',
  approved: '已通过',
  rejected: '已驳回',
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([])
  const [selected, setSelected] = useState<Report | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchReports = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get('/reports?page=1&page_size=50')
      setReports(response.data.data?.items || [])
    } catch (err) {
      setError('加载报告列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchReports()
  }, [])

  const handleCreated = (report: Report) => {
    setReports((prev) => [report, ...prev])
  }

  const stats = useMemo(() => {
    const total = reports.length
    const approved = reports.filter((r) => r.status === 'approved').length
    const reviewing = reports.filter((r) => r.status === 'reviewing').length
    const failed = reports.filter((r) => r.status === 'failed').length
    return { total, approved, reviewing, failed }
  }, [reports])

  const statusDistribution = useMemo(() => {
    const counts: Record<string, number> = {}
    reports.forEach((r) => {
      counts[r.status] = (counts[r.status] || 0) + 1
    })
    return Object.entries(counts)
      .map(([status, count]) => ({ status, label: STATUS_LABELS[status] || status, count }))
      .sort((a, b) => b.count - a.count)
  }, [reports])

  return (
    <div className="container">
      <div className="page-header">
        <h1>财务报告中心</h1>
        <NavBar showLogout />
      </div>

      <div className="stat-grid compact">
        <div className="stat-card">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">全部报告</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.approved}</div>
          <div className="stat-label">已通过</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.reviewing}</div>
          <div className="stat-label">待复核</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.failed}</div>
          <div className="stat-label">生成失败</div>
        </div>
      </div>

      {statusDistribution.length > 0 && (
        <div className="card status-summary">
          <h3 className="card-title">状态分布</h3>
          <div className="status-badges">
            {statusDistribution.map((item) => (
              <div key={item.status} className="status-badge-item">
                <Badge status={item.status} />
                <span className="status-count">{item.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <ReportCreate onCreated={handleCreated} />

      {error && (
        <div className="alert alert-error mb-4" role="alert">
          {error}
        </div>
      )}

      {loading ? <Loading text="加载报告中..." /> : <ReportList reports={reports} onSelect={setSelected} />}

      {selected && <ReportDetail report={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
