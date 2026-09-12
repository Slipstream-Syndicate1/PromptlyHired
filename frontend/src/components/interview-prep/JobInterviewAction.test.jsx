// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import JobInterviewAction from './JobInterviewAction.jsx'
import { api } from '../../api/client'
vi.mock('../../api/client', () => ({ api: { listCalendarEvents: vi.fn(), setJobStatus: vi.fn() } }))
afterEach(() => { cleanup(); vi.resetAllMocks() })
it('offers scheduling after the Interview status has successfully saved', async () => {
  api.listCalendarEvents.mockResolvedValue([])
  api.setJobStatus.mockResolvedValue({ id: 5, status: 'interview' })
  const user = userEvent.setup()
  render(<MemoryRouter><JobInterviewAction job={{ id: 5, status: 'applied' }} onUpdate={() => {}} /></MemoryRouter>)
  await user.selectOptions(screen.getByLabelText('Application status'), 'interview')
  expect(await screen.findByRole('link', { name: 'Schedule interview' })).toHaveProperty('href', expect.stringContaining('/calendar?job=5'))
})
it('links an existing interview directly to its preparation', async () => {
  api.listCalendarEvents.mockResolvedValue([{ id: 'event1', job_id: 5, type: 'interview', starts_at:'2030-12-20T12:00:00Z' }])
  render(<MemoryRouter><JobInterviewAction job={{ id: 5, status: 'interview' }} onUpdate={() => {}} /></MemoryRouter>)
  const link = await screen.findByRole('link', { name: 'Prepare with AI' })
  expect(link.getAttribute('href')).toBe('/interviews/event1/prep')
})
