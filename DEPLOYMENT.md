# Deploying PromptlyHired

The frontend goes on **Netlify**. The API and Postgres go on **Render**. Uploaded
resumes go in **Cloudflare R2**. All three have free tiers that cover this app.
It takes about 30 minutes, most of it waiting for builds.

Work through the steps in order, because later steps need values from earlier ones.

---

## 0. Push the repo to GitHub

Netlify and Render both deploy from GitHub.

```bash
git add -A
git commit -m "PromptlyHired"
git branch -M main
git remote add origin https://github.com/<you>/PromptlyHired.git
git push -u origin main
```

`.gitignore` already excludes `backend/.env`, `frontend/.env`, `node_modules/`,
`.venv/` and `media/`. **Never commit a `.env` file.** Every secret below goes in
the host's environment variable settings instead.

---

## 1. Get your keys

Keep these somewhere safe. You'll paste them in later.

| Key | Where to get it | Needed? |
| --- | --- | --- |
| JWT secret | Run `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Render can also generate one for you. | Yes |
| Gemini API key | [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Free, no card. | Yes. Without it there's no skill extraction, matching, resume or cover letter generation, or recommendation scoring. |
| Adzuna app ID and key | [developer.adzuna.com](https://developer.adzuna.com). Free. | Recommended. Without it the job feed only shows remote jobs from Himalayas. |
| Gmail App Password | Google Account → Security → 2-Step Verification → App passwords. | Recommended. Without it, forgot-password emails can't be sent, so anyone who forgets their password is locked out. |
| Cloudflare R2 bucket | See step 5. | Yes. Otherwise uploaded resumes are lost on every deploy. |

---

## 2. Deploy the API to Render

1. Render → **New** → **Blueprint** → select your repo. It reads `render.yaml` and
   sets up a web service (`jobtrail-api`) and a Postgres database (`jobtrail-db`).
2. Click **Apply**. The database and `JWT_SECRET` are created automatically.
3. The first deploy will **fail its health check**. That's expected, because
   `CORS_ORIGINS` and `APP_BASE_URL` aren't set yet. Continue with step 3, then
   come back in step 4 to set them.

The service uses Render's Python runtime, not Docker. `start.sh` runs
`alembic upgrade head` before starting the server, so a deploy either comes up with
the right database schema or fails loudly. You never run migrations by hand.

> Two branches that each add a migration leave Alembic with two "heads", and
> `alembic upgrade head` then fails on deploy. CI checks for a single head on every
> pull request. If it fails, add a merge migration:
> `alembic merge -m "merge ..." <head1> <head2>`.

---

## 3. Deploy the frontend to Netlify

1. Netlify → **Add new project** → **Import an existing project** → your repo.
2. Netlify reads `netlify.toml`, so the build settings are already correct
   (base `frontend`, publish `dist`).
3. Under **Project configuration → Environment variables**, add:

   | Key | Value |
   | --- | --- |
   | `VITE_API_BASE_URL` | `https://<your-render-service>.onrender.com` (no trailing slash) |

4. Deploy, and note your site URL, e.g. `https://promptlyhired.netlify.app`.

> `VITE_*` variables are built into the site when Netlify builds it. After
> changing one you need to redeploy. Refreshing the page isn't enough.

---

## 4. Point the API at the frontend and add the keys

Back in Render → your web service → **Environment**:

