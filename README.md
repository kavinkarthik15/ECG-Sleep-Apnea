# ECG-Based Sleep Apnea Screening System

This project implements an academic ECG-based sleep apnea screening prototype that combines a FastAPI backend with a React + TypeScript + Vite frontend. The backend validates ECG recordings, splits them into consecutive 60-second windows, extracts HRV-related features, and applies the frozen model artifact stored at `app/models/ecg_apnea_hrv_lr_v2.joblib`.

This application is an academic ECG-based screening prototype. Model outputs represent apnea-related patterns detected in 60-second ECG windows and are not a medical diagnosis.

## Overview

The system accepts ECG input as either a JSON payload or a `.csv`/`.txt` file upload, validates the signal format, and returns window-level screening results. It does not persist uploaded recordings or raw ECG arrays and intentionally does not claim a patient diagnosis or clinical severity estimate.

## Architecture

- Backend: FastAPI service for validation, preprocessing, feature extraction, and model inference
- Frontend: React + TypeScript + Vite interface for upload and result visualization
- ML artifact: frozen scikit-learn model (`app/models/ecg_apnea_hrv_lr_v2.joblib`)
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

Swagger UI: `/docs`
ReDoc: `/redoc`

### API endpoints

- `GET /` and `GET /health`
- `GET /api/v1/model-info`
- `POST /api/v1/predict` for a single JSON window
- `POST /api/v1/analyze-samples` for consecutive JSON windows
- `POST /api/v1/analyze-file` for `.csv` or `.txt` file uploads

Example request body:

```json
{
  "sampling_rate": 100,
  "ecg_samples": [0.01, 0.03],
  "include_features": false
}
```

CSV support includes single-column numeric data or a named column such as `ecg`, `ECG`, `signal`, or `amplitude`. Ambiguous files are rejected. Uploaded data is processed in memory and is not persisted.

## Frontend

The frontend is located under `frontend/` and communicates with the backend through `VITE_API_BASE_URL`.

```powershell
cd frontend
npm install
```

Create `.env` from `.env.example` if needed:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Start the backend in one terminal, then run the frontend in another:

```powershell
uvicorn app.main:app --reload
cd frontend
npm run dev
```

The UI supports upload and results viewing for `.csv` and `.txt` files, and keeps results in route state rather than storing them in local browser storage.

## Environment Configuration

The backend reads configuration from environment variables such as:

- `APP_ENV`
- `HOST`
- `PORT`
- `CORS_ORIGINS`
- `MAX_UPLOAD_MB`
- `LOG_LEVEL`

The frontend uses `VITE_API_BASE_URL` to target the local API.

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