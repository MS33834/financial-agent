import { useEffect, useState } from 'react'
import NavBar from '../components/NavBar.tsx'
import { api } from '../api/client'
import type { Document } from '../types/document'
import DocumentDetail from '../components/DocumentDetail'
import DocumentList from '../components/DocumentList'
import DocumentUpload from '../components/DocumentUpload'
import Loading from '../components/ui/Loading.tsx'

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
      <div className="page-header">
        <h1>文档解析中心</h1>
        <NavBar />
      </div>

      <div className="toolbar">
        <label htmlFor="status-filter">状态筛选</label>
        <select
          id="status-filter"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {statusOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <DocumentUpload onUploaded={handleUploaded} />

      {error && <div className="alert alert-error mb-4">{error}</div>}

      {loading ? <Loading text="加载文档中..." /> : <DocumentList documents={documents} onSelect={setSelected} />}

      {selected && <DocumentDetail document={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
