# Security Review — UdyamOne Prototype (Implementation-Backed)

**Team**: PulseForge · Airtel SYNC 2026 · Review date: 8 November 2026
**Method**: Implementation-backed review of source code, tests and configuration, including the KYC read-authorization remediation documented in Section 8. No intrusive security testing was performed. Every claim below cites the implementing file and, where applicable, the covering automated test.

---

## 1. Authentication & Session Management

| Control | Implementation | Evidence |
|---|---|---|
| Password hashing | PBKDF2-SHA256, 600,000 iterations, 16-byte salt, strict hash format validation on load | `backend/app/security/kyc_auth.py` (`hash_password`, `_parse_password_hash`, `PASSWORD_HASH_ITERATIONS = 600_000`) |
| Session signing | HMAC-SHA256 over versioned payload `v1.<b64 payload>.<b64 sig>`; constant-time comparison | `create_session_token` / `decode_session_token`, `hmac.compare_digest` |
| Session expiry | 30-minute lifetime (`SESSION_LIFETIME_SECONDS = 1_800`); `exp > iat`, `exp > now`, small `iat` skew tolerance (60 s) enforced | `decode_session_token`; tests: `test_kyc_auth.py::test_expired_and_malformed_sessions_are_rejected` (expired + malformed rejected), `test_orders.py::test_invalid_or_expired_session_token_rejected` |
| Account source | Backend-only environment configuration (`UDYAMONE_KYC_AUTH_SECRET` ≥32 bytes, `UDYAMONE_KYC_AUTH_USERS` JSON); validation of usernames/roles/hash format; duplicate usernames rejected; requires ≥1 CUSTOMER and ≥1 non-CUSTOMER | `load_kyc_auth_configuration`; `docs/LOCAL_DEMO_SETUP.md` documents setup without publishing credentials |
| Sign-out semantics | Frontend removes token from `sessionStorage` (`frontend/app/*/page.tsx` `signOut`) | **Limitation**: stateless tokens remain cryptographically valid until expiry; no server-side revocation exists. Header navigation reflects sign-out within ~2 s via poll/`storage` events (`frontend/components/landing.tsx`) |

**Roles**: `KycRole = Literal["CUSTOMER", "REVIEWER", "OPERATIONS", "PARTNER"]` in both `backend/app/security/kyc_auth.py` and `backend/app/models/kyc_auth.py`.

## 2. Role-Permission Matrix (server-enforced)

| Capability | CUSTOMER | REVIEWER | OPERATIONS | PARTNER | Enforcing code | Test evidence |
|---|---|---|---|---|---|---|
| Own applicant KYC view/consent/upload/OCR/corrections | ✅ own only | ❌ | ❌ | ❌ | `require_kyc_read_access` for KYC read; `require_kyc_role(CUSTOMER)` + `require_applicant_access` for consent/upload/OCR/corrections (`api/kyc.py`) | `test_kyc.py`, `test_kyc_auth.py` |
| Document review, additional-doc requests, finalize | ❌ | ✅ | ❌ | ❌ | `require_kyc_role(REVIEWER)` (`api/kyc.py`) | `test_kyc.py` reviewer tests |
| Place order, view/cancel own orders | ✅ own only | ❌ | ❌ | ❌ | `api/orders.py` role + ownership checks | `test_orders.py` (incl. cross-applicant 403s) |
| Operations list/search/detail, assign/reassign, lifecycle transitions incl. simulated activation | ❌ | ❌ | ✅ | ❌ | `api/operations.py` + `TRANSITION_ROLES` matrix (`models/order.py`) | `test_orders.py` (reviewer/ops/partner blocked; assignment tests) |
| View assigned orders, fulfilment transitions, hand-off to ACTIVATION_PENDING | ❌ | ❌ | ❌ | ✅ assigned-only | `api/partner.py` validates active assignment = session username | `test_partner_cannot_access_unassigned_order`, `test_partner_cannot_access_another_partners_order`, `test_partner_cannot_reassign_orders` |
| Access KYC documents | ✅ own | ✅ workflow | ❌ | ❌ (no KYC routes exist for partners) | `require_kyc_read_access` on `GET /{applicant_id}` and `GET /{applicant_id}/documents/{document_type}/file` (`api/kyc.py`); rejects OPERATIONS/PARTNER with 403 (`security/kyc_auth.py`) | `test_kyc_auth.py` role-based 403 tests |
| Invalid state transitions | 409 | 409 | 409 | 409 | `PERMITTED_TRANSITIONS` | `test_invalid_transition_rejected`, terminal-state tests |

