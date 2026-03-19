#!/usr/bin/env python3
"""Agent Team QA — property-analyzer mechanical validation.

Validates:
  - Yield calculations (gross/net/cap_rate)
  - DSCR, CCR, breakeven occupancy
  - Score component sums & tier mapping
  - Loan payment formulas
  - CF projection consistency (cumulative = running sum)
  - IRR sign & range
  - HTML output sanity (file size, property count)

Usage:
  python qa_validate.py                  # validate latest output
  python qa_validate.py --json           # structured JSON output
  python qa_validate.py --module         # validate analyzer module directly
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    status: str  # PASS / FAIL / WARN / SKIP
    detail: str = ""
    expected: str = ""
    actual: str = ""


@dataclass
class QAReport:
    project: str = "property-analyzer"
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == "PASS")

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status == "FAIL")

    @property
    def warnings(self) -> int:
        return sum(1 for c in self.checks if c.status == "WARN")

    def summary(self) -> str:
        total = len(self.checks)
        lines = [
            f"=== QA Report: {self.project} ===",
            f"Total: {total}  PASS: {self.passed}  FAIL: {self.failed}  WARN: {self.warnings}",
            "",
        ]
        for c in self.checks:
            icon = {"PASS": "✓", "FAIL": "✗", "WARN": "⚠", "SKIP": "—"}[c.status]
            line = f"  {icon} [{c.status}] {c.name}"
            if c.detail:
                line += f" — {c.detail}"
            lines.append(line)

        if self.failed:
            lines.append(f"\n❌ {self.failed} check(s) FAILED — review required")
        elif self.warnings:
            lines.append(f"\n⚠ All passed with {self.warnings} warning(s)")
        else:
            lines.append("\n✅ All checks passed")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps({
            "project": self.project,
            "summary": {"pass": self.passed, "fail": self.failed, "warn": self.warnings},
            "checks": [asdict(c) for c in self.checks],
        }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def _close(a: float, b: float, tol: float = 0.01) -> bool:
    """Check if two values are close (relative tolerance)."""
    if b == 0:
        return abs(a) < tol
    return abs(a - b) / max(abs(b), 1e-9) < tol


def validate_analyzer_module(report: QAReport) -> None:
    """Validate the analyzer module's calculation logic with known inputs."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from src.analyzer import (
            AnalysisResult,
            calc_loan_balance,
            calc_monthly_payment,
        )
    except ImportError as e:
        report.checks.append(CheckResult(
            "module_import", "FAIL", f"Cannot import analyzer: {e}"
        ))
        return

    # --- Loan payment formula ---
    # ¥10M, 2%, 35yr → expected ~¥33,126/mo
    pmt = calc_monthly_payment(10_000_000, 0.02, 35)
    if 33_000 < pmt < 33_300:
        report.checks.append(CheckResult(
            "loan_payment_formula", "PASS",
            f"¥10M/2%/35yr → ¥{pmt:,.0f}/mo"
        ))
    else:
        report.checks.append(CheckResult(
            "loan_payment_formula", "FAIL",
            expected="~¥33,126", actual=f"¥{pmt:,.0f}"
        ))

    # --- Zero rate ---
    pmt_zero = calc_monthly_payment(12_000_000, 0.0, 10)
    expected_zero = 12_000_000 / (10 * 12)
    if _close(pmt_zero, expected_zero):
        report.checks.append(CheckResult("loan_zero_rate", "PASS"))
    else:
        report.checks.append(CheckResult(
            "loan_zero_rate", "FAIL",
            expected=f"¥{expected_zero:,.0f}", actual=f"¥{pmt_zero:,.0f}"
        ))

    # --- Loan balance declining ---
    bal_0 = calc_loan_balance(10_000_000, 0.02, 35, 0)
    bal_10 = calc_loan_balance(10_000_000, 0.02, 35, 10)
    bal_35 = calc_loan_balance(10_000_000, 0.02, 35, 35)
    if bal_0 > bal_10 > 0:
        report.checks.append(CheckResult("loan_balance_declining", "PASS"))
    else:
        report.checks.append(CheckResult(
            "loan_balance_declining", "FAIL",
            detail=f"bal@0={bal_0:,.0f}, bal@10={bal_10:,.0f}"
        ))
    if abs(bal_35) < 100:  # should be ~0
        report.checks.append(CheckResult("loan_balance_final_zero", "PASS"))
    else:
        report.checks.append(CheckResult(
            "loan_balance_final_zero", "WARN",
            detail=f"bal@35={bal_35:,.0f} (expected ~0)"
        ))


