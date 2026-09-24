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
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Start the backend in one terminal from the repository root, then the frontend in another:

```powershell
uvicorn app.main:app --reload
cd frontend
npm run dev
```

The frontend expects the backend model to be available at `app/models/ecg_apnea_hrv_lr_v2.joblib`. The backend is authoritative for ECG validation, signal quality, R-peak detection, RR processing, and model inference.

## Routes

- `/` overview and workflow
- `/analyze` CSV/TXT upload and analysis submission
- `/results` current-session recording summary and window timeline
- `/about` model context, processing path, feature list, and limitations

Results are intentionally kept in route state only. Raw ECG files and analysis results are not stored in local storage or sent to another service. Refreshing the results page returns to an empty state.

## API contract

The interface uses `GET /health`, `GET /api/v1/model-info`, and `POST /api/v1/analyze-file`. Uploads are sent as multipart form data with `file` and `sampling_rate=100`. Supported files are `.csv` and `.txt`, up to the backend's documented 10 MB limit.

The backend reports consecutive non-overlapping 60-second windows. The UI distinguishes apnea-related patterns, no-apnea-related patterns, and rejected windows. An apnea-class score is presented as the model's score for the apnea-related class, never as a patient's diagnosis or clinical probability. No AHI or severity categories are calculated.

## Checks

```powershell
npm run build
npm run test
npm run lint
```

This is an academic research prototype. Its output is not a medical diagnosis and does not replace polysomnography, professional evaluation, or clinical care.
