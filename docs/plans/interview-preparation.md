# P: Interview preparation assistant — proposed implementation plan

Status: requirements agreed in conversation; technical contracts proposed for coordination. Planning only; no application code changed.

## Outcome and agreed scope

When an application moves from Applied to Interview, show an optional Prepare with AI action. The calendar stores the interview date/time. The user chooses technical, behavioral, or not sure (both), plus a daily preparation budget: 30, 60, 120, or a custom number of minutes. Generate a personalized daily checklist using the job description and time remaining, with resume evidence and existing match gaps when available. Keep a follow-up AI conversation attached to that interview. Checklist items are not calendar events.

No automatic model call on a status change, page load, or calendar update. Internet job discovery, tracker implementation, calendar implementation, branding, and document templates belong to the other workstreams.

## Existing code and approach

The current application has React/Vite routes, an authenticated API client with token refresh, FastAPI, SQLAlchemy/Postgres, Alembic, resume text, skill profiles, cached JobMatch results, and a server-side Gemini integration in backend/app/services/ai.py. There are no application-stage, interview-calendar, or conversation models in the inspected models.py. UserJob records ownership of added jobs; shared Job rows are not application records. History currently represents generated documents.

Recommended: a dedicated preparation page backed by persisted plans and conversations, using ordinary JSON requests and the existing Gemini provider. This offers a usable checklist on desktop and mobile and survives refreshes. A chat-only popup would be quicker but makes daily progress awkward; streaming or autonomous tool execution adds complexity without improving the initial checklist workflow.

## User experience

1. After a successful transition to Interview, display a callout with Prepare with AI. Keep the action accessible on the application afterward; it must not exist only in a temporary toast.
2. If no interview has been scheduled, link to the calendar scheduling flow and return afterward. Do not guess an interview date.
3. Open setup showing the selected interview, date/time and timezone, interview type, and daily minutes. Default type is not sure; require the user to choose a time budget.
4. Generate only on explicit submission. Show loading, retryable failure, and missing-data states.
5. Open /interviews/:interviewId/prep. Show role, interview countdown, daily budget, progress, dated checklist sections, estimated task minutes, and an interview-specific chat.
6. Desktop: checklist and chat in two columns. Mobile: stacked sections or accessible Checklist/Ask AI tabs. Reuse existing styles and future theme variables; do not create an independent brand or theme toggle.
7. Persist checkbox changes immediately, with rollback and an error message if saving fails. Chat answers can explain or suggest changes but cannot silently rewrite the checklist.
8. An interview-date, resume, job-description, type, or budget change marks the plan outdated. Offer explicit regeneration. Keep previous plan versions and their completion history; the new version starts a fresh checklist.

## Tracker/calendar integration contract to agree with teammates

The tracker owns application identity and status. The calendar owns interview identity and scheduling. P reads those records through a backend adapter, never trusts browser-supplied ownership or job descriptions, and does not duplicate scheduling state as a new authoritative calendar.

Proposed adapter: get_interview_context(db, user_id, interview_id) returns application_id, job_id, status, starts_at, timezone, interview_type, schedule_revision. It must verify ownership through the application, even though jobs are shared. An application can have multiple interview rounds; each interview gets its own preparation history.

- starts_at: timezone-aware timestamp, stored in UTC.
- timezone: IANA timezone used to assign local checklist dates.
- interview_type: technical | behavioral | not_sure.
- schedule_revision: changes whenever the schedule/type changes.
- Cancellation or removal from the interview stage stops new generation; existing preparation remains readable by its owner.

Frontend integration component: InterviewPrepCTA({ interviewId, applicationStatus, startsAt, prepState }). The tracker embeds it after saving status; the calendar can link to the same preparation route. Exact tracker/calendar source files will be selected when those workstreams land. Until then, develop against backend test fixtures matching this contract, not a production mock tracker.

## Scheduling and AI responsibilities

Python constructs valid local dates and daily minute budgets. Gemini generates prioritized topics and activities within those supplied slots; it does not invent the calendar or calculate the deadline.

- Validate custom daily minutes as an integer from 15 through 480 (proposed MVP limit).
- Require a future interview timestamp and nonempty job description. A missing resume permits a job-description-only plan with a visible personalization notice; do not trigger resume analysis automatically.
- Start with today in the interview timezone. Use dates before the interview day by default. For a same-day interview, ask the user for minutes actually available before it and cap them by remaining clock time; do not assume the entire day is available.
- For longer schedules, use a rolling window of at most 14 preparation days and offer an explicit next-window plan. Show the covered date range rather than implying it covers the entire period.
- Technical mode emphasizes requirements and role-appropriate exercises. Behavioral mode emphasizes evidence-backed STAR story practice. Not sure covers both, allocating emphasis using the job description.
- Each task has a title, category, priority, minutes, instructions, and a practice question or tangible expected outcome. Explain which job requirement motivates it. Avoid claiming to know the employer's actual questions.
- Use the active resume and only an already-cached match for that resume. Treat an unevidenced skill as a preparation priority, not proof the person lacks it.
- Validate output dates, task counts, positive durations, and total minutes per day before persistence. Reject malformed output with a retryable error; never save an over-budget plan.
- Store server-generated task IDs. Keep model output structured through Pydantic, following the existing provider approach.

