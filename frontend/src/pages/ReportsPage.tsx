import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.tsx'
import { api } from '../api/client.ts'
import type { Report } from '../types/report.ts'
import ReportList from '../components/ReportList.tsx'
import ReportDetail from '../components/ReportDetail.tsx'
import ReportCreate from '../components/ReportCreate.tsx'

export default function ReportsPage() {
  const { logout } = useAuth()
  const [reports, setReports] = useState<Report[]>([])
  const [selected, setSelected] = useState<Report | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchReports = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get('/reports?page=1&page_size=50')
      setReports(response.data.data.items)
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

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>财务报告中心</h1>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <Link to="/documents">
            <button className="secondary">文档解析</button>
          </Link>
          <Link to="/audit">
            <button className="secondary">审计日志</button>
          </Link>
          <button className="secondary" onClick={logout}>
            退出登录
          </button>
        </div>
      </div>

      <ReportCreate onCreated={handleCreated} />

      {error && <div className="error">{error}</div>}

      {loading ? (
        <p>加载中...</p>
      ) : (
        <ReportList reports={reports} onSelect={setSelected} />
      )}

      {selected && <ReportDetail report={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
