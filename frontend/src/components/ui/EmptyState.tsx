interface EmptyStateProps {
  title?: string
  description?: string
}

export default function EmptyState({
  title = '暂无数据',
  description = '当前列表为空，开始添加第一条记录吧。',
}: EmptyStateProps) {
  return (
    <div className="empty-state">
      <svg
        className="empty-state-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      >
        <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
      <h4 className="empty-state-title">{title}</h4>
      <p className="empty-state-desc">{description}</p>
    </div>
  )
}
