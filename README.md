# QS
## Project Structure
```

QS/
├── main.py               # Pipeline entry point
├── links_scraper.py      # Step 1: Collect product URLs from listing pages
├── products_scraper.py   # Step 2: Scrape product details
├── flatten.py            # Step 3: Flatten specifications JSON into columns
├── image_downloader.py   # Step 4: Download product images
├── analyze_data.py       # Data quality report
└── .github/
└── workflows/
└── scraper.yml   # GitHub Actions CI/CD workflow
```
---

## Pipeline Overview

```
Listing Pages  →  Product URLs  →  Product Details  →  Flatten Specs  →  Download Images
  (requests)        (CSV)           (Playwright)           (CSV)             (local)
```


| Step | Script | Method | Output |
|------|--------|--------|--------|
| 1 | `links_scraper.py` | `requests` | `all_car_links.csv` |
| 2 | `products_scraper.py` | `playwright` (3 workers) | `all_products.csv` |
| 3 | `flatten.py` | `pandas` | `all_products_flat.csv` |
| 4 | `image_downloader.py` | `requests` (5 workers) | `all_products_final.csv` + `images/` |
| 5 | `r2_uploader.py` | `boto3` | Cloudflare R2 (images + final CSV) |


## GitHub Actions (CI/CD)

The workflow runs automatically every **Monday at 12:00 AM UTC** or manually from GitHub UI.

### What happens after each run
- Scraper output is saved to `scrape_report.txt` and committed to the repo

### Workflow steps
| Step | Action |
|------|--------|
| 1 | Checkout repo |
| 2 | Set up Python 3.11 |
| 3 | Install dependencies + Playwright Chromium |
| 4 | Run `main.py` and save output to `scrape_report.txt` |
| 5 | Commit and push `scrape_report.txt` to repo |