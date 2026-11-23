"""
Sales data cleaner + Excel report generator.

Takes a messy CSV/Excel export and produces a polished multi-sheet workbook:
  1. Summary      - KPI cards + monthly trend chart + region bar chart
  2. By Product   - revenue / qty / avg price per product, ranked
  3. By Rep       - sales rep leaderboard with conditional colour scale
  4. Monthly      - month x region pivot
  5. Clean Data   - the full cleaned dataset as a filterable table
  6. Data Issues  - every row that was fixed or dropped, with the reason

Usage
    python sales_report.py raw_sales_export.csv --out output/Sales_Report_2025.xlsx
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")
KPI_FILL = PatternFill("solid", fgColor="DDEBF7")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
MONEY = '"$"#,##0.00'


# ---------------------------------------------------------------- cleaning
def parse_price(val) -> float | None:
    if pd.isna(val):
        return None
    s = re.sub(r"[^\d.\-]", "", str(val))
    return float(s) if s else None


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (clean_df, issues_df)."""
    issues = []
    df = df.copy()
    original_len = len(df)

    # duplicates
    dup_mask = df.duplicated(subset=["Order ID"], keep="first")
    for oid in df.loc[dup_mask, "Order ID"]:
        issues.append((oid, "Duplicate order removed"))
    df = df[~dup_mask]

    # text normalisation
    for col in ["Region", "Sales Rep", "Product"]:
        before = df[col].copy()
        df[col] = df[col].astype(str).str.strip().str.title()
        changed = before != df[col]
        for oid in df.loc[changed, "Order ID"]:
            issues.append((oid, f"Normalised text in '{col}'"))

    # dates (mixed formats)
    parsed = pd.to_datetime(df["Order Date"], format="mixed", dayfirst=False, errors="coerce")
    bad = parsed.isna()
    for oid in df.loc[bad, "Order ID"]:
        issues.append((oid, "Unparseable date - row dropped"))
    df = df[~bad].copy()
    df["Order Date"] = parsed[~bad].dt.normalize()

    # price
    df["Unit Price"] = df["Unit Price"].map(parse_price)

    # qty
    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce")
    missing_qty = df["Qty"].isna()
    for oid in df.loc[missing_qty, "Order ID"]:
        issues.append((oid, "Missing qty - defaulted to 1"))
    df["Qty"] = df["Qty"].fillna(1).astype(int)

    df["Revenue"] = (df["Qty"] * df["Unit Price"]).round(2)
    df["Month"] = df["Order Date"].dt.to_period("M").astype(str)
    df = df.sort_values("Order Date").reset_index(drop=True)

    issues_df = pd.DataFrame(issues, columns=["Order ID", "Issue"])
    print(f"Cleaned {original_len} -> {len(df)} rows, {len(issues_df)} issues logged")
    return df, issues_df


# ---------------------------------------------------------------- report
def style_header(ws, row=1):
    for cell in ws[row]:
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def autosize(ws, min_w=10, max_w=45):
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=0)
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(min_w, min(max_w, width + 2))


def money_cols(ws, cols, start_row=2):
    for c in cols:
        for row in ws.iter_rows(min_row=start_row, min_col=c, max_col=c):
            row[0].number_format = MONEY


