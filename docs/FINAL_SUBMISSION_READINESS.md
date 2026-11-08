# Final Submission Readiness — UdyamOne (Round 1, Airtel SYNC 2026)

**Team:** PulseForge · **Baseline:** `875eb97` (latest pushed commit on `main`) · **Review date:** 8 November 2026

---

## 1. Engineering Baseline

The following results are from previously recorded runs, documented in `docs/PHASE5_DELIVERY_REPORT.md`. They have not been rerun as part of this documentation review.

| Gate | Command | Recorded result |
|---|---|---|
| Backend regression | `.\.venv\Scripts\python.exe -m pytest backend\tests -q` | **201 passed**, 9 warnings (previously recorded run) |
| Frontend ESLint | `npm.cmd --prefix frontend run lint` | **0 errors, 0 warnings** (previously recorded run) |
| Next.js production build | `npm.cmd --prefix frontend run build` | **Success**; all routes prerendered, including `/kyc`, `/operations`, `/orders` and `/partner` (previously recorded run) |
| Isolated QA E2E | QA harness runner | **29/29 checks passed** (previously recorded run) |

**Baseline working-tree note:** The QA harness, analysis assets and related Phase 5 work were committed through `875eb97` on `main`. This describes the state of that baseline commit, not the current local working tree. Check `git status` before staging or committing further documentation changes.

---

## 2. Manual Browser Testing Plan

**Status: NOT PERFORMED.** No human browser walkthrough has been recorded in the available artifacts. Automated backend and isolated QA results do not establish that the complete frontend journey has been manually verified.

The plan below is ready for execution. Estimated execution time is approximately 20 minutes, excluding setup and troubleshooting. Each step maps to backend behaviour or an identified frontend check.

### Preconditions

Refer to `docs/LOCAL_DEMO_SETUP.md`.

- Backend running on port `8000`.
- Frontend running on port `3000`.
- `UDYAMONE_KYC_AUTH_SECRET` configured with a random value of at least 32 bytes.
- `UDYAMONE_KYC_AUTH_USERS` configured with all four roles: CUSTOMER, REVIEWER, OPERATIONS and PARTNER.
- The CUSTOMER account must have the relevant applicant ID. Other roles should have the appropriate role configuration.
- Use separate browser sessions or private windows when demonstrating different roles.

| # | Flow | Steps | Expected result | Evidence source |
|---|---|---|---|---|
| 1 | Business onboarding | `/get-started` → fill micro-retail Mumbai profile → save | `APPL-…` ID shown; recommendations rendered | `test_applicants.py` |
| 2 | AI advisor | Advisor chat: state need and select language | Reply and extracted requirement categories; HTTP 503 if unconfigured is acceptable only with an honest optional-feature disclosure | `test_advisor.py` |
| 3 | Recommendations | Compare Budget, Recommended and Advanced bundles | GST-gated products excluded without verified GSTIN | `test_recommendations.py` |
| 4 | Quote | Select products → preview quote | Itemised line items, monthly range and setup amount; latest quote persisted | `test_quotes.py`, `test_pricing.py` |
| 5 | Smart KYC and consent | Sign in as CUSTOMER → accept consent checkbox | Upload/OCR controls activate only after consent (`kyc-consent-v2`) | `test_kyc.py` |
| 6 | OCR and corrections | Upload specimen → run OCR → correct a field | Original preserved; `correction_applied` flag shown | `test_kyc.py` correction tests |
| 7 | Registry checks | Run verification | Synthetic test cases: cancelled GSTIN returns MISMATCH; applicable verified sample returns VERIFIED; synthetic-data notice visible | `test_registry_verification.py` |
| 8 | Order placement | `/orders` → tick estimate acknowledgement → place order | HTTP 201; duplicate submission returns 409; quote snapshot frozen; "View My Orders" appears | `test_orders.py` |
| 9 | Operations assignment | Sign out → `/operations` as OPERATIONS → filter → manage order → assign partner with reason | Status `ORDER_PLACED` → `ASSIGNED`; event records actor and reason | `test_orders.py` |
| 10 | Partner fulfilment | `/partner` as PARTNER → open assigned order → progress through IN_PROGRESS, COMPLETED and ACTIVATION_PENDING with notes | Only the partner's own assigned orders are visible; partner cannot set ACTIVATED | `test_orders.py` partner tests |
| 11 | Simulated activation | Sign in as OPERATIONS → transition to ACTIVATED with reason | ACTIVATED status shown; terminal state and audit event recorded | `test_orders.py` |
| 12 | Customer tracking | CUSTOMER → `/orders` → open order | ACTIVATED status, progress steps, complete timeline, unchanged snapshot and appropriate cancellation visibility | `test_orders.py` |
| 13 | Role-matrix negatives | Try `/operations` as CUSTOMER and `/orders/{id}` as unauthorised roles | Expected 401/403 responses and appropriate workspace/access messages | Authorization tests |
| 14 | Responsive layout and navigation | Resize to mobile width; check header links per role and sign-out behaviour | Role-specific links only; signed-out user sees public navigation | Frontend navigation logic; manual check required |

