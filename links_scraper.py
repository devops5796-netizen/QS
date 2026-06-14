import random
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def extract_product_links(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    product_links = []
    cards = soup.find_all("qs-product-card-v2")
    if not cards:
        cards = soup.find_all("qs-product-card-classic")
    for card in cards:
        for a in card.find_all("a", href=True):
            href = a["href"].strip()
            if "/product/" in href:
                if href.startswith("/"):
                    href = f"https://qatarsale.com{href}"
                if href not in product_links:
                    product_links.append(href)
                    break
    return product_links

def run(listing_url: str, start_page: int, end_page: int, output_csv: str):
    print("\n" + "="*50)
    print("STEP 1: Scraping listing pages for links...")
    print("="*50)

    session = requests.Session()
    all_links = set()
    failed_pages = {}
    success_count = 0

    for page_num in range(start_page, end_page + 1):
        url = f"{listing_url}&page={page_num}"
        print(f"Page {page_num}/{end_page}: {url}")
        
        for attempt in range(3):
            try:
                headers = {"User-Agent": random.choice(USER_AGENTS)}
                response = session.get(url, headers=headers, timeout=30)  # من 15 لـ 30
                if response.status_code == 200:
                    links = extract_product_links(response.text)
                    if links:
                        for l in links:
                            all_links.add(l)
                        success_count += 1
                        print(f"  Found {len(links)} links")
                    else:
                        failed_pages[f"Page {page_num}"] = "No links found"
                        print(f"  No links found")
                    break  # نخرج من الـ retry loop لو نجح
                else:
                    failed_pages[f"Page {page_num}"] = f"HTTP {response.status_code}"
                    print(f"  HTTP Error: {response.status_code}")
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