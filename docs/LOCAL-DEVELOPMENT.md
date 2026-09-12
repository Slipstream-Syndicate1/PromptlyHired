# Run JobTrail locally on macOS

These commands assume the initial dependency installation and database migration have been completed. Run from the existing `pragati` checkout; no commits or pushes are required.

## Start

Open Docker Desktop and wait until its engine is running.

Database (any terminal):

```bash
cd "/Users/pragatipuri/Desktop/EVENTS+PROGRAMS+HACKATHONS/hackathon401/JobTrail"
docker compose up -d
docker compose ps
```

Backend (leave this terminal running):

```bash
cd "/Users/pragatipuri/Desktop/EVENTS+PROGRAMS+HACKATHONS/hackathon401/JobTrail/backend"
source .venv/bin/activate
python -m uvicorn app.main:app --reload
```

Frontend (a separate terminal; leave running):

```bash
cd "/Users/pragatipuri/Desktop/EVENTS+PROGRAMS+HACKATHONS/hackathon401/JobTrail/frontend"
npm run dev
```

Open http://localhost:5173 in your browser. Backend health is http://localhost:8000/health. The backend root is not a website. Read the URL printed by Vite: if port 5173 is occupied, stop the earlier frontend process rather than running two copies; backend CORS is configured for 5173.

## Stop and reopen

Press **Ctrl+C** in the frontend terminal and in the backend terminal. Closing a browser tab does not stop either process. You can leave Postgres running, or stop it with:

```bash
cd "/Users/pragatipuri/Desktop/EVENTS+PROGRAMS+HACKATHONS/hackathon401/JobTrail"
docker compose stop
```

The database data remains in its Docker volume. To reopen, repeat the Start commands. Do not delete the Docker volume to restart the application.

## Useful checks

```bash
docker --version
curl http://localhost:8000/health
```

If Docker is installed but the command is missing in the current terminal:

```bash
export PATH="$HOME/.docker/bin:$PATH"
```

Keep that export in `~/.zshrc` for new terminals (it was added during setup). Open a new terminal after changing shell settings.

Frontend changes reload automatically. Backend Python changes reload under `--reload`; restart the backend after changing `.env`. After dependency changes, use `npm ci` in frontend or `python -m pip install -r requirements-dev.txt` in the activated backend environment. When an agreed database migration is added, run `python -m alembic upgrade head` from backend before starting it.
