import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import DocumentUpload from '../DocumentUpload'
import { api } from '../../api/client'

vi.mock('../../api/client')

describe('DocumentUpload', () => {
  const pdfFile = new File(['content'], 'report.pdf', { type: 'application/pdf' })

  beforeEach(() => {
    vi.resetAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const getFileInput = (container: HTMLElement) => container.querySelector('#file-input') as HTMLInputElement
  const getForm = (container: HTMLElement) => container.querySelector('form') as HTMLFormElement

  const uploadFile = (input: HTMLInputElement, file: File) => {
    fireEvent.change(input, { target: { files: [file] } })
  }

  it('shows error when submitting without file', async () => {
    const { container } = render(<DocumentUpload onUploaded={vi.fn()} />)
    fireEvent.submit(getForm(container))
    expect(await screen.findByText('请选择文件')).toBeInTheDocument()
  })

  it('shows error for unsupported file extension', async () => {
    const { container } = render(<DocumentUpload onUploaded={vi.fn()} />)
    const input = getFileInput(container)
    uploadFile(input, new File(['content'], 'report.txt', { type: 'text/plain' }))
    await waitFor(() => expect(input.files?.length).toBe(1))
    fireEvent.submit(getForm(container))
    expect(await screen.findByText('仅支持 csv/xlsx/xls/pdf 文件')).toBeInTheDocument()
  })

  it('uploads file and calls onUploaded', async () => {
    const onUploaded = vi.fn()
    const mockedApi = api as unknown as { post: ReturnType<typeof vi.fn> }
    mockedApi.post = vi.fn().mockResolvedValue({
      data: { data: { id: '2', filename: 'report.pdf' } },
    })

    const { container } = render(<DocumentUpload onUploaded={onUploaded} />)
    const input = getFileInput(container)
    uploadFile(input, pdfFile)
    await waitFor(() => expect(input.files?.length).toBe(1))
    fireEvent.submit(getForm(container))

    await waitFor(() => {
      expect(onUploaded).toHaveBeenCalledWith({ id: '2', filename: 'report.pdf' })
    })
    expect(mockedApi.post).toHaveBeenCalledWith(
      '/documents/upload',
      expect.any(FormData),
    )
  })

  it('shows error when upload fails', async () => {
    const mockedApi = api as unknown as { post: ReturnType<typeof vi.fn> }
    mockedApi.post = vi.fn().mockRejectedValue(new Error('upload failed'))

    const { container } = render(<DocumentUpload onUploaded={vi.fn()} />)
    const input = getFileInput(container)
    uploadFile(input, pdfFile)
    await waitFor(() => expect(input.files?.length).toBe(1))
    fireEvent.submit(getForm(container))

    expect(await screen.findByText('upload failed')).toBeInTheDocument()
  })
})
