# Dip Buying Trigger — API (Backend only)

This repository contains a small FastAPI backend that computes dip-buying triggers (based on 200-DMA) for a set of indices and returns the results as JSON.

Files added:

- `server.py` — FastAPI app with `/dip` endpoint returning recommendations in JSON.
- `requirements.txt` — Python dependencies.
- `Procfile` — start command for platforms that use Procfile (Render, Railway, Heroku-style).

How to run locally

1. Create a virtual environment and install dependencies.

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

2. Run the app locally with uvicorn (development) or gunicorn (production):

```powershell
# development
python -m uvicorn server:app --host 0.0.0.0 --port 8000

# production-like (requires gunicorn)
gunicorn server:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Then open http://localhost:8000/dip

Notes about deployment (free hosting)

- Render (https://render.com): Create a new Web Service, connect your repo, set the build command `pip install -r requirements.txt` and start command from the `Procfile`. Render will set `$PORT` automatically.
- Railway (https://railway.app): Create a new Project > Deploy from GitHub. Railway will detect a Python app; use `gunicorn server:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT` as start command.

Tips

- yfinance may be rate-limited; for heavy usage consider caching or using a dedicated data provider.
- If you want the exact same behavior as the Streamlit UI in `main.py`, we can refactor the calculation into a shared module and import it from both `server.py` and `main.py`.
