"""Generate a realistically messy sales export (the kind clients actually send)."""
import random
from datetime import date, timedelta

import pandas as pd

random.seed(42)
REGIONS = ["North", "South", "East", "West"]
PRODUCTS = {"Laptop Pro 14": 1299, "Laptop Air 13": 899, "Wireless Mouse": 29, "USB-C Hub": 49,
            "4K Monitor": 399, "Mechanical Keyboard": 119, "Webcam HD": 79, "Laptop Stand": 39}
REPS = ["Alice Tan", "Ben Lee", "Chloe Wong", "Daniel Lim", "Emma Ng"]
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y", "%Y/%m/%d"]

rows = []
start = date(2025, 1, 1)
for i in range(1, 1201):
    d = start + timedelta(days=random.randint(0, 364))
    product = random.choice(list(PRODUCTS))
    qty = random.choice([1, 1, 1, 2, 2, 3, 5, 10])
    unit = PRODUCTS[product] * random.uniform(0.9, 1.1)
    # inject mess
    region = random.choice(REGIONS)
    if random.random() < 0.15:
        region = random.choice([region.lower(), region.upper(), f" {region} ", region + "  "])
    rep = random.choice(REPS)
    if random.random() < 0.1:
        rep = rep.upper() if random.random() < 0.5 else rep.lower()
    price_str = f"{unit:.2f}"
    if random.random() < 0.2:
        price_str = random.choice([f"${unit:,.2f}", f"USD {unit:.2f}", f"{unit:.2f} "])
    date_str = d.strftime(random.choice(DATE_FORMATS))
    status = random.choice(["Completed"] * 8 + ["Refunded", "Pending"])
    rows.append({
        "Order ID": f"ORD-{i:05d}", "Order Date": date_str, "Region": region, "Sales Rep": rep,
        "Product": product if random.random() > 0.05 else product.lower(),
        "Qty": qty if random.random() > 0.03 else "",   # some missing qty
        "Unit Price": price_str, "Status": status,
    })
# duplicates
rows += random.sample(rows, 25)
random.shuffle(rows)
pd.DataFrame(rows).to_csv("raw_sales_export.csv", index=False)
print(f"wrote raw_sales_export.csv with {len(rows)} rows (incl. 25 duplicates)")
