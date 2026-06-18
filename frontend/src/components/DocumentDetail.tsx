import type { Document } from '../types/document'

interface DocumentDetailProps {
  document: Document
  onClose: () => void
}

export default function DocumentDetail({ document: doc, onClose }: DocumentDetailProps) {
  return (
    <div className="modal" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>{doc.filename}</h2>
          <button className="secondary" onClick={onClose}>
            关闭
          </button>
        </div>

        <p>
          <strong>状态：</strong>
          {doc.status}
        </p>
        {doc.confidence !== null && doc.confidence !== undefined && (
          <p>
            <strong>置信度：</strong>
            {(doc.confidence * 100).toFixed(0)}%
          </p>
        )}
        {doc.error_message && (
          <div className="error">
            <strong>错误：</strong>
            {doc.error_message}
          </div>
        )}

        {doc.parse_result && (
          <div>
            <strong>解析结果：</strong>
            <pre
              style={{
                background: '#f5f5f5',
                padding: '1rem',
                borderRadius: '4px',
                overflow: 'auto',
                maxHeight: '400px',
              }}
            >
              {JSON.stringify(doc.parse_result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
