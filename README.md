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

## AI business advisor

The advisor is optional. It returns an explicit `503` response when the backend
LLM provider is not configured. Copy `backend\.env.example` as a reference and
set these variables in the backend process environment:

```powershell
$env:UDYAMONE_LLM_API_KEY = "your-provider-key"
$env:UDYAMONE_LLM_BASE_URL = "https://api.openai.com/v1"
$env:UDYAMONE_LLM_MODEL = "your-compatible-model"
$env:UDYAMONE_LLM_TIMEOUT_SECONDS = "20"
```

Keep the key on the backend; do not use a `NEXT_PUBLIC_` variable. The adapter
posts to the OpenAI-compatible `/chat/completions` endpoint. The provider handles
message interpretation and response wording; the existing recommendation,
eligibility, dependency and pricing services remain authoritative. Chat content
is held only in browser memory and is sent to the configured provider per turn.

`POST /api/v1/advisor/chat` accepts the business profile, segment, current
requirement categories, bounded conversation messages and a language (`en`,
`hi`, `te`, `ta` or `kn`). Its response contains a conversational reply,
validated extracted categories and separately structured catalogue-backed
recommendations when applicable.

## KYC consent and prototype roles

The KYC document workflow requires backend-configured `CUSTOMER` and `REVIEWER`
accounts. Configure `UDYAMONE_KYC_AUTH_SECRET` with a random value of at least
32 bytes and `UDYAMONE_KYC_AUTH_USERS` with JSON account records containing a
username, role, PBKDF2-SHA256 password hash, and applicant IDs for each customer.
Generate a password hash interactively from the `backend` directory with:

```powershell
python -c "from getpass import getpass; from app.security.kyc_auth import hash_password; print(hash_password(getpass()))"
```

Customer consent, its version and timestamp, and reviewer-requested document
types are stored with that applicant's local KYC manifest. Uploads and local OCR
processing are blocked until current consent is recorded. Keep the signing
secret and account configuration in the backend process environment; do not
place them in frontend variables or source control.

This environment-configured authentication is **competition-prototype-only**.
It is not production authentication and does not provide account lifecycle,
password reset, MFA, SSO, or centralized revocation. Do not deploy it as a
production identity system.

## Layout

- `backend/app/api/` — HTTP routes
- `backend/app/models/` — persistence/domain models
- `backend/app/schemas/` — request and response schemas
- `backend/app/services/` — application services
- `backend/tests/` — automated tests
