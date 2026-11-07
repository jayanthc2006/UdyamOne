# Local Prototype Setup & Configuration Guide

**Product**: UdyamOne  
**Competition**: Airtel SYNC 2026 (Track A: Project Udyam Digital)  
**Team**: PulseForge  
**Target Environment**: Local Windows / macOS / Linux Development Machine  

---

## 1. System Prerequisites

- **Python**: Version 3.11 or newer.
- **Node.js**: Version 18.17 or newer (Node 20+ recommended).
- **npm**: Version 9 or newer.
- **OS**: Windows 10/11 (required for local Windows OCR integration), macOS, or Linux.

---

## 2. Backend Setup & Startup

### A. Create Virtual Environment & Install Dependencies
From the repository root directory:

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# (On macOS/Linux: source .venv/bin/activate)

# Install backend dependencies
pip install -r backend\requirements.txt
```

### B. Environment Configuration
Backend configuration is managed via environment variables. Create or configure a local `.env` file in the `backend/` directory or export variables in your active shell.

> **CRITICAL SECURITY NOTE**: Never commit `.env` files, production secrets, API keys, or raw passwords to source control. Use the placeholders provided below.

#### Key Environment Variables

| Variable Name | Required | Description | Example / Default |
| :--- | :---: | :--- | :--- |
| `UDYAMONE_KYC_AUTH_SECRET` | **Yes** | Signing secret for prototype HMAC-SHA256 session tokens. Minimum 32 bytes. | `your-random-32-byte-secret-key-here-1234` |
| `UDYAMONE_KYC_AUTH_USERS` | **Yes** | JSON-encoded array of prototype account objects. | See Section 3 for configuration schema. |
| `UDYAMONE_LLM_API_KEY` | Optional | API key for OpenAI-compatible AI Business Advisor. | `sk-...` |
| `UDYAMONE_LLM_BASE_URL` | Optional | Base URL for the LLM provider. | `https://api.openai.com/v1` |
| `UDYAMONE_LLM_MODEL` | Optional | Model identifier. | `gpt-4o-mini` |
| `UDYAMONE_KYC_REQUIRED_DOCUMENTS` | Optional | Comma-separated list of mandatory KYC document types. | `gst_certificate,signatory_id` |

### C. Start FastAPI Backend Server
From the repository root:

```powershell
Set-Location backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Verify backend health by opening [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health). Expected response: `{"status": "ok"}`.

---

## 3. Prototype Account Configuration

UdyamOne uses signed sessions verified against backend-configured accounts. There is no public user registration in this competition prototype.

### A. Role Matrix & Permissions

| Role | Permitted Workspaces & Capabilities | Applicant Ownership Constraint |
| :--- | :--- | :--- |
| `CUSTOMER` | Complete onboarding, run advisor, preview quotes, manage KYC documents & consent, run registry checks, place orders, cancel own unassigned orders, track orders at `/orders`. | Must be explicitly linked to one or more `applicant_ids`. Cannot access other applicants. |
| `REVIEWER` | Review uploaded KYC documents (`VALID` / `INVALID`), inspect OCR extractions, request additional documents via `/kyc`. | System reviewer. No order or operations permissions. |
| `OPERATIONS` | Access `/operations`, search and filter orders, assign/reassign partners, execute lifecycle transitions (Hold, Resume, Cancel), trigger simulated activation. | Unrestricted operational view across all orders. |
| `PARTNER` | Access `/partner`, view orders currently assigned to this partner, record fulfilment progress notes, advance fulfilment stages to `ACTIVATION_PENDING`. | Strictly restricted to orders where `partner_username` matches active assignment. |

### B. Generating Password Hashes
Generate salted PBKDF2-SHA256 password hashes using the backend security module:

```powershell
# Run from repository root
.\.venv\Scripts\python.exe -c "from getpass import getpass; from backend.app.security.kyc_auth import hash_password; print(hash_password(getpass('Enter password: ')))"
```
*(Passwords must be at least 12 characters).*

### C. Example `UDYAMONE_KYC_AUTH_USERS` Configuration
Set the following JSON string in your environment (replace hashes with your generated values):

```json
[
  {
    "username": "customer_demo",
    "role": "CUSTOMER",
    "password_hash": "pbkdf2_sha256$600000$EXAMPLE_SALT$EXAMPLE_DIGEST",
    "applicant_ids": ["APPL-demo00000000000000000000000001"]
  },
  {
    "username": "reviewer_demo",
    "role": "REVIEWER",
    "password_hash": "pbkdf2_sha256$600000$EXAMPLE_SALT$EXAMPLE_DIGEST",
    "applicant_ids": []
  },
  {
    "username": "ops_demo",
    "role": "OPERATIONS",
    "password_hash": "pbkdf2_sha256$600000$EXAMPLE_SALT$EXAMPLE_DIGEST",
    "applicant_ids": []
  },
  {
    "username": "partner_demo",
    "role": "PARTNER",
    "password_hash": "pbkdf2_sha256$600000$EXAMPLE_SALT$EXAMPLE_DIGEST",
    "applicant_ids": []
  }
]
```

---

## 4. Frontend Setup & Startup

From the repository root in a separate terminal:

```powershell
Set-Location frontend