def build_report(df: pd.DataFrame, issues: pd.DataFrame, out: Path):
    completed = df[df["Status"] == "Completed"]

    by_product = (completed.groupby("Product")
                  .agg(Orders=("Order ID", "count"), Units=("Qty", "sum"), Revenue=("Revenue", "sum"),
                       Avg_Price=("Unit Price", "mean"))
                  .sort_values("Revenue", ascending=False).round(2).reset_index())
    by_rep = (completed.groupby("Sales Rep")
              .agg(Orders=("Order ID", "count"), Revenue=("Revenue", "sum"))
              .sort_values("Revenue", ascending=False).round(2).reset_index())
    by_rep["Avg Order Value"] = (by_rep["Revenue"] / by_rep["Orders"]).round(2)
    by_rep["Share %"] = (by_rep["Revenue"] / by_rep["Revenue"].sum() * 100).round(1)
    monthly = completed.pivot_table(index="Month", columns="Region", values="Revenue",
                                    aggfunc="sum", fill_value=0).round(2)
    monthly["Total"] = monthly.sum(axis=1)
    monthly = monthly.reset_index()
    by_region = completed.groupby("Region")["Revenue"].sum().round(2).reset_index()

    out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        pd.DataFrame().to_excel(xw, sheet_name="Summary")  # placeholder, filled below
        by_product.to_excel(xw, sheet_name="By Product", index=False)
        by_rep.to_excel(xw, sheet_name="By Rep", index=False)
        monthly.to_excel(xw, sheet_name="Monthly", index=False)
        df.to_excel(xw, sheet_name="Clean Data", index=False)
        issues.to_excel(xw, sheet_name="Data Issues", index=False)

    wb = load_workbook(out)

    # --- Summary sheet
    ws = wb["Summary"]
    ws.sheet_view.showGridLines = False
    ws["B2"] = "Sales Performance Report"
    ws["B2"].font = Font(bold=True, size=18, color="1F4E78")
    ws["B3"] = (f"Period: {df['Order Date'].min():%d %b %Y} - {df['Order Date'].max():%d %b %Y}"
                "   |   Generated automatically")
    ws["B3"].font = Font(italic=True, color="7F7F7F")

    kpis = [
        ("Total Revenue", completed["Revenue"].sum(), MONEY),
        ("Orders", len(completed), "#,##0"),
        ("Units Sold", completed["Qty"].sum(), "#,##0"),
        ("Avg Order Value", completed["Revenue"].mean(), MONEY),
        ("Refund Rate", (df["Status"] == "Refunded").mean(), "0.0%"),
    ]
    for i, (label, value, fmt) in enumerate(kpis):
        col = 2 + i * 2
        lc = ws.cell(row=5, column=col, value=label)
        vc = ws.cell(row=6, column=col, value=value)
        lc.font = Font(bold=True, color="1F4E78")
        lc.fill = KPI_FILL
        vc.font = Font(bold=True, size=14)
        vc.fill = KPI_FILL
        vc.number_format = fmt
        for c in (lc, vc):
            c.alignment = Alignment(horizontal="center")
            c.border = BORDER
        ws.column_dimensions[get_column_letter(col)].width = 18
        ws.column_dimensions[get_column_letter(col + 1)].width = 3

    # chart data blocks (placed off to the right, then charted)
    ws["N5"], ws["O5"] = "Month", "Revenue"
    mt = completed.groupby("Month")["Revenue"].sum().round(2)
    for r, (m, v) in enumerate(mt.items(), start=6):
        ws.cell(row=r, column=14, value=m)
        ws.cell(row=r, column=15, value=v)
    ws["Q5"], ws["R5"] = "Region", "Revenue"
    for r, (_, row) in enumerate(by_region.iterrows(), start=6):
        ws.cell(row=r, column=17, value=row["Region"])
        ws.cell(row=r, column=18, value=row["Revenue"])

    line = LineChart()
    line.title = "Monthly Revenue"
    line.height, line.width = 8, 16
    line.add_data(Reference(ws, min_col=15, min_row=5, max_row=5 + len(mt)), titles_from_data=True)
    line.set_categories(Reference(ws, min_col=14, min_row=6, max_row=5 + len(mt)))
    line.y_axis.number_format = '"$"#,##0'
    line.legend = None
    ws.add_chart(line, "B9")

    bar = BarChart()
    bar.title = "Revenue by Region"
    bar.height, bar.width = 8, 10
    bar.add_data(Reference(ws, min_col=18, min_row=5, max_row=5 + len(by_region)), titles_from_data=True)
    bar.set_categories(Reference(ws, min_col=17, min_row=6, max_row=5 + len(by_region)))
    bar.y_axis.number_format = '"$"#,##0'
    bar.legend = None
    ws.add_chart(bar, "B26")

    # --- other sheets: header style, formats, tables
    for name in ["By Product", "By Rep", "Monthly", "Clean Data", "Data Issues"]:
        s = wb[name]
        style_header(s)
        autosize(s)
        s.freeze_panes = "A2"
    money_cols(wb["By Product"], [4, 5])
    money_cols(wb["By Rep"], [3, 4])
    money_cols(wb["Monthly"], range(2, monthly.shape[1] + 1))
    money_cols(wb["Clean Data"], [7, 9])
    for row in wb["Clean Data"].iter_rows(min_row=2, min_col=2, max_col=2):
        row[0].number_format = "yyyy-mm-dd"

    rep_ws = wb["By Rep"]
    rep_ws.conditional_formatting.add(
        f"C2:C{len(by_rep) + 1}",
        ColorScaleRule(start_type="min", start_color="F8696B", mid_type="percentile", mid_value=50,
                       mid_color="FFEB84", end_type="max", end_color="63BE7B"))
    cd = wb["Clean Data"]
    tab = Table(displayName="CleanSales", ref=f"A1:{get_column_letter(cd.max_column)}{cd.max_row}")
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    cd.add_table(tab)

    wb.save(out)
    print(f"Report saved -> {out}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="messy CSV or XLSX export")
    ap.add_argument("--out", default="output/Sales_Report.xlsx")
    args = ap.parse_args(argv)
    src = Path(args.input)
    raw = pd.read_excel(src) if src.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(src)
    df, issues = clean(raw)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(Path(args.out).with_suffix(".clean.csv"), index=False)
    build_report(df, issues, Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
