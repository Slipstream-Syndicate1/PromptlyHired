// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { api } from '../api/client'
import InterviewPrepPage from './InterviewPrep.jsx'
vi.mock('../context/AuthContext.jsx', () => ({ useAuth: () => ({ user: { id: 1 } }) }))
vi.mock('../api/client', () => ({ api: {
  getInterviewPrep: vi.fn(), generateInterviewPrep: vi.fn(),
  setPrepTaskCompleted: vi.fn(), sendPrepMessage: vi.fn(),
} }))
afterEach(() => { cleanup(); vi.resetAllMocks() })
const context = { id: 'a', title: 'Engineer', company: 'Acme', startsAt: '2030-12-20T17:00:00Z', timezone: 'UTC', interviewType: 'not_sure', hasResume: false }
function mount() {
  return render(<MemoryRouter initialEntries={['/interviews/a/prep']}><Routes>
    <Route path="/interviews/:interviewId/prep" element={<InterviewPrepPage />} />
  </Routes></MemoryRouter>)
}
it('loads the authorized interview and generates only when asked', async () => {
  api.getInterviewPrep.mockResolvedValue({ context, plan: null })
  api.generateInterviewPrep.mockResolvedValue({ id: 'p', dailyMinutes: 30, tasks: [], messages: [] })
  const user = userEvent.setup()
  mount()
  await screen.findByText('Engineer · Acme')
  expect(api.generateInterviewPrep).not.toHaveBeenCalled()
  await user.selectOptions(screen.getByLabelText('Daily preparation time'), '30')
  await user.click(screen.getByRole('button', { name: 'Create my checklist' }))
  expect(api.generateInterviewPrep).toHaveBeenCalledWith('a', expect.objectContaining({ daily_minutes: 30 }))
})
it('shows a recoverable loading error with a calendar link', async () => {
  api.getInterviewPrep.mockRejectedValueOnce(new Error('Link this interview to a job first.'))
  api.getInterviewPrep.mockResolvedValue({ context, plan: null })
  const user = userEvent.setup()
  mount()
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Link this interview to a job first.')
  expect(screen.getByRole('link', { name: /calendar/i }).getAttribute('href')).toBe('/calendar')
  await user.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText('Engineer · Acme')).toBeTruthy()
})
