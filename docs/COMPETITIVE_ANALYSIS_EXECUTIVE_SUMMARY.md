# Competitive Analysis — Executive Summary (Presentation-Ready)

**For:** Airtel SYNC 2026 — Project Udyam Digital · Team PulseForge
**Research review date:** 8 November 2026
**Basis:** Public provider pages listed in `docs/competitive_analysis/evidence_register.csv`, UdyamOne prototype code and tests, and Phase 2 analysis of the synthetic lead dataset. Airtel Thanks for Business, JioBusiness services and TTBS iManage FAQ were rechecked on 8 November 2026. Other competitor claims remain subject to the individual revalidation status in the evidence register.

---

## The one-sentence position

**All three incumbents document digital self-care and some form of request or service-status tracking. UdyamOne's proposed differentiation is to integrate guided MSME discovery, catalogue-backed recommendations, instant itemised non-binding quotations, consent-based verification and partner-accountability-visible fulfilment into one customer journey.**

---

## What public research establishes about the three incumbents

| Capability | Airtel Business | JioBusiness | Tata Tele (TTBS) |
|---|---|---|---|
| Business catalogue and enquiry routes | Documented | Documented | Documented |
| Digital self-care and status tracking | Airtel Thanks for Business: account/inventory, bills, service requests, activation/deactivation and request tracking for existing customers and authorised SPOCs | Digital self-care: service management, billing, requests, status tracking, digital onboarding and order-to-delivery | iManage: account/service access, online bill payments, service-request status and new-link status |
| Published pricing | Consumer broadband pricing; business pricing requires further verification | Some SMB plans publish pricing; specific entries require revalidation | Selected Smartflo SKUs have published prices; specific entries require revalidation |
| Instant itemised SMB bundle quotation | Not publicly established in reviewed sources | Not publicly established in reviewed sources | Not publicly established in reviewed sources |
| Business-customer KYC journey | Not publicly established in reviewed sources | Not publicly established in reviewed sources | Not publicly established in reviewed sources |
| Customer-visible fulfilment with partner accountability | Not publicly established in reviewed sources | Not publicly established in reviewed sources | Not publicly established in reviewed sources |
| AI-based requirement discovery in multiple Indian languages | Not publicly established in reviewed sources | Not publicly established in reviewed sources | Not publicly established in reviewed sources |

*Evidence note: “Not publicly established” means the specific capability was not established by the public sources reviewed. It does not mean the provider lacks that capability. Check the per-source revalidation status before presenting individual claims.*

**Important distinction:** Digital self-care and service/request tracking already exist across the three providers. The reviewed sources do not establish the same customer-visible combination of installation milestones, partner assignment, partner progress notes and hold/resume accountability that UdyamOne prototypes.

---

## Where the funnel leaks (Phase 2, n = 5,000 synthetic leads)

- **92.6% of leads never activate.** Lead-to-activation conversion is approximately 7.4%.
- **The quote stage is the largest proportional funnel bottleneck:** 861 of 1,974 assessed leads accepted a quote, a 43.6% acceptance rate and 56.4% drop-off.
- **Common recorded quote-stage objections:** price too high (414), competitor cheaper (207), quote complexity (206) and quote delay (179).
- **273 quote acceptors did not reach KYC completion.** Document-detail mismatch was also recorded as a drop reason (47).
- **Activated customers made a median of three follow-up calls.** The dataset records 98 installations delayed beyond 21 days and 53 cancellations before installation.

These figures identify measurable opportunities to improve quotation clarity, verification and fulfilment communication. They do not prove that any particular prototype feature will achieve a specific uplift.

---

## Three defensible differentiators

*These are prototype capabilities, not claims of proven production superiority.*

1. **Integrated MSME onboarding journey** — guided discovery, catalogue-backed recommendations, itemised non-binding quotation, consent-based KYC, registry checks, order snapshot, operations assignment, partner fulfilment and a customer-visible timeline.

2. **Auditable human-in-the-loop verification** — local OCR, preserved original documents, flagged manual corrections and structured verification outcomes (VERIFIED / MISMATCH / UNAVAILABLE / INCONCLUSIVE). Registry checks currently use synthetic competition datasets, not live government integrations.

3. **Partner-accountability-visible fulfilment** — the prototype customer timeline records assignment, partner progress notes, hold/resume events and activation with actor attribution, role, timestamp and reason.

**Additional capability:** Multilingual conversational discovery in English, Hindi, Telugu, Tamil and Kannada.

---

## Financial framing for slides 1 and 6

See `BUSINESS_METRIC_RECONCILIATION.md` for the formulas and source reconciliation.

