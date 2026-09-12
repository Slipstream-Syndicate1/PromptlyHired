// @vitest-environment jsdom
import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import InterviewPrep from './InterviewPrep.jsx'
import InterviewPrepCTA from './InterviewPrepCTA.jsx'

afterEach(() => { cleanup(); vi.useRealTimers() })
const context = {
  id: 7, title: 'Backend Engineer', company: 'Acme',
  startsAt: '2030-05-20T16:00:00Z', timezone: 'America/Edmonton',
  interviewType: 'not_sure', hasResume: true,
}
const plan = {
  id: 3, outdated: false, dailyMinutes: 60,
  tasks: [{ id: 't1', date: '2030-05-19', title: 'Practice SQL joins', minutes: 30,
    category: 'technical', instructions: 'Explain INNER and LEFT joins.',
    outcome: 'Write one example of each.', completed: false }],
  messages: [],
}
const callbacks = () => ({
  generate: vi.fn().mockResolvedValue(plan),
  setCompleted: vi.fn().mockResolvedValue(undefined),
  sendMessage: vi.fn().mockResolvedValue({ id: 'm1', role: 'assistant', content: 'Start with an INNER JOIN.' }),
})

describe('interview preparation', () => {
  it('only offers preparation at interview stage and schedules a missing date first', async () => {
    const user = userEvent.setup()
    const open = vi.fn(), schedule = vi.fn()
    const { rerender } = render(<InterviewPrepCTA status="applied" onOpen={open} onSchedule={schedule} />)
    expect(screen.queryByRole('button')).toBeNull()
    rerender(<InterviewPrepCTA status="interview" onOpen={open} onSchedule={schedule} />)
    await user.click(screen.getByRole('button', { name: /schedule interview/i }))
    expect(schedule).toHaveBeenCalledOnce()
    expect(open).not.toHaveBeenCalled()
    rerender(<InterviewPrepCTA status="interview" startsAt={context.startsAt} onOpen={open} onSchedule={schedule} />)
    await user.click(screen.getByRole('button', { name: /prepare with ai/i }))
    expect(open).toHaveBeenCalledOnce()
  })

  it('requires a daily budget and sends both-mode only on explicit generation', async () => {
    const user = userEvent.setup(), api = callbacks()
    render(<InterviewPrep context={context} actions={api} />)
    expect(api.generate).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Create my checklist' }).disabled).toBe(true)
    await user.selectOptions(screen.getByLabelText('Daily preparation time'), '60')
    await user.click(screen.getByRole('button', { name: 'Create my checklist' }))
    expect(api.generate).toHaveBeenCalledWith(expect.objectContaining({
      daily_minutes: 60, interview_type: 'not_sure', regenerate: false,
    }))
    expect(await screen.findByText('Practice SQL joins')).toBeTruthy()
  })

  it('does not permit an invalid custom budget', async () => {
    const user = userEvent.setup(), api = callbacks()
    render(<InterviewPrep context={context} actions={api} />)
    await user.selectOptions(screen.getByLabelText('Daily preparation time'), 'custom')
    await user.type(screen.getByLabelText('Minutes per day'), '0')
    expect(screen.getByRole('button', { name: 'Create my checklist' }).disabled).toBe(true)
    expect(api.generate).not.toHaveBeenCalled()
  })

  it('restores a checkbox when saving fails and preserves the visible plan', async () => {
    const user = userEvent.setup(), api = callbacks()
    api.setCompleted.mockRejectedValue(new Error('Could not save progress.'))
    render(<InterviewPrep context={context} initialPlan={plan} actions={api} />)
    const checkbox = screen.getByRole('checkbox', { name: /practice sql joins/i })
    await user.click(checkbox)
    expect(await screen.findByText('Could not save progress.')).toBeTruthy()
    await waitFor(() => expect(checkbox.checked).toBe(false))
    expect(screen.getByText('0 of 1 completed')).toBeTruthy()
  })

  it('retains a failed chat draft for retry without changing the checklist', async () => {
    const user = userEvent.setup(), api = callbacks()
    api.sendMessage.mockRejectedValueOnce(new Error('AI is busy. Try again.'))
    render(<InterviewPrep context={context} initialPlan={plan} actions={api} />)
    const input = screen.getByLabelText('Ask about your preparation')
    await user.type(input, 'How do I start?')
    await user.click(screen.getByRole('button', { name: 'Send question' }))
    expect(await screen.findByText('AI is busy. Try again.')).toBeTruthy()
    expect(input.value).toBe('How do I start?')
    await user.click(screen.getByRole('button', { name: 'Send question' }))
    expect(await screen.findByText('Start with an INNER JOIN.')).toBeTruthy()
    expect(input.value).toBe('')
    expect(screen.getByRole('checkbox').checked).toBe(false)
    expect(api.sendMessage.mock.calls[0][1].client_request_id)
      .toBe(api.sendMessage.mock.calls[1][1].client_request_id)
  })

  it('keeps an outdated checklist until the user explicitly regenerates', async () => {
    const user = userEvent.setup(), api = callbacks()
    render(<InterviewPrep context={context} initialPlan={{ ...plan, outdated: true }} actions={api} />)
    expect(screen.getByText(/interview details have changed/i)).toBeTruthy()
    expect(api.generate).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Update preparation plan' }))
    expect(api.generate).toHaveBeenCalledWith(expect.objectContaining({ regenerate: true }))
  })
})


it('requires actual same-day availability and refuses more than the remaining time', async () => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2030-05-20T15:30:00Z'))
  const user = userEvent.setup(), api = callbacks()
  render(<InterviewPrep context={context} actions={api} />)
  await user.selectOptions(screen.getByLabelText('Daily preparation time'), '60')
  const submit = screen.getByRole('button', { name: 'Create my checklist' })
  expect(submit.disabled).toBe(true)
  const available = screen.getByLabelText("Minutes available before today's interview")
  await user.type(available, '45')
  expect(submit.disabled).toBe(true)
  await user.clear(available)
  await user.type(available, '20')
  await user.click(submit)
  expect(api.generate).toHaveBeenCalledWith(expect.objectContaining({ same_day_minutes: 20 }))
})

it('leaves an expired interview plan readable but blocks generation', () => {
  const api = callbacks()
  render(<InterviewPrep context={{ ...context, startsAt: '2020-05-20T16:00:00Z' }} initialPlan={plan} actions={api} />)
  expect(screen.getByRole('button', { name: 'Update preparation plan' }).disabled).toBe(true)
  expect(screen.getByText('Practice SQL joins')).toBeTruthy()
  expect(api.generate).not.toHaveBeenCalled()
})

it('treats a null date as unscheduled rather than an expired interview', () => {
  render(<InterviewPrep context={{ ...context, startsAt: null }} actions={callbacks()} />)
  expect(screen.getByText(/schedule your interview in the calendar/i)).toBeTruthy()
  expect(screen.queryByText(/interview time has passed/i)).toBeNull()
})

it('explains when a checklist covers only a rolling preparation window', () => {
  render(<InterviewPrep context={context} initialPlan={{ ...plan, hasMoreDays: true }} actions={callbacks()} />)
  expect(screen.getByText(/covers only the dates shown/i)).toBeTruthy()
})
