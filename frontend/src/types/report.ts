export interface Report {
  id: string
  title: string
  report_type: string
  status: string
  parameters: Record<string, unknown>
  content: ReportContent | null
  content_url: string | null
  summary: string | null
  error_message: string | null
  created_at: string
}

export interface ReportContent {
  title: string
  year: number
  period: string
  period_label: string
  sections: Array<{
    name: string
    metric: string
    value: number
  }>
  summary: string
}

export interface PaginatedResponse<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}