- **Blended CAC = ₹15,053 per activation** (₹5,539,640 total acquisition spend ÷ 368 activations).
- **Direct CAC = ₹5,385 per activation** (₹1,981,750 spend attributed to activated leads ÷ 368 activations).
- **Average cost per lead = ₹1,108** (₹5,539,640 ÷ 5,000 leads).
- **The CAC opportunity:** 64.2% of total acquisition spend (₹3,557,890 of ₹5,539,640) is associated with leads that dropped before activation. This is a share of total acquisition spend, not 64.2% of blended CAC.
- **Value concentration:** Small multi-site businesses account for 15.1% of leads but 57% of monthly recurring value, with average monthly value of ₹31,233.
- **Referral channel:** 14.8% activation at ₹605 direct acquisition cost, approximately twice the overall lead-to-activation conversion rate.
- **Baseline quality signal:** NPS −25.3 and six-month churn of 15.2% among activations in the synthetic dataset.

Any improvements in quote acceptance, KYC completion, follow-up calls or CAC are projected scenarios—not achieved results.

---

## Honest boundaries to state on the slide

- UdyamOne is a **competition prototype**, not a production telecom onboarding platform.
- GSTIN and Udyam checks use synthetic competition datasets. No live government API verification is implemented.
- Pricing is estimated and non-binding. Payment processing, billing and commercial contracting are not implemented.
- Activation is simulated. There is no live Airtel OSS/BSS provisioning or field-service integration.
- The prototype uses SQLite and local OCR. Production deployment would require suitable managed infrastructure, security controls and operational integrations.
- The competitor comparison is based on reviewed public sources, not internal portals, private enterprise contracts or provider fulfilment systems.
- Business-impact improvements are modelled scenarios, not experimentally measured results.

---

## Slide-specific recommendations (seven-slide deck)

### Slide 1 — MSME problem and onboarding funnel

**Suggested title:** “Only 7.4% of MSME leads reach activation”

- Funnel visual: 5,000 → 3,406 → 1,974 → **861 (43.6% quote acceptance)** → 588 → 368.
- Callout: **Blended CAC ₹15,053 per activation**.
- Supporting metric: **64.2% of acquisition spend is associated with leads that drop before activation**.
- Drop-reason callouts: price, competitor pricing, quote complexity, quote delay and document mismatch.
- Message: the synthetic funnel identifies specific, measurable friction points across the customer journey.

### Slide 2 — UdyamOne solution

**Suggested title:** “One integrated digital journey for MSMEs”

Show how the solution connects guided discovery, product recommendations, transparent quotations, consent-based verification, order creation and fulfilment visibility instead of treating them as disconnected steps.

### Slide 3 — Product journey and screenshots

**Suggested title:** “From business discovery to tracked order fulfilment”

Show genuine screenshots of the prototype journey:

Advisor → Product recommendations → Itemised quote → Consent and KYC → Registry-check result → Order review → Operations/partner fulfilment → Customer timeline.

Use actual screenshots from the running application. Do not present mockups as implemented screens.

### Slide 4 — Architecture and AI

**Suggested title:** “A modular, explainable onboarding architecture”

Show the Next.js/TypeScript frontend, FastAPI backend, SQLite persistence, local OCR, synthetic registry verification and optional multilingual AI advisor. Clearly distinguish implemented components from optional external AI services and production integrations.

### Slide 5 — Competitive positioning

**Suggested title:** “Integrating capabilities into one MSME journey”

- Matrix summary: Airtel Thanks for Business, JioBusiness and TTBS iManage all document digital self-care and forms of service/request/link tracking.
- Pricing transparency is uneven across the reviewed provider pages; individual pricing evidence remains subject to revalidation.
- Not publicly established in the reviewed sources: instant itemised SMB bundle quotes, integrated MSME-focused AI discovery, auditable customer-facing KYC corrections and a partner-accountability-visible fulfilment lifecycle.
- **Key positioning:** UdyamOne does not claim to invent digital tracking. Its prototype connects discovery, recommendation, quotation, verification and accountable fulfilment into one MSME-oriented flow.
- Evidence disclosure: *“Competitor claims are based on the public provider pages listed in the evidence register. Selected Airtel, Jio and TTBS self-care pages were rechecked on 8 November 2026; other entries retain their individual revalidation status.”*

### Slide 6 — Business impact and unit economics

**Suggested title:** “Reduce funnel leakage and improve acquisition economics”

- Blended CAC: ₹15,053.
- Direct CAC: ₹5,385.
- Acquisition spend associated with dropped leads: 64.2%.
- Small multi-site businesses: 15.1% of leads / 57% of monthly recurring value.
- Label proposed improvements clearly: quote acceptance 43.6% → +8 percentage points; KYC completion 68.3% → +9 percentage points; follow-up calls 3 → reduction of 1, under the moderate modelled scenario.
- Message: improving conversion through the funnel is a potential lever for better acquisition economics—not a measured result.

### Slide 7 — Privacy, security and production roadmap

**Suggested title:** “Prototype controls today; production integrations next”

Cover consent-based KYC, local OCR, role-based access, document-handling controls and audit events. Clearly disclose prototype limitations and the roadmap for live registry integrations, secure production infrastructure, payment processing, identity management, telecom provisioning and monitoring.

---

**Presentation rule:** Distinguish implemented prototype capabilities, publicly documented competitor capabilities, modelled business opportunities and proposed production integrations. Do not present one category as another.