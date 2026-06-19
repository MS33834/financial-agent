import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import DocumentList from '../DocumentList'
import type { Document } from '../../types/document'

const documents: Document[] = [
  {
    id: '1',
    filename: 'invoice.pdf',
    status: 'needs_review',
    confidence: 0.85,
    parse_result: null,
    error_message: null,
    created_at: '2024-01-01T00:00:00Z',
  },
]

describe('DocumentList', () => {
  it('renders needs_review status as 待复核', () => {
    render(<DocumentList documents={documents} onSelect={vi.fn()} />)
    expect(screen.getByText('待复核')).toBeInTheDocument()
  })
})
