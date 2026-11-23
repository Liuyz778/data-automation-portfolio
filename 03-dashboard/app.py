"""
Interactive Sales Dashboard (Streamlit + Plotly)

Run:
    streamlit run app.py

Loads data/sales_clean.csv (or any CSV the user uploads from the sidebar) and shows
KPIs, trend, product/region breakdowns and a rep leaderboard with live filters.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Sales Dashboard", page_icon="📊", layout="wide")
DATA_PATH = Path(__file__).parent / "data" / "sales_clean.csv"
PALETTE = px.colors.qualitative.Set2


@st.cache_data
def load(src) -> pd.DataFrame:
    df = pd.read_csv(src, parse_dates=["Order Date"])
    df["Month"] = df["Order Date"].dt.to_period("M").dt.to_timestamp()
    return df


# ------------------------------------------------------------------ sidebar
st.sidebar.title("Filters")
uploaded = st.sidebar.file_uploader("Upload a cleaned sales CSV", type="csv")
df = load(uploaded if uploaded else DATA_PATH)

min_d, max_d = df["Order Date"].min().date(), df["Order Date"].max().date()
date_range = st.sidebar.date_input("Date range", (min_d, max_d), min_value=min_d, max_value=max_d)
regions = st.sidebar.multiselect("Region", sorted(df["Region"].unique()), default=sorted(df["Region"].unique()))
products = st.sidebar.multiselect("Product", sorted(df["Product"].unique()), default=sorted(df["Product"].unique()))
statuses = st.sidebar.multiselect("Status", sorted(df["Status"].unique()), default=["Completed"])

if len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
else:
    start, end = pd.Timestamp(min_d), pd.Timestamp(max_d)

f = df[(df["Order Date"].between(start, end)) & df["Region"].isin(regions)
       & df["Product"].isin(products) & df["Status"].isin(statuses)]

# ------------------------------------------------------------------ header + KPIs
st.title("📊 Sales Performance Dashboard")
st.caption(f"{start:%d %b %Y} – {end:%d %b %Y} · {len(f):,} orders shown")

if f.empty:
    st.warning("No data for the current filters.")
    st.stop()

prev_len = (end - start).days + 1
prev = df[(df["Order Date"].between(start - pd.Timedelta(days=prev_len), start - pd.Timedelta(days=1)))
          & df["Region"].isin(regions) & df["Product"].isin(products) & df["Status"].isin(statuses)]


def delta(cur, before):
    if before == 0 or pd.isna(before):
        return None
    return f"{(cur - before) / before * 100:+.1f}% vs prev. period"


def money(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:,.2f}M"
    if abs(v) >= 10_000:
        return f"${v / 1_000:,.0f}K"
    return f"${v:,.0f}"


k1, k2, k3, k4 = st.columns(4)
k1.metric("Revenue", money(f["Revenue"].sum()), delta(f["Revenue"].sum(), prev["Revenue"].sum()))
k2.metric("Orders", f"{len(f):,}", delta(len(f), len(prev)))
k3.metric("Units sold", f"{int(f['Qty'].sum()):,}", delta(f["Qty"].sum(), prev["Qty"].sum()))
k4.metric("Avg order value", f"${f['Revenue'].mean():,.0f}", delta(f["Revenue"].mean(), prev["Revenue"].mean()))

st.divider()

# ------------------------------------------------------------------ charts row 1
c1, c2 = st.columns((3, 2))
with c1:
    st.subheader("Monthly revenue by region")
    m = f.groupby(["Month", "Region"], as_index=False)["Revenue"].sum()
    fig = px.area(m, x="Month", y="Revenue", color="Region", color_discrete_sequence=PALETTE)
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend_title=None, yaxis_tickprefix="$", height=360)
    st.plotly_chart(fig, use_container_width=True)
with c2:
    st.subheader("Revenue share by product")
    p = f.groupby("Product", as_index=False)["Revenue"].sum().sort_values("Revenue")
    fig = px.pie(p, names="Product", values="Revenue", hole=0.55, color_discrete_sequence=PALETTE)
    fig.update_traces(textposition="inside", textinfo="percent")
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=360, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ charts row 2
c3, c4 = st.columns(2)
with c3:
    st.subheader("Top products by revenue")
    fig = px.bar(p, x="Revenue", y="Product", orientation="h", text_auto=".2s",
                 color_discrete_sequence=[PALETTE[0]])
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), xaxis_tickprefix="$", yaxis_title=None, height=360)
    st.plotly_chart(fig, use_container_width=True)
with c4:
    st.subheader("Sales rep leaderboard")
    r = (f.groupby("Sales Rep").agg(Orders=("Order ID", "count"), Revenue=("Revenue", "sum"))
         .sort_values("Revenue", ascending=False))
    r["Avg order"] = r["Revenue"] / r["Orders"]
    r["Share"] = r["Revenue"] / r["Revenue"].sum()
    st.dataframe(
        r.style.format({"Revenue": "${:,.0f}", "Avg order": "${:,.0f}", "Share": "{:.1%}"})
         .bar(subset=["Revenue"], color="#8da0cb"),
        use_container_width=True, height=360,
    )

# ------------------------------------------------------------------ detail table
with st.expander("Order-level data", expanded=False):
    st.dataframe(f.sort_values("Order Date", ascending=False), use_container_width=True, hide_index=True)
    st.download_button("Download filtered CSV", f.to_csv(index=False).encode("utf-8-sig"),
                       "filtered_sales.csv", "text/csv")
