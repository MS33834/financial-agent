import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Document } from '../types/document'
import DocumentDetail from '../components/DocumentDetail'
import DocumentList from '../components/DocumentList'
import DocumentUpload from '../components/DocumentUpload'

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [selected, setSelected] = useState<Document | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchDocuments = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get('/documents?page=1&page_size=50')
      setDocuments(response.data.data.items)
    } catch (err) {
      setError('加载文档列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDocuments()
  }, [])

  const handleUploaded = (doc: Document) => {
    setDocuments((prev) => [doc, ...prev])
  }

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>文档解析中心</h1>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <Link to="/">
            <button className="secondary">财务报告</button>
          </Link>
        </div>
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
