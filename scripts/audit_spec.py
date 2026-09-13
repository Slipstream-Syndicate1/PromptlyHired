"""Audit the codebase against every concrete claim in CLAUDE.md.

Run with: python scripts/audit_spec.py
Exits non-zero if the implementation has drifted from the spec.
"""

import re
import sys
from pathlib import Path

# Repo root, resolved from this file so it works in CI and on any machine.
ROOT = Path(__file__).resolve().parent.parent
BE, FE = ROOT / "backend", ROOT / "frontend"

issues, checks = [], 0


def read(p):
    return (ROOT / p).read_text(encoding="utf-8", errors="replace")


def read_if(p):
    """A file that may or may not exist, for checks that follow code between files."""
    path = ROOT / p
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def ck(section, label, cond, detail=""):
    global checks
    checks += 1
    if not cond:
        issues.append((section, label, detail))
    print(f"  [{'ok' if cond else 'MISSING'}] {label}" + (f"  -- {detail}" if detail and not cond else ""))


def head(t):
    print(f"\n== {t} ==")


models = read("backend/app/models.py")
schemas = read("backend/app/schemas.py")
ai = read("backend/app/services/ai.py")

head("Data model - every entity named in CLAUDE.md")
FIELDS = {
    "User": ["email", "password_hash", "name", "profile_picture_url", "created_at"],
    "Resume": ["user_id", "file_url", "original_filename", "content_type", "is_active", "uploaded_at"],
    "SkillProfile": ["resume_id", "skills", "job_titles", "domains", "locations",
                     "seniority", "years_experience", "summary", "generated_at", "model_used"],
    "Company": ["name", "logo_url", "short_description"],
    "Job": ["company_id", "title", "location", "salary_range", "url", "posted_date",
            "description", "source_api", "external_id", "source_publisher"],
    "JobMatch": ["user_id", "job_id", "resume_id", "match_percentage", "requirements_met",
                 "requirements_missing", "rationale", "generated_at", "model_used"],
    "SavedJob": ["user_id", "job_id", "saved_at"],
    "GeneratedDocument": ["user_id", "job_id", "resume_id", "kind", "content",
                          "edited_content", "created_at", "updated_at", "model_used"],
}
for cls, fields in FIELDS.items():
    m = re.search(rf"class {cls}\(Base\):(.*?)(?=\nclass |\Z)", models, re.S)
    body = m.group(1) if m else ""
    ck("model", f"{cls} exists", bool(m))
    for f in fields:
        ck("model", f"{cls}.{f}", f"{f}:" in body)

head("Removed tracker domain stays removed")
# Application tracking was brought back (see "Application tracking" below).
# The rest of the old tracker domain stays gone.
for gone in ["class Follow(", "NotifiedJob", "PushSubscription", "JobPreferences"]:
    ck("removed", f"no {gone.rstrip('(')}", gone not in models)
for path in ["backend/app/services/push.py", "backend/app/services/reminders.py",
             "backend/app/services/analytics.py", "frontend/src/pages/Applications.jsx",
             "frontend/src/pages/Analytics.jsx"]:
    ck("removed", f"{path} deleted", not (ROOT / path).exists())

# Reminder emails came back with application tracking, so the file is allowed
# again - but only as reminders about the user's own tracked applications.
notifications = read_if("backend/app/services/notifications.py")
if notifications:
    head("Follow-up reminders")
    ck("reminders", "about tracked applications, not a job digest",
       "Application" in notifications and "Follow" not in notifications)
    ck("reminders", "driven by the application's own next action date",
       "next_action_date" in notifications)
    ck("reminders", "opt-in per user", "preferences" in notifications)
    ck("reminders", "sent through the shared email service", "email" in notifications)
    ck("reminders", "sent by a task, never during a web request",
       "reminders" in read("backend/app/tasks.py")
       and "notifications" not in read("backend/app/routers/applications.py"))

head("Application tracking")
TRACKING_FIELDS = {
    "Application": ["user_id", "job_id", "resume_id", "status", "applied_date",
                    "status_updated_at", "notes", "next_action", "next_action_date"],
    "ApplicationEvent": ["application_id", "from_status", "to_status", "changed_at", "note"],
    "Communication": ["application_id", "kind", "direction", "occurred_at",
                      "contact_name", "subject", "summary"],
}
for cls, fields in TRACKING_FIELDS.items():
    m = re.search(rf"class {cls}\(Base\):(.*?)(?=\nclass |\Z)", models, re.S)
    body = m.group(1) if m else ""
    ck("tracking", f"{cls} exists", bool(m))
    for f in fields:
        ck("tracking", f"{cls}.{f}", f"{f}:" in body)
