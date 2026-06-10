import json
import os
import threading
import html
import pandas as pd
import requests as req
from pathlib import Path

import boto3
from scrapling import StealthyFetcher
from concurrent.futures import ThreadPoolExecutor, as_completed

from r2_uploader import upload_single_file

def parse_product(page) -> dict:
    title = price = currency = listing_type = condition = seller_type = ""
    description = posted_time = showroom_name = showroom_url = ""
    fans_count = view_count = "0"
    latitude = longitude = ""
    phones, whatsapps, images = [], [], []
    specs = {}

    # ── 1. serverApp-state ──
    state_script = page.find("script#serverApp-state")
    if state_script:
        try:
            raw = state_script.text
            if "&q;" in raw:
                raw = raw.replace("&q;", '"').replace("&l;", "<").replace("&a;", "&").replace("&s;", "'")
            else:
                raw = html.unescape(raw)
                
            state_data = json.loads(raw)
            product_data = state_data.get("product", {}).get("product", {})

            if isinstance(product_data, dict) and product_data:
                title       = product_data.get("title", "")
                price       = str(product_data.get("startingPrice", "")) if product_data.get("startingPrice") is not None else ""
                description = product_data.get("desc", product_data.get("arDesc", ""))
                fans_count  = str(product_data.get("fansCount", 0))
                view_count  = str(product_data.get("viewCount", 0))
                posted_time = product_data.get("timeAgo", "")
                showroom_name = product_data.get("showroomName", "")

                s_uri = product_data.get("showroomUri", "")
                if s_uri:
                    showroom_url = f"https://qatarsale.com/ar/showroom/{s_uri}"

                list_type_code = str(product_data.get("advertisedFor", ""))
                listing_type = "للبيع" if list_type_code == "0" else ("للإيجار" if list_type_code == "1" else "")

                cond_obj = product_data.get("condition", {})
                if isinstance(cond_obj, dict):
                    condition = cond_obj.get("nameAr", "")

                curr_obj = product_data.get("currency", {})
                if isinstance(curr_obj, dict):
                    currency = curr_obj.get("nameAr", "")

                owner_obj = product_data.get("owner", {})
                if isinstance(owner_obj, dict):
                    seller_type = owner_obj.get("name", "")
                    for p in owner_obj.get("phones", []):
                        phone_num = p.get("phone", "").strip()
                        if phone_num:
                            if p.get("isPhone", True): phones.append(phone_num)
                            if p.get("isWhatsapp", False): whatsapps.append(phone_num)

                location_obj = product_data.get("location", {})
                if isinstance(location_obj, dict):
                    latitude  = str(location_obj.get("latitude", ""))
                    longitude = str(location_obj.get("longitude", ""))
        except Exception as e:
            print(f" [JSON Parsing Error]: {e}")

    # ── 2. HTML Fallback المحدث للموقع ──
    if not title:
        el = page.find("h1") or page.find("[data-testid*='title']")
        title = el.text.strip() if el else ""

    if not price:
        el = page.find("[data-testid='at-show-product-info-startingPrice-text']") or page.find(".product-price h2") or page.find(".price")
        price = el.text.strip() if el else ""

    if not currency:
        el = page.find("[data-testid='at-show-product-info-currency-text']") or page.find(".product-price span")
        currency = el.text.strip() if el else ""

    if not posted_time:
        el = page.find("[data-testid='at-show-product-info-productPosted-text']")
        posted_time = el.text.strip() if el else ""

    if not fans_count or fans_count == "0":
        el = page.find("[data-testid='at-show-product-info-fansCount-text']")
        fans_count = el.text.strip() if el else "0"

    if not view_count or view_count == "0":
        el = page.find("[data-testid='at-show-product-info-viewCount-text']")
        view_count = el.text.strip() if el else "0"

    if not listing_type:
        el = page.find("[data-testid='at-show-product-info-forSale-text']")
        if el:
            listing_type = el.attrib.get("title", "").strip() or el.text.strip()

    if not showroom_name:
        el = page.find("[data-testid='at-show-product-info-showroom-name-text']")
        if el:
            showroom_name = el.text.strip()
            href = el.attrib.get("href", "").strip()
            if href and not href.startswith("http"):
                showroom_url = f"https://qatarsale.com/{href}"

    if not description:
        el = page.find("[data-testid='at-show-product-description-text']") or page.find(".product-description")
        description = el.text.strip() if el else ""

    # ── 3. Specs ──
    seen = set()
    for label_el, value_el in zip(
        page.find_all("[data-testid^='at-show-product-parsedDefs-label-text-']"),
        page.find_all("[data-testid^='at-show-product-parsedDefs-value-text-']")
    ):
        key = label_el.text.strip()
        val = value_el.text.strip()
        if key and key not in seen:
            specs[key] = val
            seen.add(key)

    # ── 4. Images ──
    script = page.find("script[type='application/ld+json'][data-json-ld='true']")
    if script:
        try:
            ld_data = json.loads(script.text)
            graph = ld_data.get("@graph", []) if isinstance(ld_data, dict) else (ld_data if isinstance(ld_data, list) else [])
            for item in graph:
                if isinstance(item, dict) and item.get("@type") == "Product":
                    images = item.get("image", [])
        except Exception:
            pass
    if isinstance(images, list):
        images = [img.get("url", img) if isinstance(img, dict) else img for img in images]

    return {
        "title": title, "price": price, "currency": currency,
        "listing_type": listing_type, "condition": condition, "seller_type": seller_type,
        "description": description, "posted_time": posted_time,
        "fans_count": fans_count, "view_count": view_count,
        "showroom_name": showroom_name, "showroom_url": showroom_url,
        "phones": phones, "whatsapps": whatsapps,
        "images": images, "images_count": len(images),
        "latitude": latitude, "longitude": longitude,
        "specs": specs
    }