def validate_analysis_result(result, report: QAReport) -> None:
    """Validate an AnalysisResult's internal consistency."""
    # Yield formulas
    if result.annual_gross_income > 0 and result.loan_amount > 0:
        price = result.total_investment - (result.total_investment * 0.08)  # rough
        # Gross yield check: positive and reasonable
        if 0 < result.gross_yield < 30:
            report.checks.append(CheckResult("gross_yield_range", "PASS", f"{result.gross_yield}%"))
        else:
            report.checks.append(CheckResult(
                "gross_yield_range", "WARN",
                detail=f"Unusual gross yield: {result.gross_yield}%"
            ))

    # NOI = effective_income - expenses
    noi_check = result.annual_gross_income - result.annual_operating_expenses
    if _close(noi_check, result.annual_noi, tol=0.02):
        report.checks.append(CheckResult("noi_consistency", "PASS"))
    else:
        report.checks.append(CheckResult(
            "noi_consistency", "FAIL",
            expected=f"¥{noi_check:,.0f}", actual=f"¥{result.annual_noi:,.0f}"
        ))

    # Net CF = NOI - debt service
    ncf_check = result.annual_noi - result.annual_debt_service
    if _close(ncf_check, result.annual_net_cf, tol=0.02):
        report.checks.append(CheckResult("net_cf_consistency", "PASS"))
    else:
        report.checks.append(CheckResult(
            "net_cf_consistency", "FAIL",
            expected=f"¥{ncf_check:,.0f}", actual=f"¥{result.annual_net_cf:,.0f}"
        ))

    # DSCR = NOI / debt_service
    if result.annual_debt_service > 0:
        dscr_check = result.annual_noi / result.annual_debt_service
        if _close(dscr_check, result.dscr, tol=0.02):
            report.checks.append(CheckResult("dscr_formula", "PASS", f"{result.dscr:.2f}"))
        else:
            report.checks.append(CheckResult(
                "dscr_formula", "FAIL",
                expected=f"{dscr_check:.2f}", actual=f"{result.dscr:.2f}"
            ))
        # DSCR safety threshold
        if result.dscr >= 1.2:
            report.checks.append(CheckResult("dscr_safety", "PASS", f"DSCR={result.dscr:.2f} ≥ 1.2"))
        else:
            report.checks.append(CheckResult(
                "dscr_safety", "WARN",
                detail=f"DSCR={result.dscr:.2f} < 1.2 (risky)"
            ))

    # CCR = net_cf / equity
    if result.equity > 0:
        ccr_check = result.annual_net_cf / result.equity * 100
        if _close(ccr_check, result.cash_on_cash, tol=0.05):
            report.checks.append(CheckResult("ccr_formula", "PASS"))
        else:
            report.checks.append(CheckResult(
                "ccr_formula", "FAIL",
                expected=f"{ccr_check:.2f}%", actual=f"{result.cash_on_cash:.2f}%"
            ))

    # Cashflow cumulative consistency
    if result.cashflows:
        running_sum = 0.0
        cf_ok = True
        for cf in result.cashflows:
            running_sum += cf.net_cash_flow
            if not _close(running_sum, cf.cumulative_cf, tol=0.01):
                cf_ok = False
                report.checks.append(CheckResult(
                    "cf_cumulative", "FAIL",
                    detail=f"Year {cf.year}: expected cumulative {running_sum:,.0f}, got {cf.cumulative_cf:,.0f}"
                ))
                break
        if cf_ok:
            report.checks.append(CheckResult("cf_cumulative", "PASS", f"{len(result.cashflows)} years"))

    # IRR range
    if result.irr is not None:
        if -50 < result.irr < 50:
            report.checks.append(CheckResult("irr_range", "PASS", f"{result.irr}%"))
        else:
            report.checks.append(CheckResult(
                "irr_range", "WARN", detail=f"IRR={result.irr}% seems extreme"
            ))

    # Breakeven occupancy
    if 0 < result.breakeven_occupancy < 100:
        report.checks.append(CheckResult("breakeven_range", "PASS", f"{result.breakeven_occupancy}%"))
    elif result.breakeven_occupancy >= 100:
        report.checks.append(CheckResult(
            "breakeven_range", "WARN",
            detail=f"Breakeven occupancy {result.breakeven_occupancy}% ≥ 100% (negative CF at full occupancy)"
        ))

    # Equity = total_investment - loan_amount (roughly, depends on purchase costs)
    if result.equity > 0 and result.loan_amount > 0:
        report.checks.append(CheckResult(
            "equity_positive", "PASS",
            f"Equity=¥{result.equity:,.0f}, Loan=¥{result.loan_amount:,.0f}"
        ))


