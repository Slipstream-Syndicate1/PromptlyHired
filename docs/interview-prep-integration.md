# Calendar → interview preparation

## Integration

The calendar UI is the entry point while application status tracking is not yet available. Calendar events are account-owned API records. Interview events link to an existing job; job ownership is checked server-side through UserJob. The date, time, and timezone belong to the calendar event.

From Calendar, create an Interview event, select the job, supply its time, and choose Prepare with AI. The protected route `/interviews/:interviewId/prep` loads the authorized event and existing plan without generating anything. The user chooses technical, behavioral, or not sure (both), plus daily minutes, then explicitly generates a plan. Same-day interviews require actual available minutes before the interview.

Editing the calendar event can make a saved plan outdated. The user chooses when to regenerate; previous plan versions remain stored. Checklist changes and interview-specific messages persist server-side. No email, application-status update, calendar-task creation, or web search occurs through chat.

## Existing browser events

The previous calendar used one browser-wide localStorage key without an account owner. These records are not automatically imported. The calendar offers an explicit import action; new records use the authenticated account. Unlinked or untimed interview imports must be completed before preparation. Existing job descriptions and resumes stay backend-owned inputs, never trusted from the browser request.

## Files

- `frontend/src/pages/Calendar.jsx`: calendar CRUD, import, job selection, preparation links.
- `frontend/src/pages/InterviewPrep.jsx`: authorized loading, error/retry, API bindings.
- `frontend/src/components/interview-prep/`: setup, checklist, chat, responsive theme-aware styling.
- `frontend/src/api/client.js`: authenticated calendar/preparation calls.
- `backend/app/services/interview_prep.py`: deterministic scheduling and structured AI plan/chat services.
- `backend/app/interview_prep_schemas.py`: service contracts.
- Backend calendar/preparation routes and models own persistence, authorization, revision checks, and request deduplication.

## Future tracker integration

When application stages are added, persist the stage first, then show the existing InterviewPrepCTA for the interview stage. Its `onSchedule` should open the calendar form for that job, and `onOpen` should navigate to `/interviews/{eventId}/prep`. There is no separate preparation calendar. Multiple interview events can link to the same job and retain separate preparation histories.

## Local verification

```bash
# backend
source .venv/bin/activate
python -m alembic upgrade head
python -m pytest

# frontend, separate terminal
npm test
npm run build
```

Backend tests use a dedicated disposable Postgres database and stub AI. The existing development database must not be used as the test database. A live Gemini smoke test is separate from the deterministic suite and requires a configured key; never print the key or commit `.env`.