# Install Node dependencies
npm install

# Start Next.js development server
npm run dev
```

The frontend application will be accessible at [http://127.0.0.1:3000](http://127.0.0.1:3000).

---

## 5. End-to-End Walkthrough Demonstration

1. **Step 1: Guided Onboarding (`/get-started`)**
   - Fill in business profile: Business Name, City Tier, Employee Count, Segment, Primary Requirements.
   - Click "Save and view recommendations". Note the generated `APPL-...` ID stored in session storage.
2. **Step 2: Quotation Preview**
   - Review recommended bundles (Budget, Recommended, Advanced).
   - Select product quantities and preview estimated monthly and setup pricing.
3. **Step 3: Smart KYC & Synthetic Registry Verification (`/kyc`)**
   - Sign in using your configured `CUSTOMER` credentials.
   - Accept document-processing consent (`kyc-consent-v2`).
   - Run synthetic registry checks (`POST /verify-registries`).
4. **Step 4: Order Conversion (`/orders`)**
   - Navigate to "My Orders" via the top navigation bar.
   - Review the latest persisted quote estimate.
   - Check the explicit confirmation box acknowledging that pricing is estimated.
   - Click **Confirm and place order**. An immutable order snapshot is created in status `ORDER_PLACED`.
5. **Step 5: Operations Partner Assignment (`/operations`)**
   - In a private/incognito window or after signing out, sign in with your `OPERATIONS` credentials.
   - The navigation updates to show **Operations Dashboard**.
   - Search or filter for `ORDER_PLACED`. Click **Manage order**.
   - Assign to `partner_demo` with reason `"Zone coverage"`. Order status moves to `ASSIGNED`.
6. **Step 6: Partner Fulfilment (`/partner`)**
   - Sign in with your `PARTNER` credentials (`partner_demo`).
   - The navigation updates to show **Partner Workspace**.
   - Open the assigned order, update status to `FULFILMENT_IN_PROGRESS` with progress note `"Site survey complete"`.
   - Update status to `FULFILMENT_COMPLETED` with note `"Fibre termination verified"`.
   - Advance order to `ACTIVATION_PENDING`.
7. **Step 7: Simulated Activation (`/operations`)**
   - Re-access the order as Operations.
   - Apply lifecycle transition to `ACTIVATED` with note `"Simulated prototype activation"`.
8. **Step 8: Customer Tracking Verification (`/orders`)**
   - Re-access the order as Customer.
   - View updated `ACTIVATED` badge, progress steps, and chronological event audit log.

---

## 6. Running Automated Tests & Quality Checks

All automated tests use isolated temporary SQLite databases and mock environments without mutating local runtime data.

```powershell
# Run complete backend pytest suite
.\.venv\Scripts\python.exe -m pytest backend\tests -q

# Run frontend ESLint check
npm.cmd --prefix frontend run lint

# Run Next.js production build check
npm.cmd --prefix frontend run build
```
