# Business Metric Reconciliation — CAC & Financial Metrics

**Dataset:** `data/sample_leads/smb_leads.csv` (5,000 leads, Apr–Jun 2026, synthetic competition data)
**Reconciliation script:** `scripts/reconcile_metrics.py` (reproducible)
**Purpose:** Explain why the case-pack's "approximately ₹15,000" blended CAC, the ₹5,385 direct CAC and the ₹1,108 average acquisition cost per lead differ, and recommend the defensible metrics for the Airtel SYNC presentation.

---

## 1. Verified calculation results (all figures computed from the raw CSV)

No records were discarded. `acquisition_cost_inr` is populated for **every** lead (0 empty values); `monthly_bundle_value_inr`, `one_time_setup_inr`, `nps_score` and follow-up-call fields are populated **only** for the 368 activated leads (empty for the 4,632 dropped leads). Revenue and NPS figures therefore use the activated cohort by necessity, not by choice.

| # | Metric | Formula | Actual value |
|---|---|---|---:|
| 1 | **Total acquisition spend (all leads)** | `Σ acquisition_cost_inr` (all 5,000 leads) | **₹5,539,640** |
| 2 | Total acquisition cost (activated cohort) | `Σ acquisition_cost_inr` (368 activated leads) | **₹1,981,750** |
| 3 | Acquisition cost among dropped leads | `Σ acquisition_cost_inr` (4,632 dropped leads) | **₹3,557,890** |
| — | Consistency check | (2) + (3) = (1) | ✓ Exact (₹5,539,640) |
| 4 | Average acquisition cost **per lead** | (1) ÷ 5,000 | **₹1,108** |
| 5 | **Blended CAC — per activated customer** | (1) ÷ 368 activations | **₹15,053** |
| 6 | **Direct CAC — per activated customer** | (2) ÷ 368 activations | **₹5,385** |
| 7 | Average monthly bundle value | Mean of `monthly_bundle_value_inr` (activated leads) | **₹12,351** (median ₹6,900) |
| 8 | Total monthly recurring bundle value | `Σ monthly_bundle_value_inr` (activated leads) | **₹4,544,990** |
| 9 | Total estimated one-time setup value | `Σ one_time_setup_inr` (activated leads) | **₹5,107,500** (average ₹13,879 per activation) |
| 10a | Six-month churn | `churned_within_6_months = Y` ÷ 368 | **15.2%** (56 of 368) |
| 10b | NPS | (Promoters − detractors) ÷ 368 | **−25.3** (67 promoters, 18.2%; 141 passives, 38.3%; 160 detractors, 43.5%) |
| — | Mean days from lead to activation | Mean `days_lead_to_activation` (activated leads) | **17.62 days** (median 17) |
| — | Follow-up calls (activated customers) | Mean / median | **3.01 / 3** |

**Important distinction:**
- Blended CAC and direct CAC are both measured per activated customer.
- ₹1,108 is the average acquisition spend per lead, including both activated and dropped leads. It is not CAC per activated customer.

Corroboration of previously published figures: the Phase 2 analysis's ₹5,385 direct CAC, ₹12,351 average monthly bundle value, ₹4.54M total monthly bundle value, ₹5.11M estimated one-time setup value, 15.2% churn and −25.3 NPS all reconcile with this independent recalculation.

> **Correction to Phase 2:** The average acquisition cost per total lead was reported as ₹2,197 in an earlier draft of `BUSINESS_IMPACT_ANALYSIS.md`. The correct value is **₹1,108** (= ₹5,539,640 ÷ 5,000), as verified by `scripts/reconcile_metrics.py`. The ₹2,197 figure does not correspond to any denominator of the recorded fields and must not be used. This was the only material correction identified.

---

## 2. Why the three acquisition-cost figures differ — root cause

The three figures are correct for their respective definitions. They differ because they use different numerator and denominator populations.

```text
₹15,053 = ₹5,539,640 (ALL lead acquisition spend)
          ÷ 368 activated customers

₹5,385  = ₹1,981,750 (spend attributed to activated leads only)
          ÷ 368 activated customers

₹1,108  = ₹5,539,640 (ALL lead acquisition spend)
          ÷ 5,000 total leads
```

