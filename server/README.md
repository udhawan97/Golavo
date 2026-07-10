# golavo-server

The Golavo local server (FastAPI). **AGPL-3.0.** It orchestrates the `core`
library, serves the UI, builds AI evidence bundles, and runs background jobs.
It never computes statistics inline — it calls `golavo-core`.

```bash
uvicorn golavo_server.main:app --host 127.0.0.1 --port 8000 --app-dir server
# GET /health -> {"status": "ok", ...}
```

Security: binds to `127.0.0.1` only; in the packaged app it runs on an ephemeral
port behind a per-launch token with strict CORS/CSP. See the repository
`SECURITY.md`.