def download_images(images: list, images_folder: str) -> list:
    Path(images_folder).mkdir(exist_ok=True)
    local_paths = []
    
    for img_url in images:
        filename = img_url.split("/")[-1]
        local_path = os.path.join(images_folder, filename)
        if os.path.exists(local_path):
            local_paths.append(local_path)
            continue
        try:
            r = req.get(img_url, timeout=15)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(r.content)
                local_paths.append(local_path)
                
                upload_single_file(local_path, r2_folder="images")
                
        except Exception:
            pass
    return local_paths

def scrape_single(url: str, images_folder: str = "images") -> dict:
    try:
        page = StealthyFetcher.fetch(url, headless=True, network_idle=False, timeout=30000)
        data = parse_product(page)
        data["images_local_paths"] = download_images(data.get("images", []), images_folder)
        return data
    except Exception as e:
        print(f"  Error URL: {url} -> {e}")
        return {}

def run(links_csv: str, output_json: str, workers: int = 5):
    print("\n" + "="*50)
    print(f"STEP 2: Scraping product pages ({workers} workers)...")
    print("="*50)

    if not os.path.exists(links_csv):
        print(f"ERROR: '{links_csv}' not found!")
        return {"success": 0, "failed": 0}

    urls = pd.read_csv(links_csv)["product_url"].tolist()
    print(f"Loaded {len(urls)} URLs")

    scraped_urls = set()
    if os.path.exists(output_json):
        with open(output_json, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                    scraped_urls.add(row.get("product_url", ""))
                except Exception:
                    pass
        print(f"Skipping {len(scraped_urls)} already scraped")

    urls_to_scrape = [u for u in urls if u not in scraped_urls]
    print(f"Remaining: {len(urls_to_scrape)} URLs")

    if not urls_to_scrape:
        print("All URLs already scraped!")
        return {"success": 0, "failed": 0}

    counters = {"success": 0, "failed": 0}
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(scrape_single, url, "images"): url for url in urls_to_scrape}

        for future in as_completed(futures):
            url = futures[future]
            data = future.result()

            if data:
                row = {
                    "product_url": url,
                    "title": data.get("title"),
                    "price": data.get("price"),
                    "currency": data.get("currency"),
                    "listing_type": data.get("listing_type"),
                    "condition": data.get("condition"),
                    "seller_type": data.get("seller_type"),
                    "showroom_name": data.get("showroom_name"),
                    "showroom_url": data.get("showroom_url"),
                    "posted_time": data.get("posted_time"),
                    "fans_count": data.get("fans_count"),
                    "view_count": data.get("view_count"),
                    "description": data.get("description"),
                    "phones": data.get("phones", []),
                    "whatsapps": data.get("whatsapps", []),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "images": data.get("images", []),
                    "images_count": data.get("images_count"),
                    "specifications": data.get("specs", {}),
                    "images_local_paths": data.get("images_local_paths", [])
                }
                with lock:
                    with open(output_json, "a", encoding="utf-8") as f:
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                with lock:
                    counters["success"] += 1
                print(f"  Saved: {data.get('title', 'OK')}")
            else:
                with lock:
                    counters["failed"] += 1
                print(f"  Failed: {url}")

    print(f"\nSTEP 2 DONE: {counters['success']} OK | {counters['failed']} failed")
    return counters