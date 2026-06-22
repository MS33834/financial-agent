import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import { api } from '../api/client.ts'
import NavBar from '../components/NavBar.tsx'
import Loading from '../components/ui/Loading.tsx'
import Badge from '../components/ui/Badge.tsx'
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip as ReTooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts'
import { useAuth } from '../context/AuthContext.tsx'

interface DashboardSummary {
  greeting: string
  report_count: number
  pending_approval_count: number
  document_count: number
  recent_reports: Array<{
    id: string
    title: string
    status: string
    created_at: string
  }>
  recent_documents: Array<{
    id: string
    filename: string
    status: string
    created_at: string
  }>
  report_status_distribution: Record<string, number>
  document_status_distribution: Record<string, number>
  recent_activities: Array<{
    id: string
    action: string
    resource: string
    result: string
    created_at: string
  }>
  approval_trend: Array<{
    date: string
    count: number
  }>
}

const REPORT_STATUS_COLORS: Record<string, string> = {
  draft: '#9ca3af',
  pending: '#f59e0b',
  processing: '#3b82f6',
  reviewing: '#a855f7',
  approved: '#22c55e',
  rejected: '#ef4444',
  published: '#06b6d4',
  failed: '#dc2626',
}

const DOCUMENT_STATUS_COLORS: Record<string, string> = {
  pending: '#f59e0b',
  processing: '#3b82f6',
  success: '#22c55e',
  needs_review: '#a855f7',
  failed: '#ef4444',
}

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  pending: '待处理',
  processing: '解析中',
  reviewing: '待复核',
  approved: '已通过',
  rejected: '已驳回',
  published: '已发布',
  failed: '失败',
  success: '成功',
  needs_review: '需复核',
}

const SUGGESTIONS = [
  '本月收入是多少？',
  '2025年Q2净利润',
  '生成利润表',
  '待审批报告有哪些？',
]

const ROLE_TIPS: Record<string, string> = {
  admin: '管理员提示：可在审计日志中查看所有关键操作记录。',
  finance_manager: '财务经理提示：上传新文档或创建报告即可启动自动化分析流程。',
  auditor: '审计员提示：待复核报告已集中展示在审批页面。',
  viewer: '查看者提示：使用智能问答可基于已有报表快速查数。',
}

const ACTION_ICONS: Record<string, string> = {
  'report.create': '📊',
  'report.approval': '✅',
  'document.upload': '📄',
  'document.parse': '🔍',
  'query.nl2sql': '💬',
  'user.login': '🔑',
}

