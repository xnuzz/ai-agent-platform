# Browser e2e suite (Playwright)

Starts the real Django API (`runserver`) and Vite, seeds each test's workspace through the real API with
**mock agents** (`e2e/seed.py` → `tests/support/bundles.py`), and drives Chromium. Fails on any browser JS error.

```bash
export DATABASE_URL=postgres://...  DJANGO_SECRET_KEY=...  FIELD_ENCRYPTION_KEY=...   # migrated DB
export E2E_PYTHON=/path/to/venv/bin/python      # needs backend deps + platform_sdk
cd frontend && npm run e2e
```
Ports: `E2E_API_PORT` (8000), `E2E_WEB_PORT` (5173). Runs in CI as the `e2e` job.
