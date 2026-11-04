# UdyamOne

UdyamOne is a FastAPI backend project. This initial scaffold provides a
health-check endpoint and separates API, model, schema, and service layers.

## Prerequisites

- Python 3.11 or newer
- A working Python installation (the currently registered Microsoft Store
  Python 3.11 installation must be repaired or replaced before setup)

## Setup

From the repository root, create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies and start the development server:

```powershell
pip install -r backend\requirements.txt
Set-Location backend
uvicorn app.main:app --reload
```

The health endpoint is available at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
and returns the current application status.

## Tests

From the `backend` directory:

```powershell
pytest
```

## Layout

- `backend/app/api/` — HTTP routes
- `backend/app/models/` — persistence/domain models
- `backend/app/schemas/` — request and response schemas
- `backend/app/services/` — application services
- `backend/tests/` — automated tests
