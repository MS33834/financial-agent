import { useEffect, useState } from 'react'
import NavBar from '../components/NavBar.tsx'
import { api } from '../api/client'
import type { Document } from '../types/document'
import DocumentDetail from '../components/DocumentDetail'
import DocumentList from '../components/DocumentList'
import DocumentUpload from '../components/DocumentUpload'

const statusOptions: { value: string; label: string }[] = [
  { value: '', label: '全部' },
  { value: 'pending', label: '待处理' },
  { value: 'processing', label: '解析中' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'needs_review', label: '待复核' },
]

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [selected, setSelected] = useState<Document | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  const fetchDocuments = async (filterStatus: string) => {
    setLoading(true)
    setError('')
    try {
      const query = filterStatus
        ? `/documents?status=${filterStatus}&page=1&page_size=50`
        : '/documents?page=1&page_size=50'
      const response = await api.get(query)
      setDocuments(response.data.data.items)
    } catch (err) {
      setError('加载文档列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDocuments(status)
  }, [status])

  const handleUploaded = (doc: Document) => {
    setDocuments((prev) => [doc, ...prev])
  }

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>文档解析中心</h1>
        <NavBar />
      </div>

      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
        <label htmlFor="status-filter">状态筛选：</label>
        <select
          id="status-filter"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          style={{ minWidth: 140 }}
        >
          {statusOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <DocumentUpload onUploaded={handleUploaded} />

      {error && <div className="error">{error}</div>}

      {loading ? (
        <p>加载中...</p>
      ) : (
        <DocumentList documents={documents} onSelect={setSelected} />
      )}

      {selected && <DocumentDetail document={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
