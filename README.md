# ECG-Based Sleep Apnea Screening System

This project implements an academic ECG-based sleep apnea screening prototype that combines a FastAPI backend with a React + TypeScript + Vite frontend. The backend validates ECG recordings, splits them into consecutive 60-second windows, extracts HRV-related features, and applies the frozen model artifact stored at `app/models/ecg_apnea_hrv_lr_v2.joblib`.

This application is an academic ECG-based screening prototype. Model outputs represent apnea-related patterns detected in 60-second ECG windows and are not a medical diagnosis.

## Overview

The system accepts ECG input as either a JSON payload or a `.csv`/`.txt` file upload, validates the signal format, and returns window-level screening results. Raw ECG uploads are processed in memory and are not persisted. Derived analysis results are temporarily stored in PostgreSQL and scoped to an anonymous visitor session. The system intentionally does not claim a patient diagnosis or clinical severity estimate.

## Architecture

- Backend: FastAPI service for validation, preprocessing, feature extraction, and model inference
- Frontend: React + TypeScript + Vite interface for upload and result visualization
- ML artifact: frozen scikit-learn model (`app/models/ecg_apnea_hrv_lr_v2.joblib`)
- Persistence: PostgreSQL-backed anonymous sessions and derived analyses
- Waveform display: bounded per-window min/max envelopes; raw ECG samples are not persisted
- Validation: backend regression tests and frontend tests/build checks

## Technology Stack

- Python 3.11+
- FastAPI
- Pydantic
- scikit-learn / joblib
- NumPy / pandas
- React 19
- TypeScript
- Vite
- Tailwind CSS
- Vitest + jsdom

## ML Pipeline

The backend expects ECG input sampled at 100 Hz and processes consecutive non-overlapping 60-second windows. The pipeline performs:

- signal validation and file parsing
- numeric conversion and format checks
- rejection of ambiguous or malformed inputs
- feature extraction for HRV-related ECG characteristics
- model inference using the frozen artifact
- window-level summary reporting without making a diagnosis

The apnea-class score is a model score for the apnea-related class of a 60-second ECG window. It is not described as the probability that a patient has sleep apnea, and no AHI or mild/moderate/severe classification is produced.

## Backend

The backend application is started from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is served at `http://127.0.0.1:8000`.
Set `DATABASE_URL` to a PostgreSQL connection URL and run the migration before using session or analysis routes. For plain-HTTP local development only, `SESSION_COOKIE_SECURE=false` can be used; never disable Secure cookies in production.

If Windows DNS cannot resolve a Neon hostname locally, the development-only DNS-over-HTTPS workaround can be explicitly enabled with `DATABASE_DNS_OVER_HTTPS=true` and `DATABASE_DNS_OVER_HTTPS_TIMEOUT_SECONDS=5`. It queries Google's DNS-over-HTTPS endpoint, follows CNAME records, caches A records by TTL, and passes the resolved address as libpq `hostaddr` while retaining the original database hostname in the connection string for TLS hostname validation. This setting is rejected in production and must not be enabled on Vercel. It is not a replacement for correcting a production DNS configuration.

Swagger UI: `/docs`
ReDoc: `/redoc`

### API endpoints

- `GET /` and `GET /health`
- `GET /api/v1/model-info`
- `POST /api/v1/predict` for a single JSON window
- `POST /api/v1/analyze-samples` for consecutive JSON windows
- `POST /api/v1/analyze-file` for `.csv` or `.txt` file uploads
- `POST /api/v1/session` to create or resume the anonymous visitor session
- `GET /api/v1/session/analysis` to retrieve that session's latest analysis
- `GET /api/v1/analyses/{analysis_ref}` to retrieve an owned analysis
- `GET /api/v1/analyses/{analysis_ref}/windows/{window_index}` to retrieve an owned window's bounded waveform and R-peak details
- `POST /api/v1/assistant/message` to ask the educational AI assistant about an owned analysis
- `DELETE /api/v1/session` to end the session and delete its analyses
- `GET /api/v1/internal/cleanup` for authenticated scheduled retention cleanup

Example request body:

```json
{
  "sampling_rate": 100,
  "ecg_samples": [0.01, 0.03],
  "include_features": false
}
```

