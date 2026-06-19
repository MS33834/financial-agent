import { useState, useMemo } from 'react'
import { api } from '../api/client.ts'
import type { Report } from '../types/report.ts'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

interface ReportDetailProps {
  report: Report
  onClose: () => void
}

export default function ReportDetail({ report, onClose }: ReportDetailProps) {
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const [format, setFormat] = useState<'pdf' | 'xlsx' | 'markdown' | 'json'>('markdown')

  const chartData = useMemo(() => {
    if (!report.content) return []
    return report.content.sections
      .filter((section) => typeof section.value === 'number')
      .map((section) => ({
        name: section.name,
        value: section.value as number,
      }))
  }, [report.content])

  const handleExport = async () => {
    setExporting(true)
    setExportError('')
    try {
      const response = await api.get(`/reports/${report.id}/export?fmt=${format}`)
      const url = response.data.data.content_url as string
      window.open(url, '_blank')
    } catch (err) {
      setExportError('导出失败')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{report.title}</h2>
        <p>
          <span className={`badge ${report.status}`}>{report.status}</span>
          <span style={{ marginLeft: 12 }}>类型: {report.report_type}</span>
        </p>

        {report.error_message && (
          <div className="error">生成错误: {report.error_message}</div>
        )}

        {report.summary && (
          <div className="card">
            <h4>摘要</h4>
            <p>{report.summary}</p>
          </div>
        )}

        {report.content && (
          <div className="card">
            <h4>指标</h4>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>指标</th>
                    <th>数值</th>
                  </tr>
                </thead>
                <tbody>
                  {report.content.sections.map((section) => (
                    <tr key={section.metric}>
                      <td>{section.name}</td>
                      <td>{section.value.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {chartData.length > 0 && (
              <div style={{ width: '100%', height: 300, marginTop: 16 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="value" fill="#1a73e8" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        <div className="actions">
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value as 'pdf' | 'xlsx' | 'markdown' | 'json')}
          >
            <option value="pdf">PDF</option>
            <option value="xlsx">Excel</option>
            <option value="markdown">Markdown</option>
            <option value="json">JSON</option>
          </select>
          <button onClick={handleExport} disabled={exporting}>
            {exporting ? '导出中...' : '导出'}
          </button>
          {report.content_url && (
            <a href={report.content_url} target="_blank" rel="noreferrer">
              已导出文件
            </a>
          )}
          <button className="secondary" onClick={onClose}>
            关闭
          </button>
        </div>

        {exportError && <div className="error">{exportError}</div>}
      </div>
    </div>
  )
}
