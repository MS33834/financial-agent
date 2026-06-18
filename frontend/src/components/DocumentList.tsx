import type { Document } from '../types/document'

interface DocumentListProps {
  documents: Document[]
  onSelect: (doc: Document) => void
}

export default function DocumentList({ documents, onSelect }: DocumentListProps) {
  const statusMap: Record<string, string> = {
    pending: '待处理',
    processing: '解析中',
    success: '成功',
    failed: '失败',
  }

  if (documents.length === 0) {
    return <p>暂无文档</p>
  }

  return (
    <table>
      <thead>
        <tr>
          <th>文件名</th>
          <th>状态</th>
          <th>置信度</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => (
          <tr key={doc.id}>
            <td>{doc.filename}</td>
            <td>{statusMap[doc.status] || doc.status}</td>
            <td>
              {doc.confidence !== null && doc.confidence !== undefined
                ? `${(doc.confidence * 100).toFixed(0)}%`
                : '-'}
            </td>
            <td>{new Date(doc.created_at).toLocaleString()}</td>
            <td>
              <button className="secondary" onClick={() => onSelect(doc)}>
                查看
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