## Persistence and API proposal

Add InterviewPrepPlan: id, user_id, interview_id, version, resume_id (nullable), source fingerprint, schedule revision, interview timestamp/timezone snapshot, type, daily_minutes, structured plan JSON, model_used, created_at. Fingerprint includes relevant input snapshots and the preparation window.

Add InterviewPrepTask: id, plan_id, scheduled_date, position, structured task content, completed_at. Task records are the checklist source of truth; plan JSON records the generated original.

Add InterviewPrepMessage: id, plan_id, role (user/assistant), content, client_request_id, created_at. Bound requests to 2,000 characters and include only the latest 10 messages plus the plan and bounded source context in a model request. Older messages remain readable through pagination.

Proposed endpoints, all authenticated and ownership-checked:

| Endpoint | Behavior |
| --- | --- |
| GET /api/interviews/{id}/prep | Current plan, task progress, setup context, and outdated flag; no model call |
| POST /api/interviews/{id}/prep | Generate with daily_minutes, interview_type, and client_request_id; return persisted plan |
| PATCH /api/interview-prep/{planId}/tasks/{taskId} | Set completed true/false, checking task belongs to plan |
| GET /api/interview-prep/{planId}/messages | Paginated saved conversation |
| POST /api/interview-prep/{planId}/messages | Send message with client_request_id; persist and return response |

Use a separate explicit regenerate flag for replacing the current version. Reuse an unchanged existing plan without a model call. Enforce request-ID uniqueness and one in-flight generation per interview so double clicks/retries do not duplicate model calls. Do not hold a database transaction open during a provider request. On return, recheck the calendar revision before saving; reject a stale generation with 409. Failed requests must release the in-flight state and be retryable.

Handle provider quota as HTTP 429, missing configuration as 503, and other provider/output failures as 502. The current document router catches AIError broadly, so explicitly catch AIRateLimited first for these new routes. Apply existing AI limits and add an authenticated-user bucket; the current limiter keys by IP. Keep provider keys server-side, enforce bounded output/context, and avoid logging resume text or conversations.

Chat is advisory: no sending emails, changing application stages, modifying calendar events, or browsing the web. Render text safely without raw HTML. Fence resume, job description, and persisted conversational context as untrusted data, keeping system rules separate. Delimiters supplement authorization and structured validation; they are not the security boundary.

## Delivery sequence and files

- [ ] 1. Agree the integration contract with tracker/calendar owners. Record the canonical application/interview model names and adapter mapping before adding foreign keys. Verify an owner can resolve an interview and another user cannot.
- [ ] 2. Add persistence in backend/app/models.py, a migration under backend/alembic/versions/, and backend/app/interview_prep_schemas.py. Add tests in backend/tests/test_interview_prep.py for ownership, plan versioning, task persistence, request deduplication, and independent interview rounds. Check the latest Alembic head before creating the migration.
- [ ] 3. Add backend/app/services/interview_prep.py for scheduling, source context, structured generation, and bounded chat. Reuse the current Gemini client through a small public wrapper in backend/app/services/ai.py instead of duplicating SDK setup. Add backend/tests/test_interview_prep_schedule.py for timezone/day boundaries, same-day limits, expired dates, and daily budgets; stub every provider call.
- [ ] 4. Add backend/app/routers/interview_prep.py and register it in backend/app/main.py. Extend backend/app/rate_limit.py for authenticated-user AI limiting. Test GET makes no model calls, regeneration is explicit, concurrent requests are deduplicated, revision changes reject stale output, failures recover, and 429/502/503 responses are preserved.
- [ ] 5. Add API methods in frontend/src/api/client.js and a protected route in frontend/src/App.jsx. Add frontend/src/pages/InterviewPrep.jsx and frontend/src/components/interview-prep/{InterviewPrepCTA,PrepSetup,PrepChecklist,PrepChat}.jsx. Add responsive rules in frontend/src/styles.css. Keep setup, checkbox, and chat failure states independent.
- [ ] 6. Wire the CTA into the real tracker and the preparation link into calendar interview details. Confirm changing status exposes the action but makes no AI call. Verify a missing date routes to scheduling and a rescheduled interview offers regeneration without deleting prior progress.
- [ ] 7. Validate against real Postgres with stubbed AI using python -m pytest from backend, and npm run build from frontend. Add component interaction tests with Vitest/React Testing Library if no team frontend test harness has landed; cover setup validation, failed-checkbox rollback, and chat retry. Manually check keyboard navigation, labeled controls, screen-reader status announcements, narrow mobile layout, wide desktop layout, reload persistence, and logout/account isolation.

## Demonstration and acceptance

Create an application for a backend role with Python/SQL requirements. Move Applied to Interview, schedule five days ahead, choose not sure and 60 minutes/day, and click Prepare with AI. The saved checklist covers technical and behavioral practice without exceeding 60 minutes on any date. Mark a task complete, reload, ask a question about that task, and reopen the saved conversation. Reschedule the interview for tomorrow and explicitly regenerate a shorter plan. Verify the old version remains stored and no request exposes another user's plan.

Completion means this flow works with actual tracker/calendar records, not only test fixtures. No paid provider tier or new SDK version is assumed; implementation should use the installed provider interface and verify the configured model through the project's doctor command when doing an authorized live smoke test.
