import { useState, type ChangeEvent, type FormEvent } from 'react'
import { api } from '../api/client'
import type { Document } from '../types/document'

interface DocumentUploadProps {
  onUploaded: (doc: Document) => void
}

export default function DocumentUpload({ onUploaded }: DocumentUploadProps) {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setError('')
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0])
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!file) {
      setError('请选择文件')
      return
    }

    const allowedExtensions = ['csv', 'xlsx', 'xls', 'pdf']
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ext || !allowedExtensions.includes(ext)) {
      setError(`仅支持 ${allowedExtensions.join('/')} 文件`)
      return
    }

    setUploading(true)
    setError('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await api.post('/documents/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      if (response.data.data) onUploaded(response.data.data)
      setFile(null)
      const input = document.getElementById('file-input') as HTMLInputElement
      if (input) input.value = ''
    } catch (err) {
      setError('上传失败，请检查文件格式和权限')
    } finally {
      setUploading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="file-input">
        <input
          id="file-input"
          type="file"
          accept=".csv,.xlsx,.xls,.pdf"
          onChange={handleChange}
          disabled={uploading}
        />
        <button type="submit" disabled={uploading || !file}>
          {uploading ? '上传中...' : '上传并解析'}
        </button>
      </div>
      {error && (
        <div className="alert alert-error" role="alert">
          {error}
        </div>
      )}
    </form>
  )
}
