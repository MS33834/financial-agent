import { useEffect, useState } from 'react'
import NavBar from '../components/NavBar.tsx'
import { api } from '../api/client'
import type { AuditLog } from '../types/audit'
import AuditLogList from '../components/AuditLogList'

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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>审计日志</h1>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <NavBar />
          <button className="secondary" onClick={fetchLogs}>
            刷新
          </button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      {loading ? <p>加载中...</p> : <AuditLogList logs={logs} />}
    </div>
  )
}
