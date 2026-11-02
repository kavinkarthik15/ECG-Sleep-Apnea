# ECG-Based Sleep Apnea Screening Frontend

A React, TypeScript, Vite, and Tailwind CSS interface for the existing FastAPI ECG screening backend. The frontend does not recreate signal processing or machine-learning logic; it uploads recordings and presents the backend's window-level output.

## Setup

From the repository root:

```powershell
cd frontend
npm install
```

Create `.env` from `.env.example`:

```env
VITE_API_BASE_URL=/api/v1
```

Start the backend in one terminal from the repository root, then the frontend in another:

```powershell
uvicorn app.main:app --reload
cd frontend
npm run dev
```

Vite proxies `/api/*` and `/health` to the local FastAPI server. In production, `frontend/vercel.json` rewrites those paths to the fixed backend deployment, so the browser uses the frontend origin for API requests and cookies.

The frontend expects the backend model to be available at `app/models/ecg_apnea_hrv_lr_v2.joblib`. The backend is authoritative for ECG validation, signal quality, R-peak detection, RR processing, and model inference.

## Routes

- `/` overview and workflow
- `/analyze` CSV/TXT upload and analysis submission
- `/results` current-session recording summary and window timeline
- `/about` model context, processing path, feature list, and limitations

Results are kept in route state for immediate navigation and are also temporarily persisted by the backend as derived analysis data. Refreshing the results page retrieves the current analysis, or the opaque analysis reference in the URL, using the anonymous visitor cookie. Session identifiers are never stored in local or session storage. Raw ECG files are not persisted.

## API contract

The interface uses `GET /health`, `GET /api/v1/model-info`, `POST /api/v1/session`, `POST /api/v1/analyze-file`, and the session-scoped analysis retrieval endpoints. Uploads are sent as multipart form data with `file`, `sampling_rate=100`, and HRV feature inclusion enabled. Supported files are `.csv` and `.txt`, up to the backend's configured 10 MB limit.

API requests include credentials. Production requests use the same-origin `/api/v1` path and are proxied by Vercel. Keep the backend's exact frontend origin in `CORS_ORIGINS`; the backend continues to validate request origins for cookie-authenticated state-changing requests. The session cookie remains host-only, `HttpOnly`, `Secure`, and `SameSite=Lax`. Do not put database URLs or cleanup secrets in `VITE_*` variables.

The backend reports consecutive non-overlapping 60-second windows. The UI distinguishes apnea-related patterns, no-apnea-related patterns, and rejected windows. An apnea-class score is presented as the model's score for the apnea-related class, never as a patient's diagnosis or clinical probability. No AHI or severity categories are calculated.

## Checks

```powershell
npm run build
npm run test
npm run lint
```

The backend expires visitor sessions after two hours of inactivity or twelve hours absolutely. Associated derived results are deleted when the visitor ends a session or scheduled cleanup deletes an expired session. Deployment retention is not guaranteed until its PostgreSQL database and scheduled cleanup job are configured and verified.

This is an academic research prototype. Its output is not a medical diagnosis and does not replace polysomnography, professional evaluation, or clinical care.
