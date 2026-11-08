"""Task 1 - Data validation of data/sample_leads/smb_leads.csv.

Run: .\\.venv\\Scripts\\python.exe scripts\\validate_leads.py
Prints a validation report. Read-only; no data is modified.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "sample_leads" / "smb_leads.csv"


def main() -> None:
    df = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    print(f"rows={len(df)} cols={len(df.columns)}")

    print("\n-- uniqueness --")
    print(f"unique lead_id: {df['lead_id'].nunique()} of {len(df)}")
    dup_ids = df["lead_id"][df["lead_id"].duplicated()].tolist()
    print(f"duplicated lead_ids: {dup_ids[:10]}{' ...' if len(dup_ids) > 10 else ''}")
    full_dupes = df[df.duplicated()]
    print(f"fully duplicated rows: {len(full_dupes)}")

    print("\n-- missing (empty string) per column --")
    missing = (df == "").sum()
    print(missing[missing > 0].sort_values(ascending=False).to_string())

    print("\n-- categorical distributions --")
    for col in ["lead_source", "segment", "business_type", "city_tier",
                "preferred_language", "stage_reached", "outcome", "drop_reason",
                "has_gstin", "has_udyam", "current_internet", "current_provider",
                "annual_turnover_band", "contact_role"]:
        vc = df[col].value_counts(dropna=False)
        print(f"\n{col} ({df[col].nunique()} unique):")
        print(vc.head(15).to_string())

    print("\n-- numeric fields (coercion check) --")
    for col in ["monthly_telecom_spend_inr", "monthly_bundle_value_inr",
                "one_time_setup_inr", "contract_months",
                "customer_follow_up_calls", "acquisition_cost_inr", "nps_score",
                "employee_count", "num_sites"]:
        coerced = pd.to_numeric(df[col], errors="coerce")
        bad = df.loc[coerced.isna() & (df[col] != ""), col].unique()[:8]
        print(f"{col}: non-numeric non-empty values = {list(bad)!r}")
        empty = int((df[col] == "").sum())
        print(f"  empty: {empty}, min: {coerced.min()}, max: {coerced.max()}")

    print("\n-- boolean-ish fields --")
    for col in ["churned_within_6_months", "has_gstin", "has_udyam"]:
        print(f"{col}: {df[col].value_counts(dropna=False).to_dict()}")

    print("\n-- date fields --")
    date_cols = ["created_date", "contacted_date", "needs_assessed_date",
                 "quote_accepted_date", "kyc_complete_date", "activated_date"]
    for col in date_cols:
        s = df[col].replace("", pd.NA)
        parsed = pd.to_datetime(s, errors="coerce", format="%Y-%m-%d")
        unparsable = df.loc[s.notna() & parsed.isna(), col].unique()[:8]
        print(f"{col}: min={parsed.min()} max={parsed.max()} "
              f"unparsable={list(unparsable)!r} empty={int(s.isna().sum())}")

    print("\n-- stage/outcome consistency --")
    stage_order = ["", "Contacted", "Needs assessed", "Quote accepted",
                   "KYC complete", "Activated"]
    print("stage_reached counts:")
    print(df["stage_reached"].value_counts(dropna=False).to_string())
    print("outcome by stage:")
    print(pd.crosstab(df["stage_reached"], df["outcome"]).to_string())

    activated = df["stage_reached"] == "Activated"
    print(f"\nactivated rows with empty monthly_bundle_value_inr: "
          f"{int((activated & (df['monthly_bundle_value_inr'] == '')).sum())}")
    print(f"activated rows with empty acquisition_cost_inr: "
          f"{int((activated & (df['acquisition_cost_inr'] == '')).sum())}")

    dla = pd.to_numeric(df["days_lead_to_activation"], errors="coerce")
    act_dates = pd.to_datetime(df.loc[activated, "activated_date"].replace("", pd.NA),
                               errors="coerce")
    created = pd.to_datetime(df.loc[activated, "created_date"].replace("", pd.NA),
                             errors="coerce")
    recomputed = (act_dates - created).dt.days
    mismatch = (dla[activated].notna() & recomputed.notna()
                & (dla[activated] != recomputed))
    print(f"days_lead_to_activation mismatches on activated rows: {int(mismatch.sum())}")

    churn_vals = set(df.loc[activated, "churned_within_6_months"].unique())
    print(f"churn values among activated: {churn_vals}")

    nps = pd.to_numeric(df.loc[activated, "nps_score"], errors="coerce")
    print(f"nps among activated: min={nps.min()} max={nps.max()} "
          f"empty={int(nps.isna().sum())}")


if __name__ == "__main__":
    sys.exit(main())
