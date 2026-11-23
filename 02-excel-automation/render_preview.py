"""Render a PNG preview of the report's Summary sheet (for portfolio / gig images)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv("output/Sales_Report_2025.clean.csv", parse_dates=["Order Date"])
c = df[df.Status == "Completed"]
monthly = c.groupby("Month")["Revenue"].sum()
region = c.groupby("Region")["Revenue"].sum().sort_values()

fig = plt.figure(figsize=(14, 8), facecolor="white")
fig.text(0.04, 0.94, "Sales Performance Report", fontsize=22, fontweight="bold", color="#1F4E78")
fig.text(0.04, 0.905, f"Period: {df['Order Date'].min():%d %b %Y} - {df['Order Date'].max():%d %b %Y}   |   Generated automatically from raw_sales_export.csv",
         fontsize=10, style="italic", color="#7F7F7F")

kpis = [("Total Revenue", f"${c.Revenue.sum():,.0f}"), ("Orders", f"{len(c):,}"), ("Units Sold", f"{int(c.Qty.sum()):,}"),
        ("Avg Order Value", f"${c.Revenue.mean():,.0f}"), ("Refund Rate", f"{(df.Status=='Refunded').mean():.1%}")]
for i, (k, v) in enumerate(kpis):
    ax = fig.add_axes([0.04 + i * 0.19, 0.74, 0.17, 0.12]); ax.set_facecolor("#DDEBF7"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color("#BFBFBF")
    ax.text(0.5, 0.68, k, ha="center", va="center", fontsize=10, color="#1F4E78", fontweight="bold")
    ax.text(0.5, 0.30, v, ha="center", va="center", fontsize=17, fontweight="bold")

ax1 = fig.add_axes([0.06, 0.10, 0.55, 0.56])
ax1.plot(monthly.index, monthly.values, marker="o", color="#4472C4", lw=2)
ax1.fill_between(range(len(monthly)), monthly.values, alpha=0.08, color="#4472C4")
ax1.set_title("Monthly Revenue", fontsize=12, fontweight="bold", loc="left")
ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"${x/1000:.0f}K"))
ax1.tick_params(axis="x", rotation=45, labelsize=8); ax1.grid(axis="y", alpha=0.3)
for s in ("top", "right"): ax1.spines[s].set_visible(False)

ax2 = fig.add_axes([0.68, 0.10, 0.29, 0.56])
ax2.barh(region.index, region.values, color=["#A5A5A5", "#ED7D31", "#70AD47", "#4472C4"])
ax2.set_title("Revenue by Region", fontsize=12, fontweight="bold", loc="left")
ax2.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"${x/1000:.0f}K"))
for s in ("top", "right"): ax2.spines[s].set_visible(False)
for i, v in enumerate(region.values): ax2.text(v, i, f"  ${v:,.0f}", va="center", fontsize=9)

fig.text(0.04, 0.03, "Workbook sheets: Summary | By Product | By Rep | Monthly | Clean Data (1,200 rows) | Data Issues (687 fixes logged)",
         fontsize=9, color="#7F7F7F")
fig.savefig("output/report_preview.png", dpi=130)
print("saved output/report_preview.png")
