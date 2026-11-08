# Competitive Analysis — Executive Summary (Presentation-Ready)

**For**: Airtel SYNC 2026 — Project Udyam Digital · Team PulseForge  
**Basis**: Public provider websites (checked 9 Nov 2026) + UdyamOne prototype code/tests + Phase 2 funnel analysis. Full detail in [`COMPETITIVE_ANALYSIS.md`](COMPETITIVE_ANALYSIS.md); every claim in [`competitive_analysis/evidence_register.csv`](competitive_analysis/evidence_register.csv).

---

## The one-sentence position

> **Incumbents sell through enquiry forms and sales calls; UdyamOne sells through a transparent, trackable digital journey — instant itemised quotes, auditable verification, and customer-visible fulfilment — built exactly where the MSME funnel leaks.**

---

## What public research establishes about the three incumbents

| Capability | Airtel Business | JioBusiness | Tata Tele (TTBS) |
|---|---|---|---|
| Business catalogue & sales-led funnel | ✅ documented | ✅ documented | ✅ documented |
| Published pricing | Consumer broadband ✅ / business sales-led | Some SMB plans ✅ / enterprise enquiry | Selected Smartflo SKUs ✅ (e.g., ₹1,250/user/mo, ₹20k one-time) |
| Instant itemised SMB bundle quote | ❓ not publicly established | ❓ not publicly established | ❓ not publicly established |
| Public business-KYC journey | ❓ not publicly established | ❓ not publicly established | ❓ not publicly established |
| Customer-visible lifecycle incl. partner accountability | ❓ not publicly established | ❓ not publicly established | ❓ not publicly established |
| AI requirement-based discovery (multilingual) | ❓ not publicly established | ❓ not publicly established | ❓ not publicly established |

*❓ = not found on public pages as of 9 Nov 2026. Absence of public evidence is NOT evidence of absence — internal portals, apps and SLAs certainly exist. Always present this as "not publicly established", never as "they don't have it".*

## Where the funnel leaks (Phase 2, n=5,000 synthetic leads)

- **92.6% of leads never activate**; lead→activation conversion 7.4%.
- **Quote stage is the worst transition: 43.6% acceptance** (56.4% drop). Top addressable objections: "price too high" (414), "quote too complex" (206), "quote took too long" (179).
- **273 quote-accepters lost in KYC/paperwork**; "document details did not match" (47) is what registry verification catches early.
- **Activated customers made a median 3 follow-up calls**; "installation delayed beyond 21 days" (98) and "cancelled before install" (53) reflect zero fulfilment visibility.

## Three defensible differentiators (prototype-implemented, production-integration pending)

1. **Instant, itemised, non-binding quote** with explicit ranges and an immutable order snapshot — no public evidence any incumbent offers this for SMB bundles.
2. **Auditable human-in-the-loop verification** — local OCR (documents stay on-premises by design), preserved originals + flagged corrections, structured registry outcomes (VERIFIED / MISMATCH / UNAVAILABLE / INCONCLUSIVE) against synthetic datasets today; live GSTN/Udyam APIs in production.
3. **Accountable fulfilment visibility** — customer timeline shows assignment, partner progress notes, hold/resume and activation with actor, role, timestamp and reason on every event.

## Financial framing for slides 5–6 (see BUSINESS_METRIC_RECONCILIATION.md)

- **Blended CAC ≈ ₹15,000/activation** (₹55.4L total spend ÷ 368 activations = ₹15,053 — matches case pack). **Direct CAC ₹5,385** (spend on converted leads only).
- **The CAC lever**: ~65% of blended CAC (₹3.56M) is spent on the 92.6% of leads that leak. Lifting quote-acceptance is the highest-leverage CAC reduction available — a *modelled* opportunity, not an achieved result.
- **Value concentration**: multi-site businesses = 11% of leads, **57% of monthly recurring value** (₹31,233 avg). Referral channel converts 2× blended (14.8%) at ₹605 direct cost.
- **Baseline quality signal**: NPS −25.3 and 15.2% six-month churn among activations — consistent with an opaque, high-friction process.

## Honest boundaries to state on the slide

- UdyamOne is a **competition prototype**: synthetic registries (no live GSTN/Udyam), estimated non-binding pricing (no payments), simulated activation (no telecom provisioning), SQLite + local OCR.
- Improvements in quote-acceptance, KYC completion and follow-up calls are **projected scenarios** (conservative/moderate/ambitious in the Phase 2 report), not measured outcomes.
- Competitor comparisons rely on public web pages only; internal capabilities may exist but are not publicly established.

## Slide 5 — "Where the funnel leaks (and why it costs ₹15,000 a customer)"

- Funnel visual: 5,000 → 3,406 → 1,974 → **861 (43.6%)** → 588 → 368.
- Callout: blended CAC **≈ ₹15,000**; ~65% of it is spent on leads that never activate.
- Drop-reason mini-cloud: unreachable / price / quote complexity / paperwork.
- Message: *the leaks are process friction, not demand* — and they're measurable.

## Slide 6 — "UdyamOne closes the leaks: one journey, every step accountable"

- Journey strip: Advisor → Recommendations → **Instant itemised quote** → Smart KYC + registry check → Immutable order → Ops assignment → Partner fulfilment → **Activated, tracked**.
- Three differentiator chips: transparent quote · auditable verification · visible fulfilment.
- Baseline vs target KPI chips (labelled *proposed*): quote acceptance 43.6% → +8 pp (moderate scenario); KYC completion 68.3% → +9 pp; follow-up calls 3 → −1.
- Disclosure footer: prototype with synthetic registries, estimated pricing, simulated activation; production roadmap = live GSTN/Udyam APIs, payments, Airtel OSS/BSS integration.
