import { useEffect, useState } from 'react'
import NavBar from '../components/NavBar.tsx'
import { api } from '../api/client'
import type { AuditLog } from '../types/audit'
import AuditLogList from '../components/AuditLogList'
import Loading from '../components/ui/Loading.tsx'

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchLogs = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get('/audit/logs?page=1&page_size=100')
      setLogs(response.data.data.items)
    } catch (err) {
      setError('加载审计日志失败，可能没有权限')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [])

  return (
    <div className="container">
      <div className="page-header">
        <h1>审计日志</h1>
        <div className="actions">
          <NavBar />
          <button className="secondary" onClick={fetchLogs}>
            刷新
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error mb-4">{error}</div>}

      {loading ? <Loading text="加载审计日志中..." /> : <AuditLogList logs={logs} />}
    </div>
  )
}
