#!/usr/bin/env python3
"""Generate portfolio dashboard from properties.yaml master data.

Usage:
  python generate_portfolio.py              # generate output/portfolio_dashboard.html
  python generate_portfolio.py --open       # generate and open in browser
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "properties.yaml"
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"


def load_data() -> dict:
    with open(DATA_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def enrich(data: dict) -> dict:
    """Calculate derived values for each property."""
    meta = data.get("meta", {})
    tax_personal = meta.get("tax_rate_personal", 0.43)
    tax_corporate = meta.get("tax_rate_corporate", 0.34)
    now_year = datetime.now().year

    totals = {
        "count": 0, "personal": 0, "corporate": 0,
        "wooden": 0, "rc": 0,
        "total_price": 0, "total_loan_remaining": 0,
        "monthly_rent_total": 0, "monthly_cf_total": 0,
        "annual_depreciation_total": 0, "annual_tax_savings_total": 0,
    }

    for p in data.get("properties", []):
        totals["count"] += 1
        if p.get("entity") == "個人":
            totals["personal"] += 1
        else:
            totals["corporate"] += 1
        if p.get("structure") == "木造":
            totals["wooden"] += 1
        elif p.get("structure") == "RC":
            totals["rc"] += 1

        # Loan totals
        total_loan_remaining = 0
        total_monthly_payment = 0
        for loan in p.get("loans", []):
            if loan.get("remaining"):
                total_loan_remaining += loan["remaining"]
            if loan.get("monthly_payment"):
                total_monthly_payment += loan["monthly_payment"]
        p["total_loan_remaining"] = total_loan_remaining
        p["total_monthly_payment"] = total_monthly_payment
        totals["total_loan_remaining"] += total_loan_remaining

        # Total price
        if p.get("total_price"):
            totals["total_price"] += p["total_price"]

        # Monthly rent
        rent = p.get("monthly_rent", 0) or 0
        totals["monthly_rent_total"] += rent

        # Monthly expenses
        expenses = p.get("annual_expenses")
        if expenses and expenses > 12000:  # annual
            monthly_exp = expenses / 12
        elif expenses:
            monthly_exp = expenses  # already monthly
        else:
            monthly_exp = 0
        p["monthly_expenses"] = monthly_exp

        # Monthly net CF
        net_cf = rent - monthly_exp - total_monthly_payment
        p["monthly_net_cf"] = net_cf
        totals["monthly_cf_total"] += net_cf

        # Depreciation
        bc = p.get("building_cost")
        dr = p.get("depreciation_rate")
        br = p.get("business_ratio", 1.0)
        if bc and dr:
            annual_dep = bc * dr * br
            tax_rate = tax_personal if p.get("entity") == "個人" else tax_corporate
            annual_savings = annual_dep * tax_rate
            p["annual_depreciation"] = annual_dep
            p["annual_tax_savings"] = annual_savings
            totals["annual_depreciation_total"] += annual_dep
            totals["annual_tax_savings_total"] += annual_savings
        else:
            p["annual_depreciation"] = None
            p["annual_tax_savings"] = None

        # Acquisition year & depreciation end
        acq = p.get("acquisition_date", "")
        if acq:
            acq_year = int(acq.split("-")[0])
            p["acquisition_year"] = acq_year
            p["holding_years"] = now_year - acq_year
            if p.get("useful_life"):
                end_year = acq_year + p["useful_life"]
                p["depreciation_end_year"] = end_year
                p["depreciation_remaining"] = end_year - now_year
            else:
                p["depreciation_end_year"] = None
                p["depreciation_remaining"] = None
            p["capital_gains_type"] = "長期(20%)" if p["holding_years"] >= 5 else "短期(39%)"
        else:
            p["acquisition_year"] = None
            p["holding_years"] = None
            p["depreciation_end_year"] = None
            p["depreciation_remaining"] = None
            p["capital_gains_type"] = "不明"

        # Display name
        p["display_name"] = p.get("name_ja") or p.get("name", "")

    data["totals"] = totals
    data["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return data


def generate(data: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
    )
    env.filters["comma"] = lambda v: f"{v:,.0f}" if v else "—"
    env.filters["yen"] = lambda v: f"¥{v:,.0f}" if v else "—"
    env.filters["pct"] = lambda v: f"{v:.1f}%" if v else "—"
    template = env.get_template("portfolio_dashboard.html")
    return template.render(**data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()

    data = load_data()
    data = enrich(data)
    html = generate(data)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / "portfolio_dashboard.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[OK] Generated {out_path} ({len(html):,} bytes)")

    if args.open:
        subprocess.run(["open", str(out_path)])


if __name__ == "__main__":
    main()
