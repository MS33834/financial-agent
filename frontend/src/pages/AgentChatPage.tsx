import { useState, type FormEvent, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

interface Message {
  id: string
  role: 'user' | 'agent'
  content: string
  createdAt: Date
}

const formatTime = (date: Date) =>
  date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

export default function AgentChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: question.trim(),
      createdAt: new Date(),
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
          createdAt: new Date(),
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
      <div className="page-header">
        <h1>智能问答</h1>
        <div className="navbar">
          <Link to="/" className="nav-link">
            财务报告
          </Link>
          <Link to="/documents" className="nav-link">
            文档解析
          </Link>
          <Link to="/audit" className="nav-link">
            审计日志
          </Link>
        </div>
      </div>

      <div className="card chat-container">
        <div className="chat-messages">
          {messages.length === 0 ? (
            <div className="empty-state">
              <svg
                className="empty-state-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
              <h4 className="empty-state-title">开始对话</h4>
              <p className="empty-state-desc">输入财务相关问题，智能体将基于报表数据为您解答。</p>
            </div>
          ) : (
            messages.map((message) => (
              <div key={message.id} className={`chat-message ${message.role}`}>
                <div className="chat-avatar">{message.role === 'user' ? '我' : 'AI'}</div>
                <div>
                  <div className="chat-bubble">{message.content}</div>
                  <div className="chat-time">{formatTime(message.createdAt)}</div>
                </div>
              </div>
            ))
          )}
          {loading && (
            <div className="chat-message agent">
              <div className="chat-avatar">AI</div>
              <div className="chat-bubble">
                <span className="spinner" style={{ width: 14, height: 14, display: 'inline-block' }} />
                <span style={{ marginLeft: 8 }}>思考中...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {error && <div className="alert alert-error mb-4">{error}</div>}

        <form onSubmit={handleSubmit} className="chat-input">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="请输入问题..."
            disabled={loading}
          />
          <button type="submit" disabled={loading || !question.trim()}>
            {loading ? '发送中' : '发送'}
          </button>
        </form>
      </div>
    </div>
  )
}
