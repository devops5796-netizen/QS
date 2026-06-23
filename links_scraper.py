import random
import time
import pandas as pd
from scrapling import StealthyFetcher
BASE_URL = "https://qatarsale.com"

def extract_product_links(page) -> list:
    product_links = []
    
    items = page.css("qs-product-card-v2 a[href*='/product/']")
    
    for it in items:
        href = it.attrib.get("href", "")
        if href:
            if href.startswith("/"):
                href = BASE_URL + href
            product_links.append(href)
    
    return list(set(product_links))

def run(listing_url: str, start_page: int, end_page: int, output_csv: str):
    print("\n" + "="*50)
    print("STEP 1: Scraping listing pages for links...")
    print("="*50)

    all_links = set()
    failed_pages = {}
    success_count = 0

    for page_num in range(start_page, end_page + 1):
        url = f"{listing_url}&page={page_num}"
        print(f"Page {page_num}/{end_page}: {url}")

        for attempt in range(3):
            try:
                page = StealthyFetcher.fetch(
                    url,
                    headless=True,
                    network_idle=True,
                    timeout=60000,
                    wait_for_idle_network_timeout=10000
                )

                links = extract_product_links(page)
                
                if links:
                    for l in links:
                        all_links.add(l)
                    success_count += 1
                    print(f"  ✓ Found {len(links)} links")
                    break
                else:
                    failed_pages[f"Page {page_num}"] = "No links found"
                    print(f"  ⚠ No links found")
                    break
      
            except Exception as e:
                if attempt < 2:
                    print(f"  Attempt {attempt+1} failed, retrying...")
                    time.sleep(3)
                else:
                    failed_pages[f"Page {page_num}"] = str(e)
                    print(f"  Error: {e}")

        if page_num < end_page:
            time.sleep(random.uniform(2.0, 5.0))

    pd.DataFrame(list(all_links), columns=["product_url"]).to_csv(output_csv, index=False, encoding="utf-8")

    return {
        "success": success_count,
        "failed": len(failed_pages),
        "total_links": len(all_links)
    }

if __name__ == "__main__":
    result = run(
        listing_url="https://qatarsale.com/ar/products/wrist_watches-watches?basic_search:StatusFilter=0",
        start_page=1,
        end_page=5,
        output_csv="product_links.csv",
    )