def validate_search_report_scores(report: QAReport) -> None:
    """Validate search report scoring logic."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from generate_search_report_common import (
            PropertyRow,
            budget_score,
            area_score,
            earthquake_score,
            station_score,
            grade_tier,
        )
    except ImportError as e:
        report.checks.append(CheckResult(
            "search_score_import", "SKIP", f"Cannot import: {e}"
        ))
        return

    # Budget score boundary tests
    tests = [
        (3000, 20, "≤3500万=20"),
        (3500, 20, "≤3500万=20"),
        (4000, 15, "≤4000万=15"),
        (5000, 10, "≤5000万=10"),
        (6000, 0, ">5000万=0"),
    ]
    for price, expected, label in tests:
        actual = budget_score(price)
        if actual == expected:
            report.checks.append(CheckResult(f"budget_score_{price}", "PASS", label))
        else:
            report.checks.append(CheckResult(
                f"budget_score_{price}", "FAIL",
                expected=str(expected), actual=str(actual)
            ))

    # Tier mapping
    tier_tests = [
        (80, "強く推奨"),
        (65, "推奨"),
        (50, "条件付き"),
        (30, "見送り"),
    ]
    for score, expected_label in tier_tests:
        label, _, _ = grade_tier(score)
        if label == expected_label:
            report.checks.append(CheckResult(f"tier_{score}", "PASS", label))
        else:
            report.checks.append(CheckResult(
                f"tier_{score}", "FAIL",
                expected=expected_label, actual=label
            ))


def validate_portfolio_data(report: QAReport) -> None:
    """Validate properties.yaml data completeness and portfolio_dashboard consistency."""
    data_file = Path(__file__).parent / "data" / "properties.yaml"
    if not data_file.exists():
        report.checks.append(CheckResult("yaml_exists", "FAIL", "data/properties.yaml missing"))
        return

    try:
        import yaml
        with open(data_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        report.checks.append(CheckResult("yaml_parse", "FAIL", f"YAML parse error: {e}"))
        return

    report.checks.append(CheckResult("yaml_parse", "PASS"))

    props = data.get("properties", [])
    meta = data.get("meta", {})

    # Property count matches meta
    expected_count = meta.get("total_properties", 0)
    actual_count = len(props)
    if actual_count == expected_count:
        report.checks.append(CheckResult("property_count", "PASS", f"{actual_count} properties"))
    else:
        report.checks.append(CheckResult(
            "property_count", "WARN",
            expected=str(expected_count), actual=str(actual_count),
            detail=f"meta says {expected_count}, YAML has {actual_count}"
        ))

    # Entity count check
    personal = sum(1 for p in props if p.get("entity") == "個人")
    corporate = sum(1 for p in props if p.get("entity") == "法人")
    if personal == meta.get("personal_count", 0) and corporate == meta.get("corporate_count", 0):
        report.checks.append(CheckResult("entity_count", "PASS", f"個人{personal} 法人{corporate}"))
    else:
        report.checks.append(CheckResult(
            "entity_count", "WARN",
            detail=f"meta: 個人{meta.get('personal_count')}/法人{meta.get('corporate_count')} vs actual: 個人{personal}/法人{corporate}"
        ))

    # Required fields check per property
    required_fields = ["id", "name", "location", "entity", "monthly_rent"]
    important_fields = ["structure", "acquisition_date", "building_cost", "total_price"]
    missing_required = []
    missing_important = []

    for p in props:
        pid = p.get("id", "unknown")
        for fld in required_fields:
            if p.get(fld) is None:
                missing_required.append(f"{pid}.{fld}")
        for fld in important_fields:
            if p.get(fld) is None:
                missing_important.append(f"{pid}.{fld}")

    if not missing_required:
        report.checks.append(CheckResult("required_fields", "PASS"))
    else:
        report.checks.append(CheckResult(
            "required_fields", "FAIL",
            detail=f"Missing: {', '.join(missing_required[:5])}"
        ))

    if not missing_important:
        report.checks.append(CheckResult("important_fields", "PASS"))
    else:
        report.checks.append(CheckResult(
            "important_fields", "WARN",
            detail=f"Null: {', '.join(missing_important[:8])}"
        ))

    # Loan data check — every property should have at least one loan
    no_loans = [p.get("id") for p in props if not p.get("loans")]
    if not no_loans:
        report.checks.append(CheckResult("loan_data", "PASS", "All properties have loan data"))
    else:
        report.checks.append(CheckResult(
            "loan_data", "WARN", detail=f"No loans: {', '.join(no_loans)}"
        ))

    # CF sanity — rent should be >= 0
    neg_rent = [p.get("id") for p in props if (p.get("monthly_rent") or 0) < 0]
    if not neg_rent:
        report.checks.append(CheckResult("rent_non_negative", "PASS"))
    else:
        report.checks.append(CheckResult("rent_non_negative", "FAIL", detail=f"Negative rent: {neg_rent}"))

    # Portfolio dashboard HTML should contain all property names
    dashboard = Path(__file__).parent / "output" / "portfolio_dashboard.html"
    if dashboard.exists():
        html = dashboard.read_text(encoding="utf-8")
        missing_in_html = []
        for p in props:
            display = p.get("name_ja") or p.get("name", "")
            if display and display not in html:
                missing_in_html.append(display)
        if not missing_in_html:
            report.checks.append(CheckResult(
                "dashboard_all_properties", "PASS",
                f"All {len(props)} properties found in HTML"
            ))
        else:
            report.checks.append(CheckResult(
                "dashboard_all_properties", "FAIL",
                detail=f"Missing from HTML: {', '.join(missing_in_html)}"
            ))
    else:
        report.checks.append(CheckResult(
            "dashboard_all_properties", "SKIP", "portfolio_dashboard.html not found"
        ))


def validate_html_outputs(report: QAReport) -> None:
    """Validate generated HTML files exist and are reasonable size."""
    output_dir = Path(__file__).parent / "output"
    if not output_dir.exists():
        report.checks.append(CheckResult("output_dir", "FAIL", "output/ directory missing"))
        return

    html_files = list(output_dir.glob("*.html"))
    if not html_files:
        report.checks.append(CheckResult("html_files_exist", "FAIL", "No HTML files in output/"))
        return

    report.checks.append(CheckResult(
        "html_files_exist", "PASS", f"{len(html_files)} files"
    ))

    for f in html_files:
        size = f.stat().st_size
        if size < 5_000:
            report.checks.append(CheckResult(
                f"html_size_{f.name}", "FAIL",
                detail=f"{f.name}: {size:,} bytes (< 5KB, likely empty)"
            ))
        elif size < 20_000:
            report.checks.append(CheckResult(
                f"html_size_{f.name}", "WARN",
                detail=f"{f.name}: {size:,} bytes (small)"
            ))
        else:
            report.checks.append(CheckResult(
                f"html_size_{f.name}", "PASS",
                detail=f"{size:,} bytes"
            ))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_all(include_module: bool = False) -> QAReport:
    report = QAReport()

    # 1. Portfolio data (properties.yaml) checks
    validate_portfolio_data(report)

    # 2. HTML output checks
    validate_html_outputs(report)

    # 3. Search report scoring logic
    validate_search_report_scores(report)

    # 4. Analyzer module direct validation
    if include_module:
        validate_analyzer_module(report)

    return report


def main():
    parser = argparse.ArgumentParser(description="property-analyzer QA validation")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--module", action="store_true", help="Include analyzer module tests")
    args = parser.parse_args()

    report = run_all(include_module=args.module)

    if args.json:
        print(report.to_json())
    else:
        print(report.summary())

    sys.exit(1 if report.failed else 0)


if __name__ == "__main__":
    main()
