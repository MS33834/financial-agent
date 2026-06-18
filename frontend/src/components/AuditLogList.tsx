import type { AuditLog } from '../types/audit'

interface AuditLogListProps {
  logs: AuditLog[]
}

export default function AuditLogList({ logs }: AuditLogListProps) {
  if (logs.length === 0) {
    return <p>暂无审计日志</p>
  }

  return (
    <table>
      <thead>
        <tr>
          <th>时间</th>
          <th>操作</th>
          <th>资源</th>
          <th>结果</th>
          <th>IP</th>
          <th>原因</th>
        </tr>
      </thead>
      <tbody>
        {logs.map((log) => (
          <tr key={log.id}>
            <td>{new Date(log.timestamp).toLocaleString()}</td>
            <td>{log.action}</td>
            <td>{log.resource}</td>
            <td>{log.result || '-'}</td>
            <td>{log.ip || '-'}</td>
            <td>{log.reason || '-'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
