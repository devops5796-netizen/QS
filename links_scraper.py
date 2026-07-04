import json
import time
import random
import requests
import pandas as pd

API_URL = "https://production-api.qatarsale.com/api/v2/Products"
BASE_PRODUCT_URL = "https://qatarsale.com/ar/product"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://qatarsale.com/",
    "Origin": "https://qatarsale.com",
}


def fetch_page(listing_path: str, page_num: int, page_size: int = 36) -> dict:
    payload = {
        "url": listing_path,
        "includeFavs": False,
        "pageSize": page_size,
        "currentPage": page_num - 1,  
    }
    response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def extract_products_from_response(data: dict, source_url: str) -> list:
    rows = []
    defs_map = {str(d["id"]): d["label"] for d in data.get("defsMetaData", [])}

    for product in data.get("list", []):
        row = {k: v for k, v in product.items() if k != "definitions"}
        definitions = product.get("definitions", {})
        for def_id, value in definitions.items():
            col_name = defs_map.get(def_id, f"unknown_{def_id}")
            row[col_name] = value

        row["source_url"] = source_url
        row["product_url"] = f"{BASE_PRODUCT_URL}/{product.get('uri', '')}" if product.get("uri") else ""
        rows.append(row)

    return rows


def run(listing_path: str, start_page: int, end_page: int, output_csv: str):
    print("\n" + "="*50)
    print("STEP 1: Scraping listing pages via API...")
    print("="*50)

    all_rows = []
    failed_pages = {}
    success_count = 0

    for page_num in range(start_page, end_page + 1):
        print(f"Page {page_num}/{end_page}")

        for attempt in range(3):
            try:
                data = fetch_page(listing_path, page_num)
                rows = extract_products_from_response(data, listing_path)

                if rows:
                    all_rows.extend(rows)
                    success_count += 1
                    print(f"  ✓ Found {len(rows)} products")
                else:
                    failed_pages[f"Page {page_num}"] = "No products found"
                    print(f"  ⚠ No products found")
                break

            except Exception as e:
                if attempt < 2:
                    print(f"  Attempt {attempt+1} failed, retrying...")
                    time.sleep(3)
                else:
                    failed_pages[f"Page {page_num}"] = str(e)
                    print(f"  Error: {e}")

        if page_num < end_page:
            time.sleep(random.uniform(0.5, 1.5))

    df = pd.DataFrame(all_rows)

    if "product_url" in df.columns:
        df = df.drop_duplicates(subset=["product_url"], keep="first")

    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"  Saved {len(df)} products to {output_csv}")

    return {
        "success": success_count,
        "failed": len(failed_pages),
        "total_links": len(df)
    }


if __name__ == "__main__":
    result = run(
        listing_path="/ar/products/wrist_watches-watches?basic_search:StatusFilter=0",
        start_page=1,
        end_page=5,
        output_csv="product_links.csv",
    )
    print(result)