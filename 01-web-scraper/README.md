# Web Scraper – Book Catalogue

Scrapes all 1,000 books from [books.toscrape.com](https://books.toscrape.com) (a public sandbox site made for scraping practice) and exports them to CSV and Excel.

## Features
- Automatic pagination (follows "next" until the last page)
- Retries with exponential backoff, custom User-Agent, configurable delay between requests
- Typed, cleaned fields: title, price (float), star rating (1–5), stock status, product URL
- Console summary (count, avg price, price range, top cheapest 5-star books)

## Run
```bash
python scraper.py                 # all 50 pages, ~1 min
python scraper.py --max-pages 3   # quick test
python scraper.py --out output/my_books --delay 1.0
```

Output: `output/books.csv`, `output/books.xlsx`

## Adapting to a client's site
The same skeleton works for e-commerce listings, job boards, directories and real-estate portals:
change `BASE_URL`, the CSS selectors in `parse_listing()`, and the `Book` dataclass fields.
For JavaScript-heavy sites I switch to Playwright; for sites with an API I call the API directly (faster and more reliable).