CSV support includes single-column numeric data or a named column such as `ecg`, `ECG`, `signal`, or `amplitude`. Ambiguous files are rejected. Uploaded data is processed in memory and is not persisted.

### PostgreSQL, migrations, and session retention

Configure `DATABASE_URL` with a PostgreSQL connection URL using psycopg before starting the API. Apply schema changes as a release step with `alembic upgrade head`; application startup intentionally does not create or alter production tables. SQLite is rejected outside the isolated automated-test configuration.

Anonymous visitors receive a random session identifier only in the `HttpOnly`, `Secure`, `SameSite` cookie named by `SESSION_COOKIE_NAME`. The database stores its SHA-256 hash, never the cookie value. Sessions expire after two hours without activity or twelve hours absolutely. Associated analysis summaries, per-window results, signal-quality values, optional HRV features, detected R-peak sample indices, and bounded min/max waveform display envelopes are deleted when the visitor ends the session or when cleanup deletes an expired session. Raw ECG samples and uploaded filenames are not persisted. The waveform envelope is derived from the uploaded signal and is capped at 1,200 points per 60-second window; it is not a full-resolution recording. An analysis reference is not an authorization credential; every read is restricted to the session authenticated by the cookie.

For browser state-changing requests, the API checks the `Origin` against `CORS_ORIGINS`; CORS alone is not authorization. Set `CORS_ORIGINS` to the exact browser origin(s). Production must use HTTPS and `SESSION_COOKIE_SECURE=true`. Same-site frontend/API deployments can use `SESSION_COOKIE_SAMESITE=lax`. Cross-site deployments require `SESSION_COOKIE_SAMESITE=none`, `SESSION_COOKIE_SECURE=true`, credentialed CORS, and exact allowed origins; `SameSite=None` by itself is insufficient. Leave the cookie host-only unless a shared parent domain is explicitly required. Vercel terminates HTTPS at its edge; the cookie's Secure flag is configured explicitly, so the API does not infer security from forwarded headers. Keep the application behind the trusted platform proxy and do not trust client-supplied forwarding headers.

Cleanup is idempotent and removes sessions that are inactive for two hours or have reached absolute expiry, cascading to their analyses. Expiry is evaluated using the database clock in the deletion statement. The endpoint requires CRON_SECRET as a bearer token. The repository includes .github/workflows/cleanup-expired-sessions.yml, which requests cleanup daily at 06:17 UTC. Configure the GitHub Actions repository secrets ECG_API_BASE_URL (backend base URL) and CRON_SECRET (the same value configured on the backend). The workflow suppresses request details and response bodies. It has not been run against the deployed API in this development task; automatic deletion is therefore not verified or guaranteed until the secrets are configured and a scheduled or manual workflow invocation succeeds. With a daily schedule, expired records may remain until the next successful run. Expired sessions are rejected on access before scheduled deletion.

Vercel Functions are stateless, so PostgreSQL must be external and migrations must run outside function startup. Confirm the deployment's Python/FastAPI routing and request-size limits before deployment: the application accepts uploads up to its configured 10 MB limit, which may exceed a serverless platform's per-request limit.

## Frontend

The frontend is located under `frontend/`. In production, configure the Vercel project root as `frontend/`; its `vercel.json` proxies `/api/*` and `/health` to the fixed backend deployment, so browser API traffic and the host-only visitor cookie stay on the frontend origin. Local Vite development proxies those paths to the local FastAPI backend.

```powershell
cd frontend
npm install
```

Create `.env` from `.env.example` if needed:

```env
VITE_API_BASE_URL=/api/v1
```

Start the backend in one terminal, then run the frontend in another:

```powershell
uvicorn app.main:app --reload
cd frontend
npm run dev
```

The UI supports upload and results viewing for `.csv` and `.txt` files. It uses the opaque analysis reference only as a lookup identifier and retrieves the analysis through the visitor cookie before showing results. The results page includes the bounded waveform envelope, detected R-peak sample indices, existing HRV features and signal-quality values when available, screening-summary explanations, and an educational AI assistant. Selected waveform intervals, peaks, metrics, and windows are validated against the visitor-owned persisted analysis on the backend. Chat text is held only in page memory and is cleared by refresh or navigation away; it is not saved.