### Error and loading-state checks

Allow approximately five additional minutes.

- Wrong password → expected 401 message.
- Order without a quote → expected 409 message.
- Invalid lifecycle transition → expected 409 response.
- Unsupported upload type → expected 415 response.
- Oversized upload → expected 413 response.
- Backend unavailable → network error banner.
- Empty states → no orders, no assigned orders and zero filter results.

These expectations should be verified in the running application, not assumed from backend tests alone.

### Isolated demo data and reset procedure

- **Recommended:** Use the QA harness for a disposable end-to-end dry run. Set `UDYAMONE_QA_MODE=1`, with `UDYAMONE_DB_PATH` and `UDYAMONE_UPLOAD_ROOT` pointed to temporary locations. `scripts/run_qa_e2e.py` previously recorded 29/29 checks passed against isolated resources.
- **For the recorded demo:** Create a fresh applicant through `/get-started` shortly before recording. Do not reuse K01/K07 or historical team applicants. Generate the quote within the session so the order snapshot is current.
- **Reset, only if necessary:** Follow `docs/DEMO_RUNBOOK.md`, section 4. Stop the backend before deleting the documented disposable SQLite database. Do not delete specimen documents, mock registries or runtime uploads as part of a routine reset.
- **Account provisioning:** CUSTOMER, REVIEWER, OPERATIONS and PARTNER accounts must be configured in `UDYAMONE_KYC_AUTH_USERS` before the demo. Generate password hashes using the instructions in `docs/LOCAL_DEMO_SETUP.md`, section 3.B.

**Important:** Never expose `.env` contents, passwords, signing secrets or API keys while checking demo readiness.

---

## 3. Demonstration Blockers and Risks

| # | Blocker/risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| B1 | Four-role accounts not confirmed on the demo machine. The repository cannot confirm local `.env` configuration; secret files were intentionally not inspected. | Operations/Partner/Reviewer demonstrations may fail at login. | Provision all four roles and the signing secret; test the login matrix in plan step 13. | **Action required before recording** |
| B2 | Optional AI advisor requires LLM credentials and returns HTTP 503 when the provider is not configured. | Advisor demonstration may show an error instead of a conversation. | Configure the provider key locally, or demonstrate the product with the advisor explicitly disclosed as optional and disabled in this environment. | **Decision required** |
| B3 | Earlier browser automation encountered a development-server origin restriction. `allowedDevOrigins` was added to `frontend/next.config.ts` during the earlier development work. | Development-server preview or automation may encounter an origin issue if the setting is absent or incorrect. | Confirm the setting in the current file before using the development server. A production-mode run using `npm run build` followed by `npm start` is an alternative. | **Verify if using dev server** |
| B4 | OCR depends on Windows OCR language capability and runtime availability for the user running the application. | OCR may fail on the demo machine even if it worked elsewhere. | Verify local OCR once with a specimen before recording. The backend should report failure honestly rather than silently substituting a remote provider. | **Verify once** |
| B5 | The 14-step browser walkthrough has not been performed as a recorded manual test. | UI-level defects may remain despite successful API tests. | Execute the browser plan in section 2 and record the result. | **Open — main outstanding item** |
| P3 (accepted) | Header navigation can update approximately two seconds after sign-out due to polling; synthetic registries, estimated pricing and simulated activation are prototype limitations. | Minor presentation friction and scope limitations. | Disclose prototype boundaries and follow the demo runbook. | Accepted with disclosure |

**Code-review qualification:** The earlier Phase 5 review recorded the presence of negative-path handling, user-readable error responses and empty/loading/error states in the frontend. This is not a substitute for manual browser verification. No formal end-to-end human walkthrough has been completed.

---

## 4. Go/No-Go Recommendation

**GO — conditional for recording and final submission preparation.**

The previously recorded engineering baseline includes 201 passing backend tests, clean frontend lint, a successful Next.js production build and 29/29 isolated QA E2E checks. The repository also contains security, architecture, business-impact, competitive-analysis and QA documentation.

These recorded results support proceeding with final preparation, but they do not establish that the current demo machine and browser journey are ready.

### Conditions before recording the demo

1. **Provision all four demo accounts and the signing secret.** Execute the manual browser plan in section 2, especially the role and authorization flows.
2. **Decide the AI advisor demonstration approach.** Either configure the LLM provider locally or present the advisor accurately as an optional feature disabled in this environment.
3. **Verify OCR on the actual demo machine.** Confirm the required Windows OCR language/runtime availability using a specimen document.
4. **Confirm the current working tree and demo configuration.** Check `git status`, frontend origin configuration, environment variables without exposing their values, and the actual application startup path.

After these conditions are addressed, proceed with the seven-slide deck and genuine application screenshots using `docs/DEMO_SCREENSHOT_PLAN.md`.

**Final disclosure:** UdyamOne is a competition prototype. Registry verification uses synthetic datasets, pricing is estimated and non-binding, activation is simulated, and actual telecom provisioning and payment processing are not implemented.