| Key | Value |
| --- | --- |
| `CORS_ORIGINS` | Your Netlify URL, e.g. `https://promptlyhired.netlify.app` |
| `APP_BASE_URL` | The same Netlify URL. Password reset links point here. |
| `GEMINI_API_KEY` | Your Gemini key |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Your Adzuna keys |
| `JOB_COUNTRY` | Two-letter Adzuna country code. `render.yaml` sets `ca`. |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_USER` | The Gmail address |
| `SMTP_PASSWORD` | The 16-character App Password, not your normal password |
| `SMTP_FROM` | e.g. `PromptlyHired <you@gmail.com>` |

Optional:

| Key | Default | What it does |
| --- | --- | --- |
| `GEMINI_MODEL` | `gemini-3.8-flash` | The first AI model to try |
| `GEMINI_FALLBACK_MODELS` | `gemini-3.6-flash,gemini-flash-lite-latest` | Models to try next when one runs out of free quota |
| `FEED_CACHE_MINUTES` | `180` | How long identical job searches are served from cache, which saves the Adzuna quota |
| `REDIS_URL` | unset | Only needed with more than one instance or worker. Without it, rate limits are counted per process. |

The API **refuses to start** in production if:
- `JWT_SECRET` is the default or shorter than 32 characters
- `CORS_ORIGINS` is missing, `*`, or not https
- `APP_BASE_URL` is http

That's deliberate: a misconfigured deploy should fail straight away, not leak data.
The log line starts with `CONFIG ERROR` and names the variable to fix.

Settings that only switch a feature off are logged as `DEGRADED` at startup:
- no Gemini key
- no SMTP
- no Adzuna
- no R2
- no Redis

---

## 5. Uploaded resumes: Cloudflare R2

`MEDIA_STORAGE=local` writes to the server's disk, which Render **wipes on every
deploy**, so users' resumes and profile pictures would disappear. `render.yaml`
already sets `MEDIA_STORAGE=s3`; you just supply the bucket:

1. Cloudflare dashboard → **R2** → create a bucket, e.g. `jobtrail-media`.
2. Enable public access (or attach a custom domain) and copy the public base URL.
3. **Manage R2 API Tokens** → create a token with Object Read & Write.
4. Set these on the Render web service:

| Key | Value |
| --- | --- |
| `S3_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com` |
| `S3_BUCKET` | `jobtrail-media` |
| `S3_ACCESS_KEY_ID` | From the token |
| `S3_SECRET_ACCESS_KEY` | From the token |
| `S3_PUBLIC_BASE_URL` | Your bucket's public URL |

---

## 6. Costs

There are none. Every service is on its free tier:
- **AI:** Gemini
- **Jobs:** Adzuna and Himalayas
- **Hosting:** Render, Netlify and R2

The limits you'll hit are quotas, not bills:
- **Gemini:** each free model allows about 20 requests a day. The app moves to the
  next model in `GEMINI_FALLBACK_MODELS` when one runs out, and tells the user to
  try again later when they all have.
- **Adzuna:** 25 calls a minute, 250 a day. The shared search cache keeps normal
  use well under that.

---

## 7. Check the live deployment

The fastest check is the built-in doctor. It connects to every service for real
instead of just reading your environment variables. On Render, open the
service's **Shell** tab and run:

```bash
python -m app.tasks doctor
```

It checks:
- the database and migrations
- your frontend URLs
- every Gemini model in the chain, with a tiny real call
- R2, by round-tripping a real file
- both job sources, with a real search
- SMTP, by logging in without sending anything

Each line is `OK`, `SKIP` (not configured) or `FAIL`, with the variable to fix.

You can also check from anywhere:

```bash
curl https://<your-api>.onrender.com/health
```

```json
{
  "status": "ok",
  "env": "production",
  "ai_features": true,
  "durable_media_storage": true,
  "shared_rate_limit_store": false
}
```

`shared_rate_limit_store` is only `true` if you set `REDIS_URL`.

Then check it in a browser:

1. Open the Netlify URL, sign up, and sign in.
2. Upload a resume on **Profile** and check that a skill profile appears.
3. On **Profile**, click **Fill from uploaded CV**, check it, and click **Save master**.
4. Open **Jobs**. The feed should list jobs, and **Recommended for you** should load at the top.
5. Open a job. The match should appear, then try **Tailor resume with AI**,
   **Start from master resume** and **Create cover letter**, and export a PDF.
6. Sign out, use **Forgot password**, and check the email arrives.
7. Hard-refresh on `/history`. It must load, not 404. (That's the single-page-app
   redirect. If it 404s, `netlify.toml` wasn't picked up.)

---

## Moving to a new GitHub repo

If the code moves to a different repo or GitHub account:

1. **Netlify:** Project configuration → Build & deploy → **Manage repository** →
   **Link to a different repository**. Pick the new repo. The environment variables stay.
2. **Render:** web service → **Settings** → **Repository** → change it to the new repo and branch.
   - If the dropdown doesn't show the repo, give Render's GitHub app access to it
     (GitHub → Settings → Applications → Render → Configure).
   - If the service was created from a Blueprint and keeps reverting to the old repo,
     open the Blueprint and **Disconnect** it. Disconnecting keeps the service, the
     database and all environment variables.
3. Push a commit, and check both hosts build from the new repo.

---

## Free-tier gotchas

- **Render free web services sleep after about 15 minutes idle.** The next request
  takes 30–60 seconds. Not a bug.
- **Render free Postgres expires after 30 days.** Back it up or upgrade before then,
  or you lose the database.
- **Gemini's free quota is small.** Pasting a link that parses cleanly costs
  nothing. Each match, resume, cover letter and **Fill from uploaded CV** costs one
  request, and **Recommended for you** scores up to six jobs. Scores are saved, so
  repeat visits are usually free. **Start from master resume** never uses AI.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Frontend loads but every request fails | `VITE_API_BASE_URL` is unset or has a trailing slash. Check the browser console; the app logs this explicitly. |
| "Network error" or CORS errors in the console | `CORS_ORIGINS` on Render doesn't exactly match the Netlify URL, `https://` included. |
| API won't start, logs say `CONFIG ERROR` | Intentional. The message names the variable to fix. |
| Live site doesn't show your latest changes | Render or Netlify is still building from an old repo or branch. Check the repository in each host's settings (see "Moving to a new GitHub repo"). |
| Build fails with `ResolutionImpossible` | Two Python packages need conflicting versions. Pin the version the error names in `requirements.txt`. |
| Deploy fails running migrations with "multiple heads" | Two migrations branched from the same parent. Add a merge migration (see step 2). |
| `sqlalchemy.exc.NoSuchModuleError: postgres` | Shouldn't happen, because `config.py` rewrites `postgres://`. If you see it, `DATABASE_URL` was overridden with something unusual. |
| No skill profile after upload | `GEMINI_API_KEY` is unset or invalid. Check `/health` and run the doctor. |
| Match or generate returns 503 | Same cause: no Gemini key on the API service. |
| Match or generate returns 429 | The free AI quota is used up. Per-minute limits clear in a minute; the daily limit resets at midnight Pacific time. |
| Match or generate returns 502 "AI service is busy" | The model is overloaded upstream, and the app already retried 3 times. If it keeps happening, change `GEMINI_MODEL` (the doctor lists the models your key can use). |
| Job feed only shows remote jobs | Adzuna keys are missing. The doctor shows `SKIP` for Adzuna. |
| Job search says Adzuna "rejected the credentials" | `ADZUNA_APP_ID` or `ADZUNA_APP_KEY` is wrong. Copy them again from the Adzuna dashboard. |
| Forgot-password emails never arrive | SMTP isn't fully set, or `SMTP_PASSWORD` is your normal Gmail password instead of an App Password. The doctor says which. |
| "That site blocked the request" when pasting a link | LinkedIn and Indeed block server fetches. Use the paste-the-text tab. |
| Resumes vanish after a deploy | `MEDIA_STORAGE` isn't `s3`. See step 5. |
