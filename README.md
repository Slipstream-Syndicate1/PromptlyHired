# PromptlyHired

A job application organizer. Find jobs, see how well you match them, make a
resume and cover letter for each one, and keep track of every application until
you hear back.

**Runs for free.** Every service it uses has a free tier, and no paid APIs are involved.

It's one React PWA and one FastAPI backend at one URL. It works on a phone,
laptop or tablet, and you can install it to your home screen. There are no native
apps. See [CLAUDE.md](CLAUDE.md) for the full spec and the reasoning behind the
architecture.

## What it does

**Find jobs**
- **Live job feed** on the Jobs page, from Adzuna and Himalayas. Search by keywords
  and filter by location, job type, remote only and date posted.
- **Recommended for you** at the top of the Jobs page: jobs that fit the skills on
  your resume. The best matches are checked with AI and the top three are shown.
  Set your preferred location and whether to include remote jobs on Profile.
- **Paste a link** to any other posting (LinkedIn, Indeed, a company careers page),
  or paste the advert text for sites that block fetching.

**See how well you match**
- Open a job to get a match percentage, the requirements you meet and the ones
  you're missing. Results are saved, so reopening a job is free.

**Resumes and cover letters**
- **Master resume** on Profile: your base resume in a classic one-page layout.
  **Fill from uploaded CV** fills it in for you, so you only check and fix it.
  Whatever you save here is where every job's resume starts.
- For each job, either **Start from master resume** (an exact copy, no AI) or
  **Tailor resume with AI**. Tailoring rewords and reorders your bullets for the
  job. It never changes names, employers, dates or locations.
- **Create cover letter** writes one for the job from your resume and the job description.
- Edit everything in the app with a live preview, then export to PDF. Edits for
  one job never change your master resume.

**Track applications**
- Mark a job as applied and move it through the stages: applied, online
  assessment, interview, then offer, rejected or withdrawn. Each change is kept
  as history, with a note on what happened.
- Log calls, emails and meetings with the employer, and set a next step with a date.
- **Log an application** for jobs you applied to somewhere else.
- **Saved** keeps the jobs you've shortlisted. **History** keeps every job you've
  made documents for.

**Everything else**
- A home dashboard, a calendar, and a guided tour the first time you sign in.
- Light and dark themes.
- Forgot password by email.

## Running locally

```bash
docker compose up -d                                          # Postgres on :5433

cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
cp .env.example .env                                          # then fill in the keys below
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload      # :8000

cd ../frontend
npm install && cp .env.example .env
npm run dev                                                    # :5173
```

If the project folder is synced by OneDrive, `--reload` can miss file changes.
Restart the backend after switching branches.

### Keys

| Variable | What it's for | Without it |
| --- | --- | --- |
| `GEMINI_API_KEY` | Match analysis, resumes, cover letters, recommendations scoring | **No AI features work.** Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Local jobs in the feed | The feed only shows remote jobs from Himalayas. Free key at [developer.adzuna.com](https://developer.adzuna.com). |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Password reset emails | In development the reset link is written to the backend log. In production no reset email can be sent. A Gmail App Password works. |

Optional settings:
- `JOB_COUNTRY` sets the Adzuna country.
- `FEED_CACHE_MINUTES` (default 180) sets how long identical searches are served from cache.
- `GEMINI_MODEL` (default `gemini-3.8-flash`) and `GEMINI_FALLBACK_MODELS` set the AI models to use.

Each free Gemini model allows about 20 requests a day. When one runs out, the app
moves on to the next model in the list.

Check what's actually wired up:

```bash
curl localhost:8000/health                       # readiness flags
.venv/Scripts/python.exe -m app.tasks doctor     # connects to each service for real
```

The doctor checks the database, migrations, every AI model in the chain, file
storage, the job feed, email and the frontend URLs.

## What it costs

Nothing:
- **AI:** Gemini's free tier.
- **Jobs:** Adzuna's free developer key (250 calls a day) and Himalayas, which needs no key.
- **Hosting:** the free tiers of Render, Netlify and Cloudflare R2.

The real limit is the number of requests, not money. So the app:
- parses job pages itself before calling the model
- saves every AI result
- serves repeated job searches from a shared cache
- says "try again later" when a quota runs out, instead of failing

## Security

Job descriptions come from websites written by strangers and are fed to an AI
model, so two concerns dominate.

**SSRF.** When you paste a link, the server fetches that URL. Private, loopback
and link-local addresses (like cloud metadata at `169.254.169.254`) are refused.
Only http(s) is allowed, and every redirect is checked again.

**Prompt injection:**
- Job adverts are wrapped in delimiters and marked as data, never instructions,
  and they never go in the system prompt.
- Every AI call must return a fixed schema, and the match percentage is clamped to
  0–100 on the server.
- When the AI tailors your resume, it can only send back edits to your master
  resume. Names, employers, dates and locations are copied from your master on the
  server, so a poisoned advert can't change them.
- AI output never triggers an action on its own. Documents are drafts you review
  and edit, and nothing is ever sent on your behalf.
- Your resume goes to the model because the feature needs it, and nowhere else.
  It is never logged in full.

Also in place:
- bcrypt password hashing
- short-lived access tokens with rotating refresh tokens, stored as hashes
- single-use password reset links that expire after 30 minutes
- rate limits on sign-in and AI endpoints
- Pydantic validation on every endpoint, and SQLAlchemy ORM only
- CORS locked to the real site, and HTTPS

## Tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest        # needs the docker-compose Postgres
python ../scripts/audit_spec.py           # checks the code against CLAUDE.md
```

Tests run against real Postgres, never SQLite, because the schema uses native
enums, JSONB and server-side defaults. **Every AI call is stubbed**, so the tests
never use up your quota. The injection defenses and score clamping are tested directly.

## Deploying

See **[DEPLOYMENT.md](DEPLOYMENT.md)**:
- Netlify for the frontend.
- Render for the API and Postgres. Migrations run automatically on start.
- Cloudflare R2 for uploaded resumes.

In production the API refuses to start if `JWT_SECRET` is left at its default,
`CORS_ORIGINS` is a wildcard or not HTTPS, or `APP_BASE_URL` is http. Settings that
only turn features off (no AI key, no email, local file storage) are logged as
`DEGRADED` and shown on `/health`.

## Known limits

- The calendar saves events in your browser only, so they don't sync between devices yet.
- Adzuna only gives short description snippets, so matches on Adzuna jobs work
  from less text. The Apply button always opens the full listing.
- Resume PDFs are one page. The app warns you if yours runs longer.
- The free AI tier is small. With several people using it at once, some requests
  will wait for the quota to reset.
