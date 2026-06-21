import { useEffect, useState } from 'react'
import NavBar from '../components/NavBar.tsx'
import { api } from '../api/client.ts'
import type { Report } from '../types/report.ts'
import ReportList from '../components/ReportList.tsx'
import ReportDetail from '../components/ReportDetail.tsx'
import ReportCreate from '../components/ReportCreate.tsx'
import Loading from '../components/ui/Loading.tsx'

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
      <div className="page-header">
        <h1>财务报告中心</h1>
        <NavBar showLogout />
      </div>

      <ReportCreate onCreated={handleCreated} />

      {error && <div className="alert alert-error mb-4">{error}</div>}

      {loading ? <Loading text="加载报告中..." /> : <ReportList reports={reports} onSelect={setSelected} />}

      {selected && <ReportDetail report={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
