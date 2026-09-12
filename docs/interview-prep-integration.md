# Interview preparation integration handoff

## Current status

The backend scheduling/AI service and frontend setup/checklist/chat components are implemented and independently tested. They are **not exposed as a working website feature yet**. The canonical tracker/calendar records are absent from this branch. No duplicate calendar model, mock production tracker, persistence table, or public generation endpoint has been added.

## Calendar/tracker owner supplies

Implement `InterviewContextAdapter.get_interview_context(user_id=..., interview_id=...)` from `backend/app/services/interview_prep.py`. Return `InterviewContext` from `backend/app/interview_prep_schemas.py`, resolving the canonical interview and verifying application ownership server-side. Use `status='interview'` only for active interview applications; IDs and schedule revision are strings at this boundary. Supply timezone-aware `starts_at`, IANA `timezone`, title/company/description, and optional active resume/cached match summary. The authoritative calendar retains ownership of interview date/type and revision.

Mount the CTA after the tracker successfully saves a status change:

```jsx
<InterviewPrepCTA
  status={application.status}
  startsAt={interview?.startsAt}
  hasPlan={Boolean(prep)}
  onSchedule={openCalendarScheduling}
  onOpen={openPreparation}
/>
```

Import from `frontend/src/components/interview-prep/InterviewPrepCTA.jsx`. Normalize the canonical tracker status to lowercase `interview` in the integration layer. The CTA performs no model call.

## Preparation owner completes after the records are available

1. Add the plan/version/task/message tables and migration against the agreed interview ID.
2. Add authenticated routes described in `docs/plans/interview-preparation.md`. Enforce ownership, idempotency, rate limits, and calendar revision checks before/after generation. Ordinary GET and checklist updates never call AI. Store chat and checkbox changes in Postgres.
3. Call `generate_plan(context, PrepSettings(...))` and `answer_question(context, plan, message, history)` through those routes. Catch `AIRateLimited` before `AIError`; return 429, 503 for missing key, and 502 for provider/validation failure. All calls stay server-side.
4. Map persisted service output into the frontend presentation contract below. Register the authenticated route `/interviews/:interviewId/prep` and add API methods to the existing client. Do not expose a route that accepts an arbitrary browser-supplied InterviewContext as proof of ownership.
5. Run Postgres integration tests and the complete status → calendar → preparation → refresh flow.

## Frontend workspace contract

Import `InterviewPrep` from `frontend/src/components/interview-prep/InterviewPrep.jsx`. It includes its scoped theme-aware stylesheet. Mount it within the existing page shell; use `key={`${userId}:${interviewId}`}` so switching interviews/accounts discards old UI state. Load saved state before mounting. On calendar revision changes, reload/remount it with the current context and outdated flag.

```js
const context = {
  id: 'interview-id', title: 'Backend Engineer', company: 'Acme',
  startsAt: '2030-05-20T16:00:00Z', timezone: 'America/Edmonton',
  interviewType: 'not_sure', hasResume: true,
}
```

`initialPlan` is null or `{ id, outdated, dailyMinutes, summary, hasMoreDays, tasks, messages }`. Preserve service `summary` and map `has_more_days` to `hasMoreDays` so the user sees when the plan covers only an initial window. Flatten service `days` into tasks: `{ ...task, date: day.date, outcome: task.expected_outcome }`. Each task retains the persisted server ID and boolean completed state. Messages are `{ id, role, content }` with role user/assistant. Populate the latest conversation page initially; pagination UI is a follow-up when persistence lands.

Required async `actions`:

- `generate({ daily_minutes, interview_type, same_day_minutes?, regenerate, client_request_id })` returns the persisted frontend plan shape. Same-day input is actual available minutes. Strip transport-only fields before constructing PrepSettings; update canonical interview type through its owner if necessary.
- `setCompleted(planId, taskId, completed)` persists the checkbox or throws. The UI rolls back a failed save.
- `sendMessage(planId, { message, client_request_id })` persists both messages and returns `{ id, role: 'assistant', content }`. Map service `answer` to stored assistant content. The UI retains a failed draft and reuses the request ID for retry.

Render all content as text, not raw HTML. The current workspace never changes calendar records or silently regenerates. New plan IDs reset the chat display; old versions stay server-side.

## Verification

```bash
# From frontend
npm test
npm run build

# From backend; these tests use stubbed AI and do not require Postgres
.venv/bin/python -m pytest unit_tests/test_interview_prep_schedule.py -q
```

A frontend build alone does not demonstrate live integration: the components are not imported by a production route until the calendar contract is connected. No live Gemini requests were made during these tests.
