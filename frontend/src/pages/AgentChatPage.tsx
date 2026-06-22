import { useState, type FormEvent, useRef, useEffect, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../api/client'
import NavBar from '../components/NavBar.tsx'

interface Message {
  id: string
  role: 'user' | 'agent'
  content: string
  createdAt: Date
}

const SUGGESTIONS = [
  '本月营业收入是多少？',
  '2025年Q2净利润',
  '总资产周转率',
  '最近有哪些待审批报告？',
]

const formatTime = (date: Date) =>
  date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

export default function AgentChatPage() {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const initialQuestion = params.get('question') || ''

  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState(initialQuestion)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const initialSubmittedRef = useRef(false)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSubmitInternal = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || loading) return

      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: trimmed,
        createdAt: new Date(),
      }
      setMessages((prev) => [...prev, userMessage])
      setQuestion('')
      setLoading(true)
      setError('')

      try {
        const response = await api.post('/agent/chat', { question: trimmed })
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
    },
    [loading],
  )

  useEffect(() => {
    if (initialQuestion && !initialSubmittedRef.current) {
      initialSubmittedRef.current = true
      void handleSubmitInternal(initialQuestion)
    }
  }, [initialQuestion, handleSubmitInternal])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    void handleSubmitInternal(question)
  }

  const onSuggestionClick = (text: string) => {
    void handleSubmitInternal(text)
  }

  return (
    <div className="container">
      <div className="page-header">
        <h1>智能问答</h1>
        <NavBar />
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
              <div className="suggestion-chips">
                {SUGGESTIONS.map((text) => (
                  <button
                    key={text}
                    type="button"
                    className="chip"
                    onClick={() => onSuggestionClick(text)}
                    disabled={loading}
                  >
                    {text}
                  </button>
                ))}
              </div>
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
                <span className="spinner spinner-sm" />
                <span className="loading-text">思考中...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {error && <div className="alert alert-error mb-4">{error}</div>}

        <form onSubmit={handleSubmit} className="chat-input">
          <input
            ref={inputRef}
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
