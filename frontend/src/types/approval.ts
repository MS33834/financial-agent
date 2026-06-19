export interface Approval {
  id: string
  report_id: string
  report_title: string
  status: 'pending' | 'approved' | 'rejected'
  reviewer_id: string | null
  reviewer_name: string | null
  comments: string | null
  created_at: string
  updated_at: string
}
