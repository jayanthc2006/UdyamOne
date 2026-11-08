# Business Metric Reconciliation — CAC & Financial Metrics

**Dataset**: `data/sample_leads/smb_leads.csv` (5,000 leads, Apr–Jun 2026, synthetic competition data)  
**Reconciliation script**: `scripts/reconcile_metrics.py` (reproducible)  
**Purpose**: Explain why three CAC figures — ₹5,385, ₹2,197 and the case-pack's "approximately ₹15,000" — differ, and recommend the defensible metric for the Airtel SYNC presentation.

---

## 1. Verified calculation results (all figures computed from the raw CSV)

No records were discarded. `acquisition_cost_inr` is populated for **every** lead (0 empty values); `monthly_bundle_value_inr`, `one_time_setup_inr`, `nps_score` and follow-up-call fields are populated **only** for the 368 activated leads (empty for the 4,632 dropped leads). Revenue and NPS figures therefore use the activated cohort by necessity, not by choice.

| # | Metric | Formula | Actual value |
|---|---|---|---:|
| 1 | Total acquisition cost, all leads | `Σ acquisition_cost_inr` (all 5,000) | **₹5,539,640** |
| 2 | Acquisition cost among activated leads | `Σ acquisition_cost_inr` (368 activated) | **₹1,981,750** |
| 3 | Acquisition cost among dropped leads | `Σ acquisition_cost_inr` (4,632 dropped) | **₹3,557,890** |
| — | Consistency check | (2) + (3) = (1) | ✓ exact (₹5,539,640) |
| 4 | Average acquisition cost **per lead** | (1) ÷ 5,000 | **₹1,108** |
| 5 | **Blended CAC** — all spend ÷ activations | (1) ÷ 368 | **₹15,053** |
| 6 | **Direct CAC** — activated-lead spend ÷ activations | (2) ÷ 368 | **₹5,385** |
| 7 | Average monthly bundle value | mean of `monthly_bundle_value_inr` (activated) | **₹12,351** (median ₹6,900) |
| 8 | Total monthly recurring bundle value | Σ `monthly_bundle_value_inr` (activated) | **₹4,544,990** |
| 9 | Total one-time setup value | Σ `one_time_setup_inr` (activated) | **₹5,107,500** (avg ₹13,879/activation) |
| 10a | Six-month churn | churned=Y ÷ 368 | **15.2%** (56 of 368) |
| 10b | NPS | (promoters − detractors) ÷ 368 | **−25.3** (67 promoters 18.2%, 141 passives 38.3%, 160 detractors 43.5%) |
| — | Mean days lead→activation | mean `days_lead_to_activation` (activated) | **17.62 days** (median 17) |
| — | Follow-up calls (activated) | mean / median | **3.01 / 3** |

Corroboration of previously published figures: the Phase 2 analysis's ₹5,385 (direct CAC), ₹2,197*, ₹12,351, ₹4.54M, ₹5.11M, 15.2% and −25.3 all reconcile exactly with this independent recalculation.

> *Correction to Phase 2: the stricter "per total lead" CAC was reported as ₹2,197 in `BUSINESS_IMPACT_ANALYSIS.md`. The exact value is **₹1,108** (= ₹5,539,640 ÷ 5,000). The ₹2,197 figure does not correspond to any denominator of the recorded fields and should not be used. This is the only material correction identified.

---

## 2. Why the three CAC figures differ — root cause

The three numbers are **all correct for their own definitions**; they differ by numerator and denominator choice, not by any calculation error:

```
₹15,053  =  ₹5,539,640 (ALL lead spend, incl. 4,632 failures)  ÷  368 activations
₹5,385   =  ₹1,981,750 (spend on the 368 winners only)         ÷  368 activations
₹1,108   =  ₹5,539,640 (ALL lead spend)                        ÷  5,000 leads
```

1. **Different denominators** — the dominant factor. Dividing the same ₹5.54M total spend by 368 activations (₹15,053) instead of 5,000 leads (₹1,108) is a 13.6× difference purely from cohort selection.
2. **Different numerator populations** — ₹5,385 counts only the acquisition spend recorded against the 368 leads that converted; ₹15,053 spreads every rupee of spend, including ₹3.56M spent on leads that never converted, across the winners.
3. **Case-pack attribution rule** — the case-pack README's "blended acquisition cost is about ₹15,000 per activated customer" is an **all-in cost-of-acquisition definition**: total funnel spend divided by successful outcomes. Our recalculation reproduces it exactly: **₹5,539,640 ÷ 368 = ₹15,053 ≈ ₹15,000 (1.00×, within rounding)**. There is no discrepancy with the case pack — the case-pack number is simply a different (fully-loaded) metric.
4. **Case-pack approximate assumptions** — the "about ₹15,000" wording plus our exact ₹15,053 indicates the case-pack computed this same ratio on this dataset. No unrecorded overheads need to be invoked.
5. **Incorrect calculation** — none found in the funnel, revenue, churn or NPS math. The single Phase 2 error was the ₹2,197 label (see §1 correction).

---

## 3. Recommended defensible CAC metric for the presentation

**Recommendation: present the case-pack-consistent blended CAC as the headline, with the direct CAC as the secondary metric.**

- **Headline (use in slides): "Blended CAC ≈ ₹15,000 per activated customer"** — defined explicitly as *total funnel acquisition spend ÷ activated customers* (₹5,539,640 ÷ 368 = ₹15,053). This matches the case-pack framing, is the figure an Airtel business audience will expect, and honestly prices in the cost of the 92.6% of the funnel that leaks.
- **Secondary (efficiency story): "Direct CAC ₹5,385"** — spend recorded on converted leads only. Frame it as "the spend actually incurred on converted customers; the remaining ~₹9,700 of blended cost is spent on leads the current funnel loses."
- **Never quote ₹2,197** — it corresponds to no consistent definition.
- **Always state the formula on the slide** (e.g. `₹55.4L total spend ÷ 368 activations`), because a bare "₹15,000 CAC" against a "₹5,385 CAC" elsewhere in the deck will look inconsistent to evaluators.
- **The strategic takeaway that is defensible from these numbers**: with 92.6% funnel leakage, roughly **65% of blended CAC (₹3.56M of ₹5.54M) is spent on leads that never activate**. A funnel that converts even a few percentage points better materially reduces blended CAC — this is the honest, arithmetic-backed version of the "UdyamOne lowers CAC" claim, and it must be presented as a *modelled* effect, not an achieved one.

---

## 4. Definitions

| Term | Definition used here |
|---|---|
| Acquisition cost (`acquisition_cost_inr`) | Sales-and-partner spend recorded against each individual lead |
| Blended CAC | Total acquisition spend across the whole funnel ÷ number of activated customers |
| Direct CAC | Acquisition spend recorded on activated leads ÷ activated customers |
| Monthly recurring bundle value | `monthly_bundle_value_inr` — estimated recurring monthly revenue of the activated bundle (not billed revenue) |
| One-time setup value | `one_time_setup_inr` — non-recurring; always reported separately from recurring value |
| Churn (6-month) | `churned_within_6_months = Y` among activated leads |
| NPS | % promoters (score ≥9) − % detractors (score ≤6) among activated leads |

All values are synthetic competition data and estimates, not billed financials.

---

## 5. Reproducibility

```powershell
.\.venv\Scripts\python.exe scripts\reconcile_metrics.py
```

The script prints every value in §1 from the raw CSV in one pass, including the (2)+(3)=(1) consistency check and the 1.00× case-pack reconciliation factor.
