interface BadgeProps {
  status: string
}

const STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  processing: '解析中',
  success: '成功',
  failed: '失败',
  needs_review: '待复核',
  reviewing: '审核中',
  approved: '已通过',
  rejected: '已驳回',
  draft: '草稿',
}

export default function Badge({ status }: BadgeProps) {
  const label = STATUS_LABELS[status] || status
  return <span className={`badge ${status}`}>{label}</span>
}