1. **Different denominators:** This is the dominant factor. Dividing the same ₹5.54M total spend by 368 activations gives ₹15,053 per activated customer. Dividing it by 5,000 leads gives an average of ₹1,108 per lead.

2. **Different numerator populations:** ₹5,385 counts only the acquisition spend attributed to the 368 leads that converted. ₹15,053 spreads all acquisition spend, including ₹3.56M associated with leads that did not convert, across the 368 activated customers.

3. **Case-pack attribution rule:** The case-pack README's "blended acquisition cost is about ₹15,000 per activated customer" uses an all-in acquisition-cost definition: total funnel spend divided by successful outcomes. Our recalculation reproduces it: **₹5,539,640 ÷ 368 = ₹15,053 ≈ ₹15,000**. There is no discrepancy with the case pack.

4. **Case-pack approximate figure:** The case-pack's approximate ₹15,000 figure is consistent with the calculated ₹15,053. No unrecorded overheads need to be assumed.

5. **Earlier calculation error:** The ₹2,197 figure in the earlier Phase 2 draft was incorrect. The correct average acquisition cost per lead is ₹1,108, as shown in section 1.

---

## 3. Recommended defensible metrics for the presentation

**Recommendation: present blended CAC as the headline, direct CAC as the secondary metric, and average acquisition cost per lead only when discussing lead-level spend.**

- **Headline — "Blended CAC = ₹15,053 per activated customer."** This is total acquisition spend divided by activated customers (₹5,539,640 ÷ 368 = ₹15,053). It matches the case-pack framing and includes the cost associated with leads that do not convert.

- **Secondary — "Direct CAC = ₹5,385 per activated customer."** This uses only acquisition spend attributed to the activated leads (₹1,981,750 ÷ 368). It describes the acquisition cost recorded against converted leads, excluding spend attributed to dropped leads.

- **Lead-level metric — "Average acquisition cost = ₹1,108 per lead."** This uses total acquisition spend divided by all 5,000 leads. Do not label this figure as CAC per activated customer.

- **Never quote the earlier ₹2,197 figure.** The correct average acquisition cost per total lead is ₹1,108.

- **Always state the formula on the slide.** For example: `₹5,539,640 total acquisition spend ÷ 368 activations = ₹15,053 blended CAC`. This prevents confusion when the ₹5,385 direct CAC also appears elsewhere in the presentation.

- **Strategic takeaway:** **64.2% of total acquisition spend (₹3,557,890 of ₹5,539,640) is associated with leads that never activate.** This is a share of total acquisition spend, not 64.2% of blended CAC. Improving conversion could reduce blended CAC, but any improvement must be presented as a modelled opportunity, not an achieved outcome.

---

## 4. Definitions

| Term | Definition used here |
|---|---|
| Acquisition cost (`acquisition_cost_inr`) | Sales-and-partner spend recorded against each individual lead |
| Total acquisition spend | Sum of acquisition costs across all 5,000 leads |
| Blended CAC | Total acquisition spend across the whole funnel ÷ number of activated customers |
| Direct CAC | Acquisition spend recorded on activated leads ÷ number of activated customers |
| Average acquisition cost per lead | Total acquisition spend ÷ all leads, including activated and dropped leads |
| Monthly recurring bundle value | `monthly_bundle_value_inr` — estimated recurring monthly value of the activated bundle, not billed revenue |
| One-time setup value | `one_time_setup_inr` — estimated, non-recurring value, reported separately from recurring value and not treated as billed revenue |
| Six-month churn | `churned_within_6_months = Y` among activated leads |
| NPS | Percentage of promoters (score ≥9) minus percentage of detractors (score ≤6) among activated leads |

All values are based on synthetic competition data. Revenue-related fields represent estimates, not verified billed financials.

---

## 5. Reproducibility

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\reconcile_metrics.py
```

The script prints the values in section 1 from the raw CSV in one pass, including the (2) + (3) = (1) consistency check and the case-pack blended-CAC reconciliation.