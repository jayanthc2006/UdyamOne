# Final Submission Readiness — UdyamOne (Round 1, Airtel SYNC 2026)

**Team**: PulseForge · **Baseline**: `b2824e4` ("Add Phase 5 updates and documentation") + preserved uncommitted work · **Date**: 9 November 2026

---

## 1. Verified Baseline (executed during this review — no changes made)

| Gate | Command | Actual result |
|---|---|---|
| Backend regression | `.\.venv\Scripts\python.exe -m pytest backend\tests -q` | **201 passed**, 9 warnings in 21.93 s |
| Frontend ESLint | `npm.cmd --prefix frontend run lint` | **0 errors, 0 warnings** (exit 0) |
| Next.js production build | `npm.cmd --prefix frontend run build` | **Success**; all routes prerendered incl. `/kyc`, `/operations`, `/orders`, `/partner` |
| Dependency sanity | import check (fastapi/pydantic) | OK |

**Working tree (preserved, uncommitted, on `main`)** — modified: `README.md`, `backend/app/api/router.py`, `backend/app/main.py`, `backend/app/services/applicant_service.py`, `backend/app/services/kyc_service.py` (QA-mode wiring only; business logic untouched); untracked: 10 documentation files, `docs/business_analysis/`, `docs/competitive_analysis/`, `docs/security/`, QA harness (`backend/app/api/qa.py`) and 4 analysis/QA scripts. Nothing staged or committed.

---

## 2. Manual Browser Testing Plan (to be executed by a human operator)

> **Status: NOT PERFORMED.** Browser automation is excluded from this project's quality gates, and no human walkthrough has been recorded in the available artifacts. The plan below is ready to execute in ~20 minutes. Every step maps to a verified backend behaviour (test file noted), so any frontend mismatch is easy to localize.

**Pre-conditions (from `docs/LOCAL_DEMO_SETUP.md`)**: backend on :8000, frontend on :3000; `UDYAMONE_KYC_AUTH_SECRET` (≥32 bytes) and four accounts in `UDYAMONE_KYC_AUTH_USERS` (CUSTOMER with one applicant ID, REVIEWER, OPERATIONS, PARTNER). Use one normal window per role or private windows.

| # | Flow | Steps | Expected (backend-verified) | Evidence source |
|---|---|---|---|---|
| 1 | Business onboarding | `/get-started` → fill micro-retail Mumbai profile → save | `APPL-…` ID shown; recommendations rendered | `test_applicants.py` |
| 2 | AI advisor | Advisor chat: state need + language | Reply + extracted requirement categories; 503 if unconfigured (acceptable, disclose) | `test_advisor.py` |
| 3 | Recommendations | Compare Budget/Recommended/Advanced bundles | GST-gated products excluded without verified GSTIN | `test_recommendations.py` |
| 4 | Quote | Select products → preview quote | Itemised line items + monthly range + setup; persisted as latest quote | `test_quotes.py`, `test_pricing.py` |
| 5 | Smart KYC + consent | Sign in (CUSTOMER) → accept consent checkbox | Upload/OCR controls activate only after consent (`kyc-consent-v2`) | `test_kyc.py` |
| 6 | OCR & corrections | Upload specimen → run OCR → correct a field | Original preserved; `correction_applied` flag shown | `test_kyc.py` corrections tests |
| 7 | Registry checks | Run verification | K01-style: MISMATCH for cancelled GSTIN; K07-style: VERIFIED with city=Delhi; synthetic-data notice visible | `test_registry_verification.py` |
| 8 | Order placement | `/orders` → tick estimate-acknowledgement → place order | 201; duplicate submit → 409; snapshot frozen; "View My Orders" appears | `test_orders.py` |
| 9 | Operations assignment | Sign out → `/operations` as OPERATIONS → filter → Manage order → assign partner with reason | Status ORDER_PLACED→ASSIGNED; event records actor+reason | `test_orders.py` |
| 10 | Partner fulfilment | `/partner` as PARTNER → open assigned order → IN_PROGRESS → COMPLETED → ACTIVATION_PENDING with notes | Only own orders listed; no ACTIVATED option | `test_orders.py` partner tests |
| 11 | Simulated activation | Back to OPERATIONS → transition to ACTIVATED with reason | Green ACTIVATED badge; terminal state; audit event | `test_orders.py` |
| 12 | Customer tracking | CUSTOMER → `/orders` → open order | ACTIVATED status, progress steps, full timeline, snapshot unchanged, cancel hidden | `test_orders.py` |
| 13 | Role matrix negatives | Try `/operations` as CUSTOMER, `/orders/{id}` as REVIEWER/OPS/PARTNER | 403 messages; correct "wrong workspace" notices | authorization tests |
| 14 | Responsive/navigation | Resize to mobile width; check header links per role, sign-out update | Role-specific links only; signed-out shows public nav | `landing.tsx` logic (not browser-verified) |

