"""Task A - Independent financial metric reconciliation for smb_leads.csv.

Run: .\\.venv\\Scripts\\python.exe scripts\\reconcile_metrics.py
Read-only; computes every required metric from first principles with explicit
formulas and populations. Prints a full audit trail.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "sample_leads" / "smb_leads.csv"


def main() -> None:
    df = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    for col in ("acquisition_cost_inr", "monthly_bundle_value_inr",
                "one_time_setup_inr", "nps_score", "days_lead_to_activation",
                "customer_follow_up_calls"):
        df[col + "_n"] = pd.to_numeric(df[col], errors="coerce")

    total = len(df)
    act = df[df["outcome"] == "Activated"]
    drop = df[df["outcome"] == "Dropped"]
    n_act, n_drop = len(act), len(drop)
    print(f"rows={total} activated={n_act} dropped={n_drop}")

    # empty-string (not recorded) checks
    for col in ("acquisition_cost_inr", "monthly_bundle_value_inr", "one_time_setup_inr"):
        print(f"empty {col}: all={int((df[col]=='').sum())} "
              f"activated={int((act[col]=='').sum())} dropped={int((drop[col]=='').sum())}")

    acq_all = df["acquisition_cost_inr_n"].sum()
    acq_act = act["acquisition_cost_inr_n"].sum()
    acq_drop = drop["acquisition_cost_inr_n"].sum()

    print("\n=== ACQUISITION COST ===")
    print(f"1) total across all leads          : {acq_all:,.0f}")
    print(f"2) among activated leads           : {acq_act:,.0f}")
    print(f"3) among dropped leads             : {acq_drop:,.0f}")
    print(f"   check 2+3==1                    : {abs(acq_act+acq_drop-acq_all) < 1}")
    print(f"4) total / total leads             : {acq_all/total:,.0f}")
    print(f"5) total / activated leads         : {acq_all/n_act:,.0f}")
    print(f"6) activated-lead cost / activated : {acq_act/n_act:,.0f}")

    print("\n=== REVENUE (activated cohort only; fields exist only for activated) ===")
    mrr = act["monthly_bundle_value_inr_n"].sum()
    setup = act["one_time_setup_inr_n"].sum()
    print(f"7) average monthly bundle value    : {act['monthly_bundle_value_inr_n'].mean():,.0f}"
          f"  (median {act['monthly_bundle_value_inr_n'].median():,.0f})")
    print(f"8) total monthly recurring value   : {mrr:,.0f}")
    print(f"9) total one-time setup value      : {setup:,.0f}")
    print(f"   avg setup per activated         : {act['one_time_setup_inr_n'].mean():,.0f}")

    print("\n=== CHURN & NPS (activated only) ===")
    churned = int((act["churned_within_6_months"] == "Y").sum())
    print(f"10a) churned within 6 months       : {churned}/{n_act} = {100*churned/n_act:.1f}%")
    nps = act["nps_score_n"]
    promoters = int((nps >= 9).sum()); detractors = int((nps <= 6).sum()); passives = n_act - promoters - detractors
    print(f"10b) NPS mean {nps.mean():.2f} median {nps.median():.0f} "
          f"promoters {promoters} ({100*promoters/n_act:.1f}%) "
          f"passives {passives} ({100*passives/n_act:.1f}%) "
          f"detractors {detractors} ({100*detractors/n_act:.1f}%) "
          f"=> NPS {100*(promoters-detractors)/n_act:.1f}")

    print("\n=== 17.6-day activation & follow-up checks ===")
    dla = act["days_lead_to_activation_n"]
    print(f"mean days lead->activation: {dla.mean():.2f} median {dla.median():.0f}")
    print(f"mean follow-up calls (activated): {act['customer_follow_up_calls_n'].mean():.2f} "
          f"median {act['customer_follow_up_calls_n'].median():.0f}")

    print("\n=== CAC scenario reconciliations vs case-pack ~Rs 15,000 ===")
    blended_spend_per_activation = acq_all / n_act
    print(f"all-cohort spend / activated            : {blended_spend_per_activation:,.0f}")
    # What if the case-pack used average acquisition cost of ALL leads (not just
    # activated) plus post-activation servicing? Test a few candidate formulas:
    # (a) total spend incl. dropped, per activated  -> above
    # (b) avg cost of ACTIVATED leads only          -> acq_act/n_act
    # (c) monthly_spend analog: avg monthly spend per lead * activation days?
    avg_cost_all_leads = df["acquisition_cost_inr_n"].mean()
    print(f"avg acquisition cost per lead (any lead) : {avg_cost_all_leads:,.0f}")
    # (d) 3x multiplier hypothesis: case-pack blended CAC may include sales
    #     overhead beyond the recorded acquisition_cost_inr field.
    print(f"candidate (d): {avg_cost_all_leads:.0f} x ~7.4? no; "
          f"15,000 / {blended_spend_per_activation:.0f} = {15000/blended_spend_per_activation:.2f}x")


if __name__ == "__main__":
    sys.exit(main())
