"""
Book catalogue scraper - demo of a production-style scraping job.

Target: https://books.toscrape.com (a public sandbox site built for scraping practice)

Features
- Follows pagination automatically until the last page
- Polite crawling: configurable delay, retries with backoff, custom User-Agent
- Cleans data types (price -> float, rating -> int, stock -> int)
- Exports to CSV and Excel in one run
- Prints a short summary so the client sees results immediately

Usage
    python scraper.py                      # scrape everything
    python scraper.py --max-pages 3        # quick test run
    python scraper.py --out output/books   # custom output name (no extension)
"""
from __future__ import annotations

import argparse
import logging
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import time
from dataclasses import dataclass, asdict
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/catalogue/"
START_PAGE = "page-1.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; portfolio-scraper/1.0)"}
RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scraper")


@dataclass
class Book:
    title: str
    price_gbp: float
    rating: int
    in_stock: bool
    url: str


def fetch(session: requests.Session, url: str, retries: int = 3, backoff: float = 1.5) -> str:
    """GET a page with retries and exponential backoff."""
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            wait = backoff ** attempt
            log.warning("Request failed (%s). Retry %d/%d in %.1fs", exc, attempt, retries, wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def parse_listing(html: str, page_url: str) -> tuple[list[Book], str | None]:
    """Parse one listing page. Returns (books, next_page_url or None)."""
    soup = BeautifulSoup(html, "lxml")
    books: list[Book] = []
    for card in soup.select("article.product_pod"):
        a = card.select_one("h3 a")
        title = a["title"].strip()
        href = urljoin(page_url, a["href"])
        price_text = card.select_one(".price_color").get_text(strip=True)
        price = float(price_text.replace("£", "").replace("Â", ""))
        rating_cls = card.select_one("p.star-rating")["class"]
        rating = next((RATING_WORDS[c] for c in rating_cls if c in RATING_WORDS), 0)
        stock_text = card.select_one(".availability").get_text(strip=True).lower()
        books.append(Book(title, price, rating, "in stock" in stock_text, href))

    next_link = soup.select_one("li.next a")
    next_url = urljoin(page_url, next_link["href"]) if next_link else None
    return books, next_url


def scrape(max_pages: int | None, delay: float) -> pd.DataFrame:
    session = requests.Session()
    url: str | None = urljoin(BASE_URL, START_PAGE)
    all_books: list[Book] = []
    page = 0
    while url and (max_pages is None or page < max_pages):
        page += 1
        log.info("Page %d: %s", page, url)
        books, url = parse_listing(fetch(session, url), url)
        all_books.extend(books)
        if url:
            time.sleep(delay)
    df = pd.DataFrame([asdict(b) for b in all_books])
    df.insert(0, "id", range(1, len(df) + 1))
    return df


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-pages", type=int, default=None, help="stop after N pages (default: all)")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    ap.add_argument("--out", default="output/books", help="output path without extension")
    args = ap.parse_args(argv)

    df = scrape(args.max_pages, args.delay)
    if df.empty:
        log.error("No data scraped")
        return 1

    df.to_csv(f"{args.out}.csv", index=False, encoding="utf-8-sig")
    df.to_excel(f"{args.out}.xlsx", index=False)
    log.info("Saved %d rows -> %s.csv / %s.xlsx", len(df), args.out, args.out)

    print("\n=== Summary ===")
    print(f"Books scraped : {len(df)}")
    print(f"Avg price     : GBP {df.price_gbp.mean():.2f}")
    print(f"Price range   : GBP {df.price_gbp.min():.2f} - {df.price_gbp.max():.2f}")
    print(f"Avg rating    : {df.rating.mean():.2f} / 5")
    print("\nTop 5 cheapest 5-star books:")
    top = df[df.rating == 5].nsmallest(5, "price_gbp")[["title", "price_gbp"]]
    print(top.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