Endpoint separation is deliberate and tested: applicant onboarding/quote routes are intentionally unauthenticated so the pre-KYC browser flow works (see below). KYC assessment and document routes are then authenticated and role-gated.

| Unauthenticated applicant routes (no session/role dependency) | Endpoint | Pre-KYC behaviour | Data exposure if applicant ID known |
|---|---|---|---|
| POST | /api/v1/applicants | Create a new applicant identity + initial recommendation set | N/A (creates new applicant) |
| PUT | /api/v1/applicants/{applicant_id} | Update the profile and regenerate recommendations | Profile fields (business type, city, employee count, segment, requirements, GSTIN status) are overwritten with the supplied values; recommendations are replaced; existing quote_previews for this applicant are deleted |
| GET | /api/v1/applicants/{applicant_id} | Reload the saved profile, recommendations and refreshed registry eligibility | Profile fields + latest saved quote/eligibility state |
| POST | /api/v1/applicants/{applicant_id}/quotes/preview | Compute and persist a quote preview against the saved profile | Same profile + price/quote state as saved preview |

No registered customer session is required to call any of these routes. They exist solely to support the current pre-KYC onboarding flow (a browser can complete onboarding and receive recommendations without consent), and they do not create KYC assessments, perform OCR, or write KYC documents.

Knowing an applicant ID may therefore allow the caller to access, modify or seed pre-KYC profile data on any applicant. This is accepted prototype behaviour: IDs are opaque `APPL-` hex strings, but are **not** an authorization boundary. Opaque IDs reduce enumeration risk. An authenticated applicant ownership check is required before any real customer-data or production use.

- **No session required** on applicant routes; `get_current_kyc_principal` is not applied to them.

## 3. KYC Document Pipeline Security

- **Upload validation** (`api/kyc.py::upload_kyc_document` + `kyc_service._validate_upload`): MIME allow-list (PNG/JPEG/PDF); magic-byte signature match; Pillow `verify()` + 30-megapixel cap; pypdfium parse with 10-page cap and `%%EOF` presence check; 10 MB cap enforced *during streaming* (headers can lie). Client-supplied filenames are not retained — storage names are generated.
- **Consent gating**: `require_current_consent` blocks upload, OCR and registry checks until the current consent version is recorded (`kyc-consent-v2`); version + timestamp persisted with the applicant manifest.
- **Local OCR boundary**: OCR is Windows.Media.OCR via PowerShell + pypdfium2 + Pillow — **no network calls in the document path** (code inspection of `kyc_service.py`; no `requests/httpx/urllib` imports in document services). The AI advisor (`backend/app/services/advisor*`) is the only outbound LLM call and transmits only user-typed chat/profile text — never document bytes. Distinct pipelines, documented in `docs/security/THREAT_REGISTER.md`.
- **Download protection**: `FileResponse` with `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: sandbox; default-src 'none'`, `Referrer-Policy: no-referrer`; path is backend-resolved (no client-controlled paths); filename normalised to `{document_type}{ext}`.
- **Corrections & review auditability**: originals preserved (`original_value`), corrections flagged (`correction_applied`), review decisions stored separately; finalisation explicitly "not production approval" (message text in `api/kyc.py::finalize_kyc`).

## 4. Registry Verification Integrity

`registry_verification_service.py` persists per applicant+registry: status, reason, checked_at, dataset filename, compared/mismatched field names, and a **one-way input fingerprint** — not registry rows, not submitted identifiers. Verification inputs come from OCR/corrected fields and the saved applicant profile, never from client claims. Outcomes feed GST-gated eligibility through persisted state. Synthetic-data disclosure is enforced in consent v2 and UI text.

## 5. Transport, CORS, Storage & Configuration