ck("tracking", "stages include applied, interview, offer, rejected",
   all(f'{stage} = "{stage}"' in models for stage in ("applied", "interview", "offer", "rejected")))
ck("tracking", "deleting a CV keeps the application",
   'ForeignKey("resumes.id", ondelete="SET NULL")' in models)

apps_router = read("backend/app/routers/applications.py")
for route in ('prefix="/api/applications"', 'prefix="/api/communications"', '"/stats"',
              '"/{application_id}/events"', '"/{application_id}/communications"'):
    ck("tracking", f"route {route}", route in apps_router)
ck("tracking", "scoped to the signed-in user", "Application.user_id == user.id" in apps_router)
ck("tracking", "status changes recorded as events", "ApplicationEvent(from_status=" in apps_router)
ck("tracking", "follow-ups flagged", "needs_follow_up" in apps_router)
main_py = read("backend/app/main.py")
ck("tracking", "routers registered",
   "applications.router" in main_py and "applications.communications_router" in main_py)

ck("tracking", "manual links must be http(s)", "_http_url" in read("backend/app/schemas.py"))
ck("tracking", "no model call for a job with no advert",
   "require_description(job)" in read("backend/app/routers/jobs.py")
   and "require_description(job)" in read("backend/app/routers/documents.py"))

client_js = read("frontend/src/api/client.js")
for fn in ("listApplications", "applicationStats", "createApplication", "updateApplication",
           "applicationEvents", "listCommunications", "addCommunication"):
    ck("tracking", f"api.{fn}", f"{fn}:" in client_js)
for path in ("frontend/src/components/ApplicationPanel.jsx",
             "frontend/src/components/LogApplication.jsx",
             "frontend/src/lib/applicationStatus.js",
             "backend/tests/test_applications.py"):
    ck("tracking", f"{path} exists", (ROOT / path).exists())
head("Forgot password")
auth_router = read("backend/app/routers/auth.py")
ck("reset", "forgot-password endpoint", '"/forgot-password"' in auth_router)
ck("reset", "reset-password endpoint", '"/reset-password"' in auth_router)
ck("reset", "both rate limited",
   "forgot_password_rate_limit" in auth_router and "reset_password_rate_limit" in auth_router)
ck("reset", "reset signs out every session", "RefreshToken.user_id == user.id" in auth_router)
ck("reset", "email sent after the response", "background.add_task" in auth_router)
ck("reset", "only token hashes stored",
   "class PasswordResetToken(" in models and "token_hash" in models)
ck("reset", "production never logs the link", "is_production" in read("backend/app/services/email.py"))
ck("reset", "reset pages exist", all((ROOT / f).exists() for f in (
    "frontend/src/pages/ForgotPassword.jsx", "frontend/src/pages/ResetPassword.jsx")))
ck("reset", "sign-in page links to it", "/forgot-password" in read("frontend/src/pages/Login.jsx"))

head("Job feed - free sources, cached, safe")
sources_py = read("backend/app/services/job_sources.py")
feed_py = read("backend/app/services/job_feed.py")
# Read here: this section runs before the pasting section defines jobs_router.
feed_router = read("backend/app/routers/jobs.py")
ck("feed", "Adzuna source", "api.adzuna.com" in sources_py)
ck("feed", "Himalayas source", "himalayas.app/jobs/api/search" in sources_py)
ck("feed", "no Remotive or Arbeitnow (terms / fit)",
   "remotive.com" not in sources_py and "arbeitnow.com" not in sources_py)
ck("feed", "feed endpoint", '"/feed"' in feed_router)
ck("feed", "feed is rate limited", "feed_rate_limit" in feed_router)
ck("feed", "identical searches cached server-side", "feed_cache_minutes" in feed_py)
ck("feed", "a failing source never breaks the feed", "_stored(" in feed_py)
ck("feed", "only http(s) apply links kept", "_safe_url" in sources_py)
ck("feed", "HTML descriptions reduced to text", "page_text" in sources_py)
ck("feed", "Apply button names the source",
   'source_publisher="Himalayas"' in sources_py and 'source_publisher="Adzuna"' in sources_py)
ck("feed", "search bar on the Jobs page", 'type="search"' in read("frontend/src/components/JobFeed.jsx"))
ck("feed", "feed shown on the Jobs page", "JobFeed" in read("frontend/src/pages/Jobs.jsx"))
ck("feed", "Adzuna keys are secrets in the blueprint", "ADZUNA_APP_KEY" in read("render.yaml"))