**Error/loading-state checks (5 min)**: wrong password (401 message), order without quote (409 message), invalid transition attempt (409), upload wrong file type (415), oversized file (413), backend down (network error banner), empty states (no orders / no assigned orders / zero filter results).

### Isolated demo data & reset procedure
- **Recommended**: use the QA harness for a disposable end-to-end demo dry-run: `UDYAMONE_QA_MODE=1` with `UDYAMONE_DB_PATH`/`UDYAMONE_UPLOAD_ROOT` in a temp folder; `scripts/run_qa_e2e.py` proves the whole lifecycle on an isolated DB (29/29, previously verified).
- **For the recorded demo**: create a *fresh* applicant via `/get-started` minutes before recording (never reuse K01/K07 or the team's historical applicants); generate the quote in-session so the order snapshot is live.
- **Reset (only if needed)**: stop backend → delete `backend/data/applicants.sqlite3` → restart (schema auto-creates). Specimen documents, mock registries and runtime uploads must not be deleted. Documented in `docs/DEMO_RUNBOOK.md` §4.
- **Account provisioning requirement**: PARTNER/OPERATIONS/REVIEWER accounts must exist in `UDYAMONE_KYC_AUTH_USERS` before the demo — generate hashes per `LOCAL_DEMO_SETUP.md` §3.B. **This is the single most common live-demo failure mode.**

---

## 3. Demonstration Blockers & Risks (prioritised)

| # | Blocker/Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| **B1** | **Four-role accounts not yet provisioned on the demo machine** (cannot be confirmed from the repo — `.env` intentionally not read) | Demo cannot cover Operations/Partner slides | Provision all four accounts + secret now; dry-run the login matrix (plan step 13) | **Action required before recording** |
| **B2** | AI advisor needs LLM credentials; returns 503 without them | Step 2 of the demo may show an error instead of a chat | Either configure the provider key locally or script the demo to present advisor as "optional, disabled in this environment" (honest disclosure) | Decision required |
| **B3** | Frontend dev-server origin: browser automation previously hit an origin block; `allowedDevOrigins` was added to `frontend/next.config.ts` (uncommitted) | If the uncommitted change is lost, headless/preview setups may fail again | Keep the change; or record demo against `npm run build && npm start` (production mode, unaffected) | Low risk |
| **B4** | OCR depends on Windows OCR language capability installed for the running user | OCR step could fail on a different machine | Verify once on the demo machine with a specimen before recording (backend reports failure honestly rather than substituting a remote provider) | Verify once |
| **B5** | None of the 14 browser flows has been executed as a recorded walkthrough | Unknown UI-level defects may exist despite passing API tests | Execute the plan in §2; it is fully mapped to backend-verified behaviour | **Open — the main outstanding item** |
| P3 (accepted) | Header nav updates ~2 s after sign-out (polling); synthetic registries; estimated pricing; simulated activation | Minor presentation friction; disclose | Documented in runbook + privacy note | Accepted |

No *genuine* blocker was found in code review: all negative paths return clean HTTP codes with user-readable messages, empty/loading/error states exist in all three workspaces, and the frontend calls role-authorized endpoints (Phase 5 fix).

---

## 4. Go / No-Go Recommendation

**GO — conditional.** The engineering baseline is submission-grade: 201 backend tests, clean lint, clean production build, verified role/authorization matrix, immutable snapshots, append-only audit, complete documentation set (12 docs incl. business, competitive, security), and reproducible analysis/QA scripts.

**Two conditions before recording the demo/presentation:**
1. **Provision the four demo accounts + secret** and run the 20-minute browser plan in §2 at least once (B1, B5). This is the only unverified layer left.
2. **Decide the advisor stance** (configure LLM key vs. honest "optional/disabled" disclosure) to avoid an on-stage 503 (B2).

If those two are done, proceed directly to the seven-slide deck using `DEMO_SCREENSHOT_PLAN.md` and the slide 5–7 content already prepared in the Phase 2–4 documents.