- **CORS** (`app/main.py`): explicit origin allow-list from `UDYAMONE_ALLOWED_ORIGINS` (defaults to localhost:3000 dev origins); wildcard `*` is explicitly filtered out; methods/headers restricted to what the app uses.
- **Runtime storage**: `backend/runtime_uploads/` (git-ignored). Documents unencrypted at rest on local disk — acceptable for prototype, a production gap.
- **Database**: SQLite with foreign keys on order tables; applicant/order data isolated per applicant via ownership checks. Process-level `threading.RLock` guards; no multi-node safety.
- **Secrets**: `.env` git-ignored; frontend uses only `NEXT_PUBLIC_API_BASE_URL`; QA-mode credentials injected in-memory by test harnesses (`test_orders.py`, QA runner) — no hardcoded credentials in source.
- **Logging**: no structured logging of document contents or identifiers identified in document services; error handlers map domain exceptions to generic HTTP codes without tracebacks. No centralised audit-log system exists (gap).

## 6. Data Minimisation Checklist (evidence)

| Practice | Status | Evidence |
|---|---|---|
| No unnecessary PII collection | ✅ | Profile fields limited to business attributes; no payment/biometric collection |
| Client filenames not retained | ✅ | Generated storage names in `kyc_service.py` |
| No raw registry duplication | ✅ | Fingerprint + outcome only (`registry_verifications` table) |
| Downloads restricted by applicant + role | ✅ | require_kyc_read_access on the document-download route |
| Identifier masking in logs/UI | ⚠️ Partial | No logging of identifiers found; but no deliberate masking/truncation layer either — order/applicant IDs appear in full in URL paths and UI |
| Encryption at rest | ❌ | Not implemented |
| Automatic retention/deletion | ❌ **absent** | No purge/expiry code exists — stated honestly in `PRIVACY_AND_SECURITY_NOTE.md` |

## 7. Test-Coverage Backing (security-relevant)

- 205 backend tests passing (pytest), including: four-role authentication; expired/malformed/tampered session rejection; unauthenticated rejection across order endpoints; cross-applicant order access/cancel denial; partner assignment-boundary denials; reviewer-only KYC review; consent-gated processing; registry outcome persistence; duplicate-order and invalid-transition rejection; terminal-state immutability; **KYC read authorization: CUSTOMER own/other isolation, REVIEWER read access, OPERATIONS/PARTNER 403 on assessment and document-download routes** (`test_kyc_auth.py`).
- 29/29 isolated API E2E checks (previously verified run, not rerun in this review) covering the full lifecycle and negative authorization paths.

## 8. Findings & Recommendations

1. **No server-side session revocation** — sign-out is client-side only. (Production: revocation list / short TTL + refresh.)
2. **No automatic document retention/deletion** — indefinite local retention. (Production: configurable retention + approved deletion workflow; audit records kept separately.)
3. **No malware scanning** of uploads — signature/format checks only. (Production: AV pipeline.)
4. **No rate limiting / brute-force protection** on the session endpoint. (Production: limiter + lockout.)
5. **No encryption at rest** for documents or SQLite. (Production: encrypted object storage + managed DB.)
6. **No centralised audit logging** — domain events exist in DB (order events), but no security audit trail (logins, denials). (Production: SIEM-feeding audit log with field masking.)
7. **Reviewer scope is global** — reviewers can access any applicant by workflow design; acceptable for prototype, should be scoped in production RBAC.
8. **KYC read authorization hardened** — `GET /api/v1/kyc/{applicant_id}` and `GET /api/v1/kyc/{applicant_id}/documents/{document_type}/file` now use a shared `require_kyc_read_access` guard (`backend/app/security/kyc_auth.py`) that allows CUSTOMER (own applicant) and REVIEWER, and rejects OPERATIONS and PARTNER with HTTP 403. Previously these read endpoints only enforced CUSTOMER ownership, so OPERATIONS/PARTNER could read KYC records. Covered by regression tests in `backend/tests/test_kyc_auth.py` (CUSTOMER own/other isolation, REVIEWER read access, OPERATIONS/PARTNER 403 on both endpoints).
