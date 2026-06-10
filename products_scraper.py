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
    title = price = currency = listing_type = posted_time = description = ""
    showroom_name = showroom_url = sold_date = ""
    seller_type = ""  
    condition = ""    
    view_count = fans_count = "0"
    images = []
    phones = []       
    whatsapps = []    
    specs = {}

    title_el = page.find("[data-testid='at-show-product-info-market-title-text']") or page.find("h1")
    if title_el:
        title = title_el.text.strip()

    price_el = page.find("[data-testid='at-show-product-info-startingPrice-text']")
    if price_el:
        price = price_el.text.strip()
        
    curr_el = page.find(".product-price p:not([data-testid])")
    if curr_el:
        currency = curr_el.text.strip()

    posted_el = page.find("[data-testid='at-show-product-info-productPosted-text']")
    if posted_el:
        posted_time = posted_el.text.strip()

    view_el = page.find("[data-testid='at-show-product-info-viewCount-text']")
    if view_el:
        view_count = view_el.text.strip()

    fans_el = page.find("[data-testid='at-show-product-info-fansCount-text']")
    if fans_el:
        fans_count = fans_el.text.strip()

    type_el = page.find("[data-testid='at-show-product-info-forSale-text']")
    if type_el:
        listing_type = type_el.attrib.get("title", "").strip() or type_el.text.strip()

    sold_el = page.find("[data-testid='at-show-product-info-soldDate-text']")
    if sold_el:
        sold_date = sold_el.text.strip()

    desc_el = page.find("[data-testid='at-show-product-description-text']")
    if desc_el:
        description = desc_el.text.strip()

    showroom_el = page.find("[data-testid='at-show-product-info-showroom-name-text']")
    personal_el = page.find("[data-testid='at-show-product-info-personal-name-text']")

    if showroom_el:
        seller_type = "showroom"
        showroom_name = showroom_el.text.strip()
        href = showroom_el.attrib.get("href", "").strip()
        if href:
            showroom_url = href if href.startswith("http") else f"https://qatarsale.com/{href}"
    elif personal_el:
        seller_type = "personal"
        showroom_name = personal_el.text.strip()
        personal_listings_el = page.find("[data-testid='at-show-product-info-personalOtherListings-name-text']")
        if personal_listings_el:
            p_href = personal_listings_el.attrib.get("href", "").strip()
            if p_href:
                showroom_url = p_href if p_href.startswith("http") else f"https://qatarsale.com/{p_href}"

    condition_new_el = page.find("[data-testid='at-show-product-info-conditionNew-text']")
    if condition_new_el:
        condition = condition_new_el.text.strip()

    phone_el = page.find("[data-testid='at-show-product-info-increaseCount-button']")
    if phone_el:
        phone_href = phone_el.attrib.get("href", "").replace("tel:", "").strip()
        if phone_href:
            phones.append(phone_href)
            
    whatsapp_el = page.find(".wtsup")
    if whatsapp_el:
        wa_href = whatsapp_el.attrib.get("href", "").strip()
        if wa_href:
            whatsapps.append(wa_href)

    seen_images = set()
    img_elements = page.find_all("[data-testid='at-show-product-gallery-galleryImages-normal-image'] img")
    for img_el in img_elements:
        img_src = img_el.attrib.get("src", "").strip()
        if img_src:
            high_res_img = img_src.replace("_thumb.webp", ".webp")
            if high_res_img not in seen_images:
                images.append(high_res_img)
                seen_images.add(high_res_img)

    labels = page.find_all("[data-testid^='at-show-product-parsedDefs-label-text-']")
    values = page.find_all("[data-testid^='at-show-product-parsedDefs-value-text-']")
    
    if labels and values:
        for lbl, val in zip(labels, values):
            key = lbl.text.strip()
            value = val.text.strip()
            if key:
                specs[key] = value

    return {
        "title": title,
        "price": price,
        "currency": currency,
        "listing_type": listing_type,
        "condition": condition,        
        "seller_type": seller_type,    
        "posted_time": posted_time,
        "sold_date": sold_date,
        "view_count": view_count,
        "fans_count": fans_count,
        "showroom_name": showroom_name,
        "showroom_url": showroom_url,  
        "description": description,
        "images": images,
        "images_count": len(images),
        "phones": phones,        
        "whatsapps": whatsapps,  
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
        page = StealthyFetcher.fetch(url, headless=True, network_idle=True, timeout=30000)
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
                    "sold_date": data.get("sold_date"),
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