head("Recommended jobs - from resume skills")
rec_py = read("backend/app/services/recommendations.py")
rec_router = read("backend/app/routers/jobs.py")
ck("recommend", "recommendations endpoint", '"/recommended"' in rec_router)
ck("recommend", "declared before the job id route",
   '"/recommended"' in rec_router and rec_router.find('"/recommended"') < rec_router.find('"/{job_id}"'))
ck("recommend", "searches through the shared feed cache", "job_feed.search" in rec_py)
ck("recommend", "searches the resume job titles", "job_titles" in rec_py)
ck("recommend", "ranks by skills mentioned", "def match_skills" in rec_py)
ck("recommend", "jobs already applied to are left out", "Application.job_id" in rec_py)
ck("recommend", "preferred location and remote setting",
   "preferred_location" in models and "include_remote" in models)
ck("recommend", "section on the Jobs page", "RecommendedJobs" in read("frontend/src/pages/Jobs.jsx"))
ck("recommend", "AI scores only the top few", "AI_SCORED" in read("frontend/src/components/RecommendedJobs.jsx"))
ck("recommend", "tests", (ROOT / "backend/tests/test_recommendations.py").exists())

head("History is derived, not stored")
ck("history", "no History table", "class History" not in models)
documents_router = read("backend/app/routers/documents.py")
ck("history", "history derived from GeneratedDocument", "GeneratedDocument" in documents_router
   and "/history" in documents_router)

head("Match scoring is on-demand; cards show only what is already cached")
jobs_router = read("backend/app/routers/jobs.py")
user_state = read("backend/app/services/user_state.py")
# Cards DO show a percentage - but only one read from the database. The
# invariant that matters is that rendering never calls the model.
ck("cost", "cards show the cached score", "match_percentage" in user_state)
ck("cost", "rendering a card never calls the model", "ai." not in user_state)
ck("cost", "card score is scoped to the active resume", "is_active" in user_state)
ck("cost", "scoring is a separate explicit POST", '"/{job_id}/match"' in jobs_router)
ck("cost", "job detail does not score", "ai.analyze_match" not in jobs_router.split("def analyze_job")[0])
ck("cost", "match cached per (user, job, resume)", "uq_match_user_job_resume" in models)
ck("cost", "recompute only when explicitly refreshed", "refresh" in jobs_router)

head("Prompt injection defenses (the central security concern)")
ck("ai", "untrusted job text is fenced", "wrap_untrusted" in ai)
ck("ai", "delimiter injection is stripped", ".replace(UNTRUSTED_OPEN" in ai)
ck("ai", "guard tells the model the block is data", "never" in ai and "instructions to follow" in ai)
ck("ai", "job text never goes in the system prompt",
   "wrap_untrusted(description)" in ai and "system=f\"{wrap_untrusted" not in ai)
ck("ai", "structured output on every call", "response_schema=schema" in ai and "response_mime_type" in ai)
ck("ai", "match percentage clamped server-side", "max(0, min(100" in ai)
ck("ai", "generation forbids fabrication", "invent" in ai.lower())
ck("ai", "token usage is logged", "usage_metadata" in ai)
ck("ai", "free-tier quota surfaced as retryable", "AIRateLimited" in ai)
ck("ai", "AI endpoints are rate limited", "ai_rate_limit" in read("backend/app/rate_limit.py"))
for router in ("backend/app/routers/jobs.py", "backend/app/routers/documents.py",
               "backend/app/routers/resumes.py"):
    ck("ai", f"{Path(router).name} guards AI routes", "ai_rate_limit" in read(router))

head("No LLM output triggers a side effect")
ck("ai", "documents are drafts the user edits", "edited_content" in models)
ck("ai", "original AI output is never overwritten", "never overwritten" in documents_router
   or "edited_content" in documents_router)
ck("ai", "no auto-apply or auto-send anywhere",
   not re.search(r"auto_apply|send_application|submit_application", read("backend/app/routers/documents.py")))

head("Nav - Home, Jobs, Saved, Tracking, History, Calendar, Profile")
nav = read("frontend/src/components/BottomNav.jsx")
# Matches single- or double-quoted routes: the UI branch reformatted this file.
routes = re.findall(r"to: .(/[a-z-]*).", nav)
ck("nav", "core pages are in the nav", {"/jobs", "/saved", "/history", "/profile"} <= set(routes), str(routes))
ck("nav", "at most 7 nav items", 1 <= len(routes) <= 7, str(routes))

