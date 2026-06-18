import type { Report } from '../types/report.ts'

interface ReportListProps {
  reports: Report[]
  onSelect: (report: Report) => void
}

export default function ReportList({ reports, onSelect }: ReportListProps) {
  if (reports.length === 0) {
    return <p>暂无报告</p>
  }

  return (
    <div className="card">
      <h3>报告列表</h3>
      <table>
        <thead>
          <tr>
            <th>标题</th>
            <th>类型</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {reports.map((report) => (
            <tr key={report.id}>
              <td>{report.title}</td>
              <td>{report.report_type}</td>
              <td>
                <span className={`badge ${report.status}`}>{report.status}</span>
              </td>
              <td>{new Date(report.created_at).toLocaleString()}</td>
              <td>
                <button onClick={() => onSelect(report)}>查看</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