export default function DashboardPage() {
  const { username, role } = useAuth()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchSummary = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.get('/dashboard/summary')
      setSummary(response.data.data)
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.message || '加载仪表盘失败')
      } else {
        setError('加载仪表盘失败')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSummary()
  }, [])

  const reportChartData = useMemo(
    () =>
      summary
        ? Object.entries(summary.report_status_distribution).map(([status, count]) => ({
            name: STATUS_LABELS[status] || status,
            value: count,
            color: REPORT_STATUS_COLORS[status] || '#9ca3af',
          }))
        : [],
    [summary],
  )

  const documentChartData = useMemo(
    () =>
      summary
        ? Object.entries(summary.document_status_distribution).map(([status, count]) => ({
            name: STATUS_LABELS[status] || status,
            value: count,
            color: DOCUMENT_STATUS_COLORS[status] || '#9ca3af',
          }))
        : [],
    [summary],
  )

  const formatTime = (value: string) =>
    new Date(value).toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })

  const formatAction = (action: string) => {
    const labels: Record<string, string> = {
      'report.create': '创建报告',
      'report.approval.approve': '通过报告',
      'report.approval.reject': '驳回报告',
      'report.approval.modify': '退回修改',
      'document.upload': '上传文档',
      'document.parse.success': '解析文档',
      'document.parse.fail': '文档解析失败',
      'query.nl2sql': '智能查询',
      'user.login': '用户登录',
    }
    return labels[action] || action
  }

  const canApprove = role === 'admin' || role === 'auditor'
  const pendingCount = summary?.pending_approval_count || 0

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h1>工作台</h1>
          <p className="text-muted text-sm">
            {summary?.greeting || '欢迎回来'}
            {username ? `，${username}` : ''}
          </p>
        </div>
        <div className="actions">
          <NavBar />
          <button className="secondary" onClick={fetchSummary}>
            刷新
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error mb-4">{error}</div>}

      {loading ? (
        <Loading text="加载仪表盘中..." />
      ) : summary ? (
        <>
          <div className="stat-grid">
            <Link to="/reports" className="stat-card">
              <div className="stat-icon reports">📊</div>
              <div className="stat-value">{summary.report_count}</div>
              <div className="stat-label">财务报告</div>
              <div className="stat-hint">点击查看全部</div>
            </Link>
            <Link to="/approvals" className="stat-card">
              <div className="stat-icon approvals">✅</div>
              <div className="stat-value">{summary.pending_approval_count}</div>
              <div className="stat-label">待审批</div>
              <div className="stat-hint">需要人工复核</div>
            </Link>
            <Link to="/documents" className="stat-card">
              <div className="stat-icon documents">📄</div>
              <div className="stat-value">{summary.document_count}</div>
              <div className="stat-label">文档解析</div>
              <div className="stat-hint">上传与解析记录</div>
            </Link>
            <Link to="/agent" className="stat-card">
              <div className="stat-icon agent">🤖</div>
              <div className="stat-value">AI</div>
              <div className="stat-label">智能问答</div>
              <div className="stat-hint">自然语言查数</div>
            </Link>
          </div>

          <div className="dashboard-grid">
            <div className="card card-wide">
              <h3 className="card-title">最近 7 天报告趋势</h3>
              {summary.approval_trend.length === 0 ? (
                <p className="text-muted text-sm">暂无数据</p>
              ) : (
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={summary.approval_trend} margin={{ top: 8, right: 16, bottom: 8, left: -16 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
                      <ReTooltip />
                      <Bar dataKey="count" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="card">
              <h3 className="card-title">审批概览</h3>
              {pendingCount === 0 ? (
                <p className="text-muted text-sm">当前没有待审批的报告</p>
              ) : (
                <div className="approval-summary">
                  <div className="approval-count">{pendingCount}</div>
                  <div className="approval-desc">份报告等待复核</div>
                  <Link to="/approvals" className="btn mt-4">
                    立即处理
                  </Link>
                </div>
              )}
            </div>

            <div className="card">
              <h3 className="card-title">最近报告</h3>
              {summary.recent_reports.length === 0 ? (
                <p className="text-muted text-sm">暂无报告</p>
              ) : (
                <ul className="activity-list">
                  {summary.recent_reports.map((report) => (
                    <li key={report.id}>
                      <div className="activity-main">
                        <Link to={`/reports?id=${report.id}`} className="link">
                          {report.title}
                        </Link>
                        <Badge status={report.status} />
                      </div>
                      <div className="activity-time">{formatTime(report.created_at)}</div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="card">
              <h3 className="card-title">最近文档</h3>
              {summary.recent_documents.length === 0 ? (
                <p className="text-muted text-sm">暂无文档</p>
              ) : (
                <ul className="activity-list">
                  {summary.recent_documents.map((doc) => (
                    <li key={doc.id}>
                      <div className="activity-main">
                        <span>{doc.filename}</span>
                        <Badge status={doc.status} />
                      </div>
                      <div className="activity-time">{formatTime(doc.created_at)}</div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="card">
              <h3 className="card-title">报告状态分布</h3>
              {reportChartData.length === 0 ? (
                <p className="text-muted text-sm">暂无数据</p>
              ) : (
                <>
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={reportChartData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={80}
                          paddingAngle={2}
                        >
                          {reportChartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <ReTooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="legend">
                    {reportChartData.map((item) => (
                      <div key={item.name} className="legend-item">
                        <span className="legend-dot" style={{ background: item.color }} />
                        <span>
                          {item.name}: {item.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="card">
              <h3 className="card-title">文档状态分布</h3>
              {documentChartData.length === 0 ? (
                <p className="text-muted text-sm">暂无数据</p>
              ) : (
                <>
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={documentChartData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={80}
                          paddingAngle={2}
                        >
                          {documentChartData.map((entry, index) => (
                            <Cell key={`cell-doc-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <ReTooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="legend">
                    {documentChartData.map((item) => (
                      <div key={item.name} className="legend-item">
                        <span className="legend-dot" style={{ background: item.color }} />
                        <span>
                          {item.name}: {item.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div className="card">
              <h3 className="card-title">快捷操作</h3>
              <div className="quick-actions">
                <Link to="/reports" className="btn">
                  创建报告
                </Link>
                <Link to="/documents" className="btn secondary">
                  上传文档
                </Link>
                <Link to="/agent" className="btn secondary">
                  智能问答
                </Link>
                {canApprove && (
                  <Link to="/approvals" className="btn secondary">
                    去审批
                  </Link>
                )}
              </div>
            </div>

            <div className="card card-wide">
              <h3 className="card-title">最近动态</h3>
              {summary.recent_activities.length === 0 ? (
                <p className="text-muted text-sm">暂无动态</p>
              ) : (
                <ul className="activity-list">
                  {summary.recent_activities.map((activity) => (
                    <li key={activity.id}>
                      <div className="activity-main">
                        <div className="activity-title">
                          <span className="activity-icon">
                            {ACTION_ICONS[activity.action.split('.').slice(0, 2).join('.')] || '•'}
                          </span>
                          <span>{formatAction(activity.action)}</span>
                        </div>
                        <Badge status={activity.result === 'success' ? 'approved' : 'failed'} />
                      </div>
                      <div className="activity-resource">{activity.resource}</div>
                      <div className="activity-time">{formatTime(activity.created_at)}</div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="card">
              <h3 className="card-title">智能问答示例</h3>
              <div className="suggestion-chips">
                {SUGGESTIONS.map((text) => (
                  <Link key={text} to={`/agent?question=${encodeURIComponent(text)}`} className="chip">
                    {text}
                  </Link>
                ))}
              </div>
            </div>

            <div className="card card-tip">
              <h3 className="card-title">使用提示</h3>
              <p className="text-sm">{ROLE_TIPS[role || 'viewer'] || ROLE_TIPS.viewer}</p>
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