head("Apply link - required everywhere a job is shown")
apply = read("frontend/src/components/ApplyLink.jsx")
ck("apply", "opens in a new tab", 'target="_blank"' in apply)
ck("apply", "rel=noopener noreferrer", 'rel="noopener noreferrer"' in apply)
ck("apply", "labelled with source_publisher", "source_publisher" in apply)
ck("apply", "hidden when there is no url", "if (!job.url) return null" in apply)
ck("apply", "on the feed card", "ApplyLink" in read("frontend/src/components/JobCard.jsx"))
ck("apply", "on job detail", "ApplyLink" in read("frontend/src/pages/JobDetail.jsx"))
ck("apply", "on History", "ApplyLink" in read("frontend/src/pages/History.jsx"))

head("Jobs enter by pasting or from free sources - no paid feed")
job_url = read("backend/app/services/job_url.py")
ck("paste", "URL fetcher exists", bool(job_url))
ck("paste", "paste-a-link endpoint", "/from-url" in jobs_router)
ck("paste", "paste-the-text fallback", "/from-text" in jobs_router)
# Adzuna is free (developer key), so only the paid JSearch/RapidAPI route is banned.
ck("paste", "no paid job APIs remain",
   not (BE / "app/services/jsearch.py").exists() and "rapidapi" not in read("backend/app/config.py").lower())
ck("paste", "no RapidAPI key in config", "rapidapi" not in read("backend/app/config.py").lower())
ck("paste", "cheapest-first extraction (JSON-LD before the model)",
   "parse_json_ld" in jobs_router and jobs_router.index("parse_json_ld") < jobs_router.index("extract_job_from_page"))
ck("paste", "re-pasting the same job reuses the row", "sha256" in jobs_router)
ck("paste", "resume upload endpoint", (BE / "app/routers/resumes.py").exists())
ck("paste", "PDF/DOCX/text extraction", (BE / "app/services/resume_text.py").exists())
ck("paste", "skill profile is user-editable", "skill-profile" in read("backend/app/routers/resumes.py"))

head("SSRF - the server fetches a URL the user controls")
ck("ssrf", "addresses are resolved and checked", "getaddrinfo" in job_url)
ck("ssrf", "private ranges refused", "is_private" in job_url)
ck("ssrf", "loopback refused", "is_loopback" in job_url)
ck("ssrf", "link-local (cloud metadata) refused", "is_link_local" in job_url)
ck("ssrf", "only http(s) schemes", '("http", "https")' in job_url)
ck("ssrf", "redirects re-validated", job_url.count("validate_url") >= 3)
ck("ssrf", "response size capped", "MAX_PAGE_BYTES" in job_url)

head("Match percentage is presented honestly")
match_panel = read("frontend/src/components/MatchPanel.jsx")
ck("ui", "match panel exists", bool(match_panel))
# The paste box may live in a component the Jobs page renders, so follow it there.
jobs_page = read("frontend/src/pages/Jobs.jsx")
add_job = jobs_page + read_if("frontend/src/components/AddJobForm.jsx") + read_if("frontend/src/components/QuickAddJob.jsx")
ck("ui", "paste UI on the main page", "addJobFromUrl" in add_job)
ck("ui", "text fallback offered", "addJobFromText" in add_job)
ck("ui", "score never claimed as a hiring prediction", "not a prediction" in match_panel)
ck("ui", "requirements met and missing both shown",
   "requirements_met" in match_panel and "requirements_missing" in match_panel)

head("Document editor + export")
editor = read("frontend/src/pages/DocumentEditor.jsx")
ck("docs", "structured editor, not one textarea", "BulletList" in editor and "ResumeForm" in editor)
ck("docs", "user reviews before export", "before you use it" in editor)
ck("docs", "reset to generated", "resetDocument" in editor)
ck("docs", "PDF export", (FE / "src/lib/exportPdf.js").exists())
ck("docs", "export escapes model output", "function esc(" in read("frontend/src/lib/exportPdf.js"))

