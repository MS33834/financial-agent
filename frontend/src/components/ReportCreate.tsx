import { useState } from 'react'
import { api } from '../api/client.ts'
import type { Report } from '../types/report.ts'

interface ReportCreateProps {
  onCreated: (report: Report) => void
}

export default function ReportCreate({ onCreated }: ReportCreateProps) {
  const [title, setTitle] = useState('')
  const [reportType, setReportType] = useState('profit')
  const [year, setYear] = useState(new Date().getFullYear())
  const [period, setPeriod] = useState('Q2')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const response = await api.post('/reports', {
        title,
        report_type: reportType,
        parameters: { year, period },
      })
      onCreated(response.data.data as Report)
      setTitle('')
    } catch (err) {
      setError('创建报告失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h3>新建报告</h3>
      {error && <div className="error">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>标题</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <div className="form-group" style={{ flex: 1 }}>
            <label>类型</label>
            <select value={reportType} onChange={(e) => setReportType(e.target.value)}>
              <option value="profit">利润表</option>
              <option value="balance">资产负债表</option>
              <option value="cash">现金流量表</option>
            </select>
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>年份</label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(parseInt(e.target.value, 10))}
              required
            />
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>周期</label>
            <select value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="Q1">Q1</option>
              <option value="Q2">Q2</option>
              <option value="Q3">Q3</option>
              <option value="Q4">Q4</option>
              <option value="annual">全年</option>
            </select>
          </div>
        </div>
        <div className="actions">
          <button type="submit" disabled={loading}>
            {loading ? '创建中...' : '创建报告'}
          </button>
        </div>
      </form>
    </div>
  )
}
