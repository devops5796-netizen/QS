import json
import os
import threading
import pandas as pd
import requests as req
from pathlib import Path

import boto3
from scrapling import StealthyFetcher
from concurrent.futures import ThreadPoolExecutor, as_completed

def parse_product(page) -> dict:
    title_el = page.find("h1[title]")
    title = title_el.text if title_el else ""

    price_el = page.find("[data-testid='at-show-product-info-startingPrice-text']")
    price = price_el.text if price_el else ""

    currency = ""
    price_wrapper = page.find(".product-price")
    if price_wrapper:
        texts = [p.text for p in price_wrapper.find_all("p")]
        currency = texts[1] if len(texts) > 1 else ""

    seller_type_el = page.find("[data-testid='at-show-product-info-personal-name-text']")
    seller_type = seller_type_el.text if seller_type_el else ""


    condition_el = page.find("[data-testid='at-show-product-info-conditionNew-text']")
    condition = condition_el.text if condition_el else ""

    desc_el = page.find("[data-testid='at-show-product-description-text']")
    description = desc_el.text if desc_el else ""

    # listing_type
    listing_type_el = page.find("[data-testid='at-show-product-info-forSale-text']")
    listing_type = listing_type_el.find("p").text if listing_type_el and listing_type_el.find("p") else ""

    # showroom
    showroom_el = page.find("[data-testid='at-show-product-info-showroom-name-text']")
    if showroom_el:
        showroom_name = showroom_el.find("p").text if showroom_el.find("p") else showroom_el.text
        showroom_url = showroom_el.attrib.get("href", "").strip()
        if showroom_url and not showroom_url.startswith("http"):
            showroom_url = f"https://qatarsale.com/{showroom_url}"
    else:
        showroom_name = ""
        showroom_url = ""

    posted_time_el = page.find("[data-testid='at-show-product-info-productPosted-text']")
    posted_time = posted_time_el.text if posted_time_el else ""

    fans_count_el = page.find("[data-testid='at-show-product-info-fansCount-text']")
    fans_count = fans_count_el.text if fans_count_el else "0"

    view_count_el = page.find("[data-testid='at-show-product-info-viewCount-text']")
    view_count = view_count_el.text if view_count_el else "0"

    specs = {}
    seen = set()
    labels = page.find_all("[data-testid^='at-show-product-parsedDefs-label-text-']")
    values = page.find_all("[data-testid^='at-show-product-parsedDefs-value-text-']")
    for label_el, value_el in zip(labels, values):
        key = label_el.text.strip()
        value = value_el.text.strip()
        if key and key not in seen:
            specs[key] = value
            seen.add(key)

    phones, whatsapps = [], []
    state_script = page.find("script#serverApp-state")
    if state_script:
        try:
            raw = state_script.text.replace("&q;", '"').replace("&l;", "<").replace("&a;", "&").replace("&s;", "'")
            state_data = json.loads(raw)
            owner = state_data.get("product", {}).get("product", {}).get("owner", {})
            for p in owner.get("phones", []):
                phone_num = p.get("phone", "").strip()
                if phone_num:
                    if p.get("isPhone", True): phones.append(phone_num)
                    if p.get("isWhatsapp", False): whatsapps.append(phone_num)
        except Exception:
            pass

    images = []
    script = page.find("script[type='application/ld+json'][data-json-ld='true']")
    if script:
        try:
            ld_data = json.loads(script.text)
            for item in ld_data.get("@graph", []):
                if item.get("@type") == "Product":
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
        "specs": specs
    }


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("CF_R2_ENDPOINT_URL"),
        aws_access_key_id=os.environ.get("CF_R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("CF_R2_SECRET_ACCESS_KEY"),
        region_name="auto"
    )

def download_images(images: list, images_folder: str) -> list:
    Path(images_folder).mkdir(exist_ok=True)
    r2 = get_r2_client()
    bucket = os.environ.get("CF_R2_BUCKET_NAME", "")
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
                # upload to R2
                if r2 and bucket:
                    try:
                        r2.upload_file(
                            local_path, bucket,
                            f"images/{filename}",
                            ExtraArgs={"ContentType": "image/webp"}
                        )
                    except Exception as e:
                        print(f"  R2 upload error: {filename} -> {e}")
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
        print(f"  Error: {url} -> {e}")
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