head("Master resume - permanent base, per-job copies")
tailor_py = read("backend/app/services/tailored_resume.py")
docs_router = read("backend/app/routers/documents.py")
resumes_router = read("backend/app/routers/resumes.py")
ck("master", "copy of the master without AI", '"/jobs/{job_id}/documents/from-master"' in docs_router)
ck("master", "AI returns edits applied to a copy", "def apply_tailoring" in tailor_py and "tailor_master_resume" in docs_router)
ck("master", "facts cannot change: edits keyed by index", "section_index" in read("backend/app/services/ai.py"))
ck("master", "fill from uploaded CV returns a draft", '"/{resume_id}/master/draft"' in resumes_router)
ck("master", "new upload keeps the master", "master_content=master_content" in resumes_router)
ck("master", "one editor for master and job copies",
   "ResumeEditor" in read("frontend/src/pages/DocumentEditor.jsx") and "ResumeEditor" in read("frontend/src/components/ResumePanel.jsx"))
ck("master", "tests", (ROOT / "backend/tests/test_tailored_resume.py").exists())

head("Interview preparation")
apps_router = read("backend/app/routers/applications.py")
prep_py = read("backend/app/services/interview_prep.py")
ck("prep", "endpoint on the application", '"/{application_id}/interview-prep"' in apps_router)
ck("prep", "only at the interview stage", "ApplicationStatus.interview" in apps_router)
ck("prep", "saved plan reused unless refresh", "refresh" in apps_router and "existing" in apps_router)
ck("prep", "no advert, no quota spent", "require_description" in apps_router)
ck("prep", "model output clipped to the stored shape", "def normalise" in prep_py)
ck("prep", "advert fenced as untrusted", "wrap_untrusted" in read("backend/app/services/ai.py"))
ck("prep", "panel on the job page", "InterviewPrepPanel" in read("frontend/src/pages/JobDetail.jsx"))
ck("prep", "tests", (ROOT / "backend/tests/test_interview_prep.py").exists())

head("Security carried forward")
sec = read("backend/app/security.py")
auth = read("backend/app/routers/auth.py")
main = read("backend/app/main.py")
ck("sec", "bcrypt password hashing", "bcrypt" in sec)
ck("sec", "refresh tokens stored hashed", "hash_refresh_token" in sec and "sha256" in sec)
ck("sec", "rate limiting on login and signup", "login_rate_limit" in auth and "signup_rate_limit" in auth)
cors = main[main.find("add_middleware"): main.find("add_middleware") + 500]
ck("sec", "CORS restricted, not wildcard",
   "allow_origins=settings.cors_origins" in cors and '["*"]' not in cors)
ck("sec", "Pydantic validation at the boundary", "field_validator" in schemas)
ck("sec", "user text stripped of control chars", "clean_text" in schemas)
ck("sec", "API key is server-side only", "gemini_api_key" in read("backend/app/config.py")
   and "GEMINI" not in read("frontend/src/api/client.js"))
raw_sql = []
for py in (BE / "app").rglob("*.py"):
    txt = py.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r'(?:execute|text)\(\s*f["\']', txt):
        raw_sql.append(f"{py.relative_to(BE)}:{txt[:m.start()].count(chr(10))+1}")
ck("sec", "no f-string interpolated SQL", not raw_sql, "; ".join(raw_sql))

head("Deployment readiness")
ck("deploy", "frontend host config", (ROOT / "netlify.toml").exists())
ck("deploy", "SPA redirect", (ROOT / "frontend/public/_redirects").exists())
ck("deploy", "backend blueprint", (ROOT / "render.yaml").exists())
ck("deploy", "no cron jobs for deleted tasks", "app.tasks digest" not in read("render.yaml"))
ck("deploy", "GEMINI_API_KEY in the blueprint", "GEMINI_API_KEY" in read("render.yaml"))
ck("deploy", "no paid keys in the blueprint", "RAPIDAPI" not in read("render.yaml"))
ck("deploy", "container image", (ROOT / "backend/Dockerfile").exists())
ck("deploy", "migrations run before serving", "alembic upgrade head" in read("backend/start.sh"))
ck("deploy", "platform postgres:// normalised", "_PG_SCHEME_FIXES" in read("backend/app/config.py"))
ck("deploy", "production refuses a default JWT secret", "production_blockers" in read("backend/app/config.py"))
ck("deploy", "tests in the repo", (BE / "tests").is_dir())
ck("deploy", "CI runs them", (ROOT / ".github/workflows/ci.yml").exists())
ck("deploy", "deployment guide", (ROOT / "DEPLOYMENT.md").exists())
ck("deploy", "single migration head", len(list((BE / "alembic/versions").glob("*.py"))) >= 1)

print("\n" + "=" * 60)
print(f"{checks} checks, {len(issues)} problem(s)")
if issues:
    for s, l, d in issues:
        print(f"  [{s}] {l} {d}")
    sys.exit(1)
print("CLAUDE.md IS FULLY IMPLEMENTED")
