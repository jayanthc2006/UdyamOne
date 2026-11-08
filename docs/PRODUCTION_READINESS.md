# Production Readiness — UdyamOne Hardening Checklist

**Team**: PulseForge · Airtel SYNC 2026 · Companion to `SECURITY_REVIEW.md` and `PRIVACY_AND_SECURITY_NOTE.md`
**Classification legend**:
- **IMPLEMENTED** — exists in the prototype, verified by code inspection and/or tests.
- **PARTIALLY IMPLEMENTED** — a meaningful subset exists; production gaps remain.
- **NOT IMPLEMENTED** — absent from the prototype.
- **PROPOSED FOR PRODUCTION** — recommended design/roadmap item; *not* an existing feature. Roadmap text elsewhere in the repo is not counted as implementation.

---

## A. Transport & Network

| Requirement | Status | Notes |
|---|---|---|
| HTTPS / secure transport | **NOT IMPLEMENTED** | Prototype runs uvicorn + Next dev on plain HTTP over localhost. TLS termination required at ingress in production. |
| HSTS, security headers at edge | **NOT IMPLEMENTED** | Document-download responses already carry `no-store`, `nosniff`, sandbox CSP, `no-referrer` (implemented at application level); global edge headers are not. |
| CORS hardening | **IMPLEMENTED** (prototype-appropriate) | Explicit origin allow-list; `*` filtered out; restricted methods/headers (`app/main.py`). |

## B. Data Protection

| Requirement | Status | Notes |
|---|---|---|
| Encryption at rest (documents) | **NOT IMPLEMENTED** | Files under `backend/runtime_uploads/` in plaintext. |
| Encryption at rest (database) | **NOT IMPLEMENTED** | Plain SQLite file. |
| Encryption in transit internally | **NOT IMPLEMENTED** | Single-host local prototype. |
| Encrypted object storage + per-object ACLs | **PROPOSED FOR PRODUCTION** | S3-compatible with SSE + presigned URLs. |
| Malware scanning of uploads | **NOT IMPLEMENTED** | Strong format/signature/size validation exists (implemented); AV scanning absent. |
| Backup & disaster recovery | **NOT IMPLEMENTED** | No backup automation; SQLite single-file. |
| Data minimisation & no raw registry duplication | **IMPLEMENTED** | Fingerprint-based verification persistence; generated filenames; minimal fields. |

## C. Identity & Access

| Requirement | Status | Notes |
|---|---|---|
| Four-role authorization matrix | **IMPLEMENTED** | Server-enforced; covered by automated tests (`SECURITY_REVIEW.md` §2). |
| Applicant/partner isolation | **IMPLEMENTED** | Ownership + assignment checks; cross-access 403s tested. |
| Enterprise identity (IdP) | **NOT IMPLEMENTED** | Environment-config JSON accounts (prototype-only by design). |
| MFA / SSO (OAuth2/OIDC) | **NOT IMPLEMENTED** / **PROPOSED FOR PRODUCTION** | |
| Password policy & hashing | **PARTIALLY IMPLEMENTED** | PBKDF2-SHA256 @600k iterations with format validation (implemented); no rotation/expiry/complexity policy management. |
| Session revocation / blocklist | **NOT IMPLEMENTED** | Stateless 30-min HMAC tokens; sign-out is client-side only. |
| Account lifecycle (provision/deactivate) | **NOT IMPLEMENTED** | Accounts are static environment config. |
| Rate limiting / brute-force protection | **NOT IMPLEMENTED** | Session endpoint unthrottled. |

## D. Application & Operations

| Requirement | Status | Notes |
|---|---|---|
| Append-only audit events (order lifecycle) | **IMPLEMENTED** | `order_events` with actor/role/timestamp/reason; immutable order snapshots. |
| KYC correction auditability | **IMPLEMENTED** | `original_value` + `correction_applied` flags preserved. |
| Centralised security audit logging (logins, denials) | **NOT IMPLEMENTED** | Domain events in DB only; no SIEM pipeline. |
| Monitoring & alerting | **NOT IMPLEMENTED** | Health endpoint exists; no metrics/alerts. |
| Rate limiting / DDoS protection | **NOT IMPLEMENTED** | |
| Database concurrency for scale | **NOT IMPLEMENTED** (SQLite + process locks) → **PROPOSED FOR PRODUCTION**: PostgreSQL with row-level locking. | Order operations use `threading.RLock`; single-node assumption documented. |
| Document retention & automated deletion | **NOT IMPLEMENTED** | **No automatic retention, expiry or deletion exists.** Documents persist locally until manually removed. **PROPOSED FOR PRODUCTION**: configurable retention (recommend ~90 days post-decision, subject to Airtel records policy), approved deletion workflow with dual authorisation, and separate long-term retention of minimal audit records (decision, actor, timestamp) after document files are purged. |
| Data backup of KYC manifests | **NOT IMPLEMENTED** | |

## E. Integrations

| Requirement | Status | Notes |
|---|---|---|
| Government registry verification (GSTN / Udyam) | **NOT IMPLEMENTED** — synthetic datasets in prototype; **PROPOSED FOR PRODUCTION**: live/licensed APIs behind the existing `verify-registries` outcome model. | Explicitly disclosed everywhere; a match today is not a government verification. |
| Telecom provisioning (OSS/BSS) | **NOT IMPLEMENTED** — activation simulated; **PROPOSED FOR PRODUCTION**: service-order orchestration; the lifecycle state machine + event audit are the integration surface. | |
| Payments / billing | **NOT IMPLEMENTED** (by design) — quotes are estimated and non-binding. | |
| LLM advisor | **PARTIALLY IMPLEMENTED** | Optional, OpenAI-compatible adapter with 503 fallback; sends only user-typed chat/profile text (never documents). Provider key management is manual env config. |

## F. Prioritized Production Checklist

**P0 — before any real customer data**
1. HTTPS everywhere + edge security headers.
2. Enterprise identity (OAuth2/OIDC) with MFA/SSO; server-side session revocation.
3. Encrypted storage (DB + documents) and managed secrets.
4. Automated retention & approved deletion workflow for KYC documents (with separate audit retention).
5. Malware scanning pipeline for uploads; rate limiting on auth endpoints.

**P1 — production launch**
6. PostgreSQL migration with row-level locking; backups + DR drills.
7. Centralised audit logging (auth events, denials, admin actions) with field masking; monitoring/alerting.
8. Live GSTN/Udyam verification integration; SIEM integration.
9. Dependency/vulnerability management (SCA) and periodic penetration testing.

**P2 — scale & integration**
10. OSS/BSS provisioning integration replacing simulated activation; payments/billing; partner portal hardening; multi-region deployment.

*Nothing in this document should be presented as an achieved compliance certification (no DPDP/ISO 27001/SOC 2 audit has been performed). All PROPOSED items are future work, not existing features.*
