import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = Path("churn_output")
OUT.mkdir(exist_ok=True)
LINES = []


def say(text=""):
    print(text)
    LINES.append(str(text))


def find_csv():
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).expanduser()
    home = Path.home() / "Downloads"
    exact = home / "WA_Fn-UseC_-Telco-Customer-Churn.csv"
    if exact.exists():
        return exact
    matches = sorted(home.glob("*Telco*Churn*.csv")) + sorted(Path(".").glob("*Telco*Churn*.csv"))
    if matches:
        return matches[0]
    sys.exit("Could not find the Telco churn CSV. Pass its path: python3 telco_churn_project.py /path/to/file.csv")


path = find_csv()
df = pd.read_csv(path)
df.columns = df.columns.str.strip()
say(f"File: {path}")
say(f"Rows: {len(df)}   Columns: {df.shape[1]}")

say("\n--- DATA CLEANING ---")
say(f"Duplicate rows: {df.duplicated().sum()}")
say(f"Duplicate customer IDs: {df['customerID'].duplicated().sum()}")

df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
blank_total = df["TotalCharges"].isna().sum()
say(f"Rows with blank TotalCharges: {blank_total} (new customers with tenure 0), removed")
df = df.dropna(subset=["TotalCharges"]).copy()

df["Churn_flag"] = (df["Churn"].str.strip() == "Yes").astype(int)
df["SeniorCitizen"] = df["SeniorCitizen"].map({0: "No", 1: "Yes"})
df["tenure_group"] = pd.cut(
    df["tenure"], bins=[0, 12, 24, 48, 72],
    labels=["0-12 months", "13-24 months", "25-48 months", "49-72 months"],
    include_lowest=True,
)
df["monthly_charge_group"] = pd.cut(
    df["MonthlyCharges"], bins=[0, 35, 70, 90, 200],
    labels=["Under 35", "35-70", "70-90", "Over 90"],
)
say(f"Rows after cleaning: {len(df)}")

say("\n--- OVERALL CHURN ---")
overall = df["Churn_flag"].mean() * 100
churned = int(df["Churn_flag"].sum())
say(f"Customers: {len(df)}")
say(f"Churned: {churned}")
say(f"Churn rate: {overall:.1f}%")

BLUE, ORANGE = "#4C78A8", "#F58518"


def churn_by(col, title, fname, order=None, rotate=0):
    g = df.groupby(col, observed=True)["Churn_flag"].agg(["mean", "count"])
    g.columns = ["churn_rate", "customers"]
    g["churn_rate"] = (g["churn_rate"] * 100).round(1)
    if order:
        g = g.reindex(order)
    g.to_csv(OUT / f"{fname}.csv")

    say(f"\nChurn rate by {col}:")
    say(g.to_string())

    fig, ax = plt.subplots(figsize=(7, 4.2))
    colors = [ORANGE if v > overall else BLUE for v in g["churn_rate"]]
    bars = ax.bar(g.index.astype(str), g["churn_rate"], color=colors)
    ax.axhline(overall, color="gray", linestyle="--", linewidth=1)
    ax.text(len(g) - 0.5, overall + 0.8, f"Average {overall:.1f}%", ha="right", color="gray", fontsize=9)
    for b, v in zip(bars, g["churn_rate"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.8, f"{v}%", ha="center", fontsize=9)
    ax.set_title(title, fontsize=12, loc="left")
    ax.set_ylabel("Churn rate (%)")
    ax.set_ylim(0, max(g["churn_rate"].max() * 1.2, overall * 1.3))
    ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(rotation=rotate, ha="right" if rotate else "center")
    plt.tight_layout()
    fig.savefig(OUT / f"{fname}.png", dpi=150)
    plt.close(fig)
    return g


say("\n--- WHO CHURNS? ---")
churn_by("Contract", "Churn rate by contract type", "churn_by_contract")
churn_by("tenure_group", "Churn rate by time as a customer", "churn_by_tenure",
         order=["0-12 months", "13-24 months", "25-48 months", "49-72 months"])
churn_by("InternetService", "Churn rate by internet service", "churn_by_internet")
churn_by("PaymentMethod", "Churn rate by payment method", "churn_by_payment", rotate=20)
churn_by("monthly_charge_group", "Churn rate by monthly charges", "churn_by_monthly_charges",
         order=["Under 35", "35-70", "70-90", "Over 90"])
churn_by("TechSupport", "Churn rate by tech support", "churn_by_tech_support")
churn_by("SeniorCitizen", "Churn rate by senior citizen", "churn_by_senior")

say("\n--- CHURNED VS STAYED ---")
cmp = df.groupby("Churn")[["tenure", "MonthlyCharges", "TotalCharges"]].mean().round(1)
say(cmp.to_string())
cmp.to_csv(OUT / "churned_vs_stayed.csv")

say("\n--- HIGHEST-RISK SEGMENT ---")
seg = df[(df["Contract"] == "Month-to-month")
         & (df["InternetService"] == "Fiber optic")
         & (df["PaymentMethod"] == "Electronic check")]
if len(seg):
    seg_rate = seg["Churn_flag"].mean() * 100
    say("Month-to-month + Fiber optic + Electronic check:")
    say(f"  Customers: {len(seg)} ({len(seg) / len(df) * 100:.1f}% of all customers)")
    say(f"  Churn rate: {seg_rate:.1f}% (vs {overall:.1f}% overall)")

say("\n--- REVENUE AT RISK ---")
lost = df.loc[df["Churn_flag"] == 1, "MonthlyCharges"].sum()
total = df["MonthlyCharges"].sum()
say(f"Monthly revenue from churned customers: {lost:,.0f}")
say(f"Share of total monthly revenue: {lost / total * 100:.1f}%")

(OUT / "results.txt").write_text("\n".join(LINES), encoding="utf-8")
say(f"\nDone. Charts, tables and results.txt are in the folder: {OUT.resolve()}")
