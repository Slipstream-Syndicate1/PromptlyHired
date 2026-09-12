// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Calendar, { CalendarPreview } from './Calendar.jsx'
import { api } from '../api/client.js'
vi.mock('../api/client.js', () => ({ api: { listCalendarEvents: vi.fn(), listJobs: vi.fn(), createCalendarEvent: vi.fn(), updateCalendarEvent: vi.fn(), deleteCalendarEvent: vi.fn() } }))
vi.mock('../context/AuthContext.jsx', () => ({ useAuth: () => ({user: {id: 1}}) }))
const event = {id:'abc',title:'Engineer interview',date:'2099-01-01',time:'12:00',type:'interview',job_id:1,starts_at:'2099-01-01T12:00:00Z',timezone:'UTC'}
beforeEach(() => { vi.resetAllMocks(); localStorage.clear(); api.listCalendarEvents.mockResolvedValue([event]); api.listJobs.mockResolvedValue([{id:1,title:'Engineer',company:'Acme'}]) })
afterEach(cleanup)
const show = (component = <Calendar />) => render(<MemoryRouter>{component}</MemoryRouter>)
it('loads server events and links interview preparation', async () => { show(); expect((await screen.findByRole('link',{name:'Prepare with AI'})).getAttribute('href')).toBe('/interviews/abc/prep') })
it('requires explicit import and retains browser events on failure', async () => {
 localStorage.setItem('jobtrail.calendar_events',JSON.stringify([event])); api.createCalendarEvent.mockRejectedValue(new Error('Import failed')); show(); await screen.findByRole('link',{name:'Prepare with AI'}); expect(api.createCalendarEvent).not.toHaveBeenCalled(); await userEvent.click(screen.getByRole('button',{name:'Import events from this browser'})); expect(await screen.findByText('Import failed')).toBeTruthy(); expect(localStorage.getItem('jobtrail.calendar_events')).not.toBeNull()
})
it('preview reports load failure instead of claiming no events',async()=> {api.listCalendarEvents.mockRejectedValue(new Error('Calendar unavailable'));show(<CalendarPreview />);expect(await screen.findByRole('alert')).toHaveProperty('textContent','Calendar unavailable');expect(screen.queryByText('No upcoming deadlines or interviews.')).toBeNull()})
it('saves rescheduling and keeps the original when saving fails', async () => {
  const user=userEvent.setup(); api.updateCalendarEvent.mockRejectedValueOnce(new Error('Save failed')).mockResolvedValueOnce({...event,time:'13:00'}); show();
  await user.click(await screen.findByRole('button',{name:'Edit Engineer interview'}));
  const time=screen.getByLabelText('Time');
  // Time inputs model browser selection through a change event.
  const {fireEvent}=await import('@testing-library/react'); fireEvent.change(time,{target:{value:'13:00'}});
  await user.click(screen.getByRole('button',{name:'Save event'}));
  expect(await screen.findByText('Save failed')).toBeTruthy(); expect(time.value).toBe('13:00');
  await user.click(screen.getByRole('button',{name:'Save event'}));
  expect(await screen.findByRole('button',{name:'Add to calendar'})).toBeTruthy();
  expect(api.updateCalendarEvent).toHaveBeenCalledWith('abc',expect.objectContaining({time:'13:00',job_id:1,timezone:'UTC'}));
})
it('retains an event when deletion fails',async()=> {
  api.deleteCalendarEvent.mockRejectedValue(new Error('Cannot delete'));show();
  await userEvent.click(await screen.findByRole('button',{name:'Remove Engineer interview'}));
  expect(await screen.findByText('Cannot delete')).toBeTruthy();expect(screen.getByRole('link',{name:'Prepare with AI'})).toBeTruthy();
})