### Local Ollama assistant setup

Local development uses Ollama by default, so no hosted API key or usage-based service is required. Install Ollama for Windows from [ollama.com/download/windows](https://ollama.com/download/windows), then run:

```powershell
ollama pull qwen2.5:3b
ollama run qwen2.5:3b
```

Keep Ollama running while using the local chatbot and configure the backend with:

```env
ASSISTANT_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
```

The backend sends only the conversation and minimum authorized derived analysis context to Ollama. Raw ECG samples, uploaded files, cookies, and secrets are not sent. Ollama is a local-development provider and does not automatically work on Vercel or other serverless deployments; use a separately reachable provider only when explicitly configured.

### Optional OpenRouter assistant

To explicitly select OpenRouter, set `ASSISTANT_PROVIDER=openrouter` and configure `OPENROUTER_API_KEY` only in the backend environment. The configured model must be an explicitly free `:free` model; there is no automatic provider fallback or paid request path. Configure `OPENROUTER_MODEL`, `OPENROUTER_TIMEOUT_SECONDS`, `OPENROUTER_APP_NAME`, and `OPENROUTER_APP_URL` as needed. Never place the key in `VITE_*` frontend variables. OpenRouter free models have quotas and rate limits; provider failures are reported as temporary unavailability.

### Assistant provider and limitations

The backend exposes a replaceable `AssistantProvider` protocol with a local deterministic provider. It supports bounded explanations of measurements, screening outputs, signal quality, selected waveform intervals, and general ECG/HRV concepts. It does not generate open-ended answers or send user content to an AI service. Analysis context is loaded from the database only after ownership is verified; the request accepts selection identifiers, not client-supplied measurements.

A genuine open-ended model is not configured because there is no reliable zero-cost hosted model in this project and Vercel Functions are not an appropriate place to run a large local model. A suitable no-per-call-API alternative is an operator-hosted open-source model served by Ollama on separate hardware, with a backend provider adapter and authenticated private network access. That hardware, model download, availability, and secure hosting are not supplied or configured here, so generative assistant functionality remains an explicit limitation.

## Environment Configuration

The backend reads configuration from environment variables such as:

- `APP_ENV`
- `HOST`
- `PORT`
- `CORS_ORIGINS`
- `MAX_UPLOAD_MB`
- `LOG_LEVEL`
- `DATABASE_URL`
- `SESSION_COOKIE_NAME`
- `SESSION_COOKIE_SECURE`
- `SESSION_COOKIE_SAMESITE`
- `CRON_SECRET`

The frontend uses `VITE_API_BASE_URL` for the API path; `/api/v1` is the production and local-proxy default. An absolute backend URL remains supported for direct local development when needed.

Only the API base URL belongs in frontend `VITE_*` configuration. Database and cleanup credentials must remain backend-only.

## Testing

From the repository root:

```powershell
python -m pytest -q
```

From the frontend directory:

```powershell
npm run test -- --run
npm run build
```

## Project Structure

```text
ECG/
├── app/
│   ├── api/
│   ├── core/
│   ├── ml/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── main.py
│   └── __init__.py
├── tests/
├── frontend/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── run.py
├── sample_ecg.csv
├── sample_ecg.txt
├── invalid_ecg.txt
└── app/models/ecg_apnea_hrv_lr_v2.joblib
```

## Limitations

- This is an academic research prototype.
- It is not a medical diagnosis.
- It does not replace polysomnography or physician evaluation.
- It is only intended to surface apnea-related pattern estimates from ECG windows.
- The system does not estimate AHI, severity classes, or clinical probability claims.

## Academic / Research Disclaimer

This application is designed for research and educational use. It explores ECG-based pattern detection for apnea-related windows and is intended to support exploratory analysis rather than patient care decisions. Model outputs are not clinical diagnoses and should not be used as the sole basis for medical assessment.

## Notes

The frozen model artifact is intentionally kept byte-for-byte unchanged. It is validated before release and must not be retrained, renamed, modified, or replaced without explicit project review.