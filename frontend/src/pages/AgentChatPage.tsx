import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

interface Message {
  id: string
  role: 'user' | 'agent'
  content: string
}

export default function AgentChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: question.trim(),
    }
    setMessages((prev) => [...prev, userMessage])
    setQuestion('')
    setLoading(true)
    setError('')

    try {
      const response = await api.post('/agent/chat', { question: userMessage.content })
      const answer = response.data.data.answer as string
      setMessages((prev) => [
        ...prev,
        {
          id: `${Date.now()}-answer`,
          role: 'agent',
          content: answer,
        },
      ])
    } catch (err) {
      setError('智能体回答失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>智能问答</h1>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <Link to="/">
            <button className="secondary">财务报告</button>
          </Link>
          <Link to="/documents">
            <button className="secondary">文档解析</button>
          </Link>
          <Link to="/audit">
            <button className="secondary">审计日志</button>
          </Link>
        </div>
      </div>

      <div
        className="card"
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: 'calc(100vh - 240px)',
          minHeight: 400,
        }}
      >
        <div style={{ flex: 1, overflow: 'auto', marginBottom: '1rem' }}>
          {messages.length === 0 ? (
            <p style={{ color: '#64748b' }}>请输入您的问题，智能体将为您解答。</p>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                style={{
                  display: 'flex',
                  justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom: '0.75rem',
                }}
              >
                <div
                  style={{
                    maxWidth: '70%',
                    padding: '10px 14px',
                    borderRadius: 12,
                    background: message.role === 'user' ? '#1a73e8' : '#f1f5f9',
                    color: message.role === 'user' ? '#fff' : '#213547',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {message.content}
                </div>
              </div>
            ))
          )}
        </div>

        {error && <div className="error" style={{ marginBottom: '1rem' }}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="请输入问题..."
              disabled={loading}
              style={{ flex: 1 }}
            />
            <button type="submit" disabled={loading || !question.trim()}>
              {loading ? '思考中...' : '发送'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
