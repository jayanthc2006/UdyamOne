"""Reproducible business analysis of data/sample_leads/smb_leads.csv.

Run from the repository root:
    .\\.venv\\Scripts\\python.exe scripts\\analyze_leads.py

Outputs aggregate CSVs and PNG charts into docs/business_analysis/.
Uses aggregate statistics only; no individual identifiers are printed or saved.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "sample_leads" / "smb_leads.csv"
OUT = ROOT / "docs" / "business_analysis"
OUT.mkdir(parents=True, exist_ok=True)

NAVY = "#10223e"
RED = "#c93835"
GREY = "#8b96a5"
GREEN = "#28613a"

plt.rcParams.update({
    "font.size": 11,
    "axes.edgecolor": "#dfe5eb",
    "axes.labelcolor": NAVY,
    "text.color": NAVY,
    "xtick.color": NAVY,
    "ytick.color": NAVY,
    "figure.dpi": 150,
})

# ---------------------------------------------------------------- helpers


def pct(numerator: float, denominator: float) -> float:
    return round(100.0 * numerator / denominator, 1) if denominator else float("nan")


def save_table(df: pd.DataFrame, name: str) -> None:
    df.to_csv(OUT / f"{name}.csv", index=True)


def save_chart(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight")
    plt.close(fig)


def bar_labels(ax, bars, values, fmt="{:.1f}%"):
    for bar, value in zip(bars, values):
        ax.annotate(
            fmt.format(value),
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            ha="center", va="bottom", fontsize=9, color=NAVY,
        )


# ---------------------------------------------------------------- load

df = pd.read_csv(CSV, dtype=str, keep_default_na=False)
for col in ("employee_count", "num_sites", "monthly_telecom_spend_inr",
            "monthly_bundle_value_inr", "one_time_setup_inr", "contract_months",
            "customer_follow_up_calls", "acquisition_cost_inr", "nps_score",
            "days_lead_to_activation"):
    df[col + "_n"] = pd.to_numeric(df[col], errors="coerce")

STAGES = ["Lead", "Contacted", "Needs assessed", "Quote accepted",
          "KYC complete", "Activated"]
STAGE_DATES = ["contacted_date", "needs_assessed_date", "quote_accepted_date",
               "kyc_complete_date", "activated_date"]

summary: dict[str, object] = {"total_leads": len(df)}

# ---------------------------------------------------------------- task 2: funnel

# stage_reached is the last stage the lead reached; reached counts are cumulative
# because every lead that reached stage N also reached stages 1..N-1.
reached = {stage: int((df["stage_reached"] == stage).sum()) for stage in STAGES}
cumulative: dict[str, int] = {}
total = len(df)
running = 0
for stage in STAGES:
    if stage == "Lead":
        cumulative[stage] = total
        running = total
        continue
    # cumulative = leads that reached this stage or beyond
    idx = STAGES.index(stage)
    cumulative[stage] = int(df["stage_reached"].isin(STAGES[idx:]).sum())

funnel_rows = []
for i, stage in enumerate(STAGES):
    n = cumulative[stage]
    prev_n = cumulative[STAGES[i - 1]] if i else n
    drop = prev_n - n
    funnel_rows.append({
        "stage": stage,
        "leads_reached": n,
        "conversion_from_previous_pct": pct(n, prev_n) if i else 100.0,
        "conversion_from_lead_pct": pct(n, total),
        "drop_off_from_previous": drop,
        "drop_off_pct_of_previous": pct(drop, prev_n) if i else 0.0,
    })
funnel = pd.DataFrame(funnel_rows).set_index("stage")
save_table(funnel, "funnel")
summary["funnel"] = funnel.to_dict(orient="index")

# ---------------------------------------------------------------- task 3: segments

DROPPED = df["outcome"] == "Dropped"
ACTIVATED = df["outcome"] == "Activated"


def conversion_table(by: str, min_n: int = 30) -> pd.DataFrame:
    grp = df.groupby(by)
    table = grp.agg(
        leads=("lead_id", "size"),
        activated=("outcome", lambda s: int((s == "Activated").sum())),
    )
    table["activation_rate_pct"] = (100 * table["activated"] / table["leads"]).round(1)
    table["avg_monthly_bundle_value_inr"] = grp["monthly_bundle_value_inr_n"].mean().round(0)
    table["avg_acquisition_cost_inr"] = grp["acquisition_cost_inr_n"].mean().round(0)
    table = table[table["leads"] >= min_n].sort_values("activation_rate_pct", ascending=False)
    return table


for col, name in [("lead_source", "by_lead_source"),
                  ("segment", "by_segment"),
                  ("city_tier", "by_city_tier"),
                  ("business_type", "by_business_type"),
                  ("preferred_language", "by_language"),
                  ("current_provider", "by_current_provider")]:
    save_table(conversion_table(col), name)

df["employee_band"] = pd.cut(df["employee_count_n"], [0, 5, 20, 50, 200],
                             labels=["1-5", "6-20", "21-50", "51+"])
save_table(conversion_table("employee_band"), "by_employee_band")
df["sites_band"] = pd.cut(df["num_sites_n"], [0, 1, 3, 20], labels=["1", "2-3", "4+"])
save_table(conversion_table("sites_band"), "by_sites_band")

# city level (report all, but flag small samples in the doc)
city = conversion_table("city", min_n=1)
save_table(city, "by_city")

# ---------------------------------------------------------------- task 4: drop reasons

dropped = df[DROPPED]
stage_of_drop = dropped["stage_reached"].value_counts().rename("dropped_leads")
drop_stage = pd.DataFrame(stage_of_drop)
drop_stage["pct_of_all_dropped"] = (100 * drop_stage["dropped_leads"] / len(dropped)).round(1)
save_table(drop_stage, "drop_by_stage")

reasons = dropped["drop_reason"].replace("", "Not recorded").value_counts()
drop_reasons = reasons.rename_axis("drop_reason").rename("count").to_frame()
drop_reasons["pct_of_dropped"] = (100 * drop_reasons["count"] / len(dropped)).round(1)
save_table(drop_reasons, "drop_reasons")

# follow-up calls: converted vs dropped, and by stage
followups = df.groupby("outcome")["customer_follow_up_calls_n"].agg(["mean", "median", "max"])
save_table(followups, "followup_calls_by_outcome")
fu_stage = df.groupby("stage_reached")["customer_follow_up_calls_n"].agg(
    ["mean", "median", "count"]).round(2)
save_table(fu_stage, "followup_calls_by_stage")

# ---------------------------------------------------------------- task 5: unit economics

act = df[ACTIVATED].copy()
summary["activated_count"] = len(act)
total_monthly = act["monthly_bundle_value_inr_n"].sum()
total_setup = act["one_time_setup_inr_n"].sum()
total_acq = act["acquisition_cost_inr_n"].sum()
churn_rate = pct(int((act["churned_within_6_months"] == "Y").sum()), len(act))
nps = act["nps_score_n"]

econ = {
    "activated_leads": len(act),
    "total_monthly_bundle_value_inr": int(total_monthly),
    "avg_monthly_bundle_value_inr": round(total_monthly / len(act), 0),
    "median_monthly_bundle_value_inr": float(act["monthly_bundle_value_inr_n"].median()),
    "total_one_time_setup_inr": int(total_setup),
    "total_acquisition_cost_inr": int(total_acq),
    # CAC denominators stated explicitly:
    "cac_per_activated_lead_inr": round(total_acq / len(act), 0),
    "cac_per_total_lead_inr": round(df["acquisition_cost_inr_n"].sum() / len(df), 0),
    "churn_within_6_months_pct": churn_rate,
    "nps_mean": round(nps.mean(), 2),
    "nps_median": float(nps.median()),
    "nps_min": int(nps.min()),
    "nps_max": int(nps.max()),
    "nps_promoters_pct": pct(int((nps >= 9).sum()), nps.notna().sum()),
    "nps_detractors_pct": pct(int((nps <= 6).sum()), nps.notna().sum()),
    "nps_net": round(
        100 * ((nps >= 9).sum() - (nps <= 6).sum()) / nps.notna().sum(), 1),
}
econ_table = pd.Series(econ, name="value").to_frame()
save_table(econ_table, "unit_economics")
summary["unit_economics"] = econ

# contract months distribution among activated
save_table(act["contract_months"].value_counts().rename_axis("contract_months")
           .rename("count").to_frame(), "contract_months_distribution")

# revenue vs acquisition cost by segment and source (activated only)
seg_econ = act.groupby("segment").agg(
    activated=("lead_id", "size"),
    monthly_value_sum=("monthly_bundle_value_inr_n", "sum"),
    monthly_value_avg=("monthly_bundle_value_inr_n", "mean"),
    setup_sum=("one_time_setup_inr_n", "sum"),
    acq_sum=("acquisition_cost_inr_n", "sum"),
    acq_avg=("acquisition_cost_inr_n", "mean"),
    churn_n=("churned_within_6_months", lambda s: int((s == "Y").sum())),
).round(0)
seg_econ["cac_per_activated_inr"] = (seg_econ["acq_sum"] / seg_econ["activated"]).round(0)
save_table(seg_econ, "economics_by_segment")

src_econ = act.groupby("lead_source").agg(
    activated=("lead_id", "size"),
    monthly_value_sum=("monthly_bundle_value_inr_n", "sum"),
    monthly_value_avg=("monthly_bundle_value_inr_n", "mean"),
    acq_sum=("acquisition_cost_inr_n", "sum"),
    acq_avg=("acquisition_cost_inr_n", "mean"),
).round(0)
src_econ["cac_per_activated_inr"] = (src_econ["acq_sum"] / src_econ["activated"]).round(0)
save_table(src_econ, "economics_by_lead_source")

# CAC per activated lead, with all spend attributed to the cohort that produced
# them (total spend / activated) — the stricter view:
summary["cac_strict"] = round(df["acquisition_cost_inr_n"].sum() / len(act), 0)

# ---------------------------------------------------------------- task 7: charts

# 1. funnel
fig, ax = plt.subplots(figsize=(8, 5))
labels = [f"{s}\n({cumulative[s]:,})" for s in STAGES]
ax.bar(labels, [cumulative[s] for s in STAGES], color=[NAVY, "#2d5e9e", "#4a7fb5",
                                                       "#6b9bc9", "#8fb8dc", GREEN])
for i, s in enumerate(STAGES):
    ax.annotate(f"{cumulative[s]:,}", (i, cumulative[s]), ha="center", va="bottom",
                fontsize=10, fontweight="bold")
    if i:
        rate = pct(cumulative[s], cumulative[STAGES[i - 1]])
        ax.annotate(f"{rate}% of prev",
                    (i, cumulative[s] + 260), ha="center", va="bottom",
                    fontsize=9, color=RED, fontweight="bold")
ax.set_title("UdyamOne target funnel: lead to activation (n=5,000, Apr-Jun 2026)")
ax.set_ylabel("Leads reaching stage")
ax.spines[["top", "right"]].set_visible(False)
save_chart(fig, "01_funnel")

# 2. stage drop-off
fig, ax = plt.subplots(figsize=(8, 4.5))
drops = [funnel.iloc[i]["drop_off_from_previous"] for i in range(1, len(funnel))]
stages_lbl = [f"{STAGES[i-1]} → {STAGES[i]}" for i in range(1, len(STAGES))]
bars = ax.bar(stages_lbl, drops, color=RED)
bar_labels(ax, bars, [pct(d, funnel.iloc[i - 1]["leads_reached"])
                      for i, d in enumerate(drops, start=1)])
ax.set_title("Absolute lead loss per stage transition")
ax.set_ylabel("Leads lost")
ax.spines[["top", "right"]].set_visible(False)
save_chart(fig, "02_stage_dropoff")

# 3. lead source conversion
src = pd.read_csv(OUT / "by_lead_source.csv", index_col=0)
fig, ax = plt.subplots(figsize=(8, 4.5))
bars = ax.barh(src.index[::-1], src["activation_rate_pct"][::-1], color=NAVY)
for bar, (leads, rate) in zip(bars, zip(src["leads"][::-1], src["activation_rate_pct"][::-1])):
    ax.annotate(f"{rate}% (n={leads:,})", (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                va="center", fontsize=9)
ax.set_title("Activation rate by lead source")
ax.set_xlabel("Activation rate (%)")
ax.set_xlim(0, max(src["activation_rate_pct"]) * 1.25)
ax.spines[["top", "right"]].set_visible(False)
save_chart(fig, "03_lead_source_conversion")

# 4. segment conversion
seg = pd.read_csv(OUT / "by_segment.csv", index_col=0)
fig, ax = plt.subplots(figsize=(8, 4.5))
bars = ax.barh(seg.index[::-1], seg["activation_rate_pct"][::-1], color="#2d5e9e")
for bar, (leads, rate) in zip(bars, zip(seg["leads"][::-1], seg["activation_rate_pct"][::-1])):
    ax.annotate(f"{rate}% (n={leads:,})", (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                va="center", fontsize=9)
ax.set_title("Activation rate by business segment")
ax.set_xlabel("Activation rate (%)")
ax.set_xlim(0, max(seg["activation_rate_pct"]) * 1.25)
ax.spines[["top", "right"]].set_visible(False)
save_chart(fig, "04_segment_conversion")

# 5. city performance
city_full = pd.read_csv(OUT / "by_city.csv", index_col=0)
city_big = city_full[city_full["leads"] >= 80].sort_values("activation_rate_pct", ascending=False)
fig, ax = plt.subplots(figsize=(10, 5))
bars = ax.bar(city_big.index, city_big["activation_rate_pct"], color=NAVY)
bar_labels(ax, bars, city_big["activation_rate_pct"])
ax.axhline(pct(len(act), len(df)), color=RED, linestyle="--", linewidth=1.2,
           label=f"Overall activation rate ({pct(len(act), len(df))}%)")
ax.set_title("Activation rate by city (cities with ≥80 leads)")
ax.set_ylabel("Activation rate (%)")
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
save_chart(fig, "05_city_performance")

# 6. drop reasons
top_reasons = reasons.head(10)[::-1]
fig, ax = plt.subplots(figsize=(9, 5.5))
bars = ax.barh(top_reasons.index, top_reasons.values, color=RED)
for bar, count in zip(bars, top_reasons.values):
    ax.annotate(f"{count:,} ({pct(count, len(dropped))}%)",
                (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                va="center", fontsize=9)
ax.set_title(f"Top drop reasons among {len(dropped):,} dropped leads")
ax.set_xlabel("Dropped leads")
ax.spines[["top", "right"]].set_visible(False)
save_chart(fig, "06_drop_reasons")

# 7. revenue & CAC by segment
fig, ax = plt.subplots(figsize=(9, 5))
x = range(len(seg_econ.index))
ax.bar([i - 0.2 for i in x], seg_econ["monthly_value_avg"], width=0.4,
       label="Avg monthly bundle value (₹)", color=NAVY)
ax.bar([i + 0.2 for i in x], seg_econ["cac_per_activated_inr"], width=0.4,
       label="CAC per activated lead (₹)", color=RED)
ax.set_xticks(list(x))
ax.set_xticklabels(seg_econ.index, fontsize=9)
ax.set_title("Economics by segment (activated leads only)")
ax.set_ylabel("INR")
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
save_chart(fig, "07_revenue_cac")

# NPS distribution
fig, ax = plt.subplots(figsize=(7, 4))
nps_counts = nps.value_counts().sort_index()
ax.bar(nps_counts.index.astype(str), nps_counts.values, color=GREEN)
ax.set_title(f"NPS distribution among activated customers (n={nps.notna().sum()}, "
             f"mean {nps.mean():.1f}, NPS {econ['nps_net']})")
ax.set_xlabel("NPS score")
ax.set_ylabel("Customers")
ax.spines[["top", "right"]].set_visible(False)
save_chart(fig, "08_nps_distribution")

# ---------------------------------------------------------------- report json

import json  # noqa: E402

with (OUT / "summary.json").open("w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, default=str)

print("=== FUNNEL (n=5,000) ===")
print(funnel.to_string())
print("\n=== UNIT ECONOMICS (activated cohort) ===")
for k, v in econ.items():
    print(f"{k}: {v}")
print("\n=== ACTIVATION BY SOURCE ===")
print(pd.read_csv(OUT / "by_lead_source.csv", index_col=0).to_string())
print("\n=== ACTIVATION BY SEGMENT ===")
print(pd.read_csv(OUT / "by_segment.csv", index_col=0).to_string())
print("\n=== TOP DROP REASONS ===")
print(drop_reasons.head(10).to_string())
print("\n=== FOLLOW-UP CALLS BY OUTCOME ===")
print(followups.to_string())
print(f"\nCharts + tables written to {OUT}")
