import asyncio
import json
import os
import random
import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def parse_product(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    info = soup.select_one("qs-show-product-info")
    title = info.select_one("h1[title]").get_text(strip=True) if info and info.select_one("h1[title]") else ""

    price_el = soup.select_one("[data-testid='at-show-product-info-startingPrice-text']")
    price = price_el.get_text(strip=True) if price_el else ""

    currency = ""
    price_wrapper = soup.select_one(".product-price")
    if price_wrapper:
        texts = [t.get_text(strip=True) for t in price_wrapper.find_all("p")]
        currency = texts[1] if len(texts) > 1 else ""

    seller_type = soup.select_one("[data-testid='at-show-product-info-personal-name-text']")
    seller_type = seller_type.get_text(strip=True) if seller_type else ""

    listing_type = soup.select_one("[data-testid='at-show-product-info-forSale-text']")
    listing_type = listing_type.get_text(strip=True) if listing_type else ""

    condition = soup.select_one("[data-testid='at-show-product-info-conditionNew-text']")
    condition = condition.get_text(strip=True) if condition else ""

    desc_el = soup.select_one("[data-testid='at-show-product-description-text']")
    description = desc_el.get_text(strip=True) if desc_el else ""

    showroom_el = soup.select_one("[data-testid='at-show-product-info-showroom-name-text']")
    if showroom_el:
        showroom_name = showroom_el.get_text(strip=True)
        showroom_url = showroom_el.get("href", "").strip()
        if showroom_url and not showroom_url.startswith("http"):
            showroom_url = f"https://qatarsale.com/{showroom_url}"
    else:
        showroom_name = ""
        showroom_url = ""

    posted_time_el = soup.select_one("[data-testid='at-show-product-info-productPosted-text']")
    posted_time = posted_time_el.get_text(strip=True) if posted_time_el else ""

    fans_count_el = soup.select_one("[data-testid='at-show-product-info-fansCount-text']")
    fans_count = fans_count_el.get_text(strip=True) if fans_count_el else "0"

    view_count_el = soup.select_one("[data-testid='at-show-product-info-viewCount-text']")
    view_count = view_count_el.get_text(strip=True) if view_count_el else "0"

    specs = {}
    seen = set()
    for label_el, value_el in zip(
        soup.select("[data-testid^='at-show-product-parsedDefs-label-text-']"),
        soup.select("[data-testid^='at-show-product-parsedDefs-value-text-']")
    ):
        key = label_el.get_text(strip=True)
        value = value_el.get_text(strip=True)
        if key and key not in seen:
            specs[key] = value
            seen.add(key)

    phones, whatsapps = [], []
    state_script = soup.find("script", {"id": "serverApp-state"})
    if state_script and state_script.string:
        try:
            raw = state_script.string.replace("&q;", '"').replace("&l;", "<").replace("&a;", "&").replace("&s;", "'")
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
    script = soup.find("script", {"type": "application/ld+json", "data-json-ld": "true"})
    if script and script.string:
        try:
            ld_data = json.loads(script.string)
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
        "specs": specs, "images": images, "images_count": len(images)
    }

async def _scrape_page(page, url: str) -> dict:
    try:
        await page.goto(url, timeout=30000)
        try:
            await page.wait_for_selector(
                "[data-testid='at-show-product-info-startingPrice-text']",
                timeout=20000
            )
        except Exception:
            pass

        for _ in range(10):
            try:
                view_text = await page.inner_text("[data-testid='at-show-product-info-viewCount-text']")
                posted_text = await page.inner_text("[data-testid='at-show-product-info-productPosted-text']")
                if view_text.strip() not in ("0", "") and posted_text.strip() != "":
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)

        await asyncio.sleep(0.5)
        return parse_product(await page.content())
    except Exception as e:
        print(f"  Error: {e}")
        return {}

async def _worker(worker_id: int, urls: list, output_csv: str, lock: asyncio.Lock, counters: dict):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--window-size=1920,1080"]
        )
        context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
        page = await context.new_page()

        try:
            for i, url in enumerate(urls):
                print(f"  [Worker {worker_id}] ({i+1}/{len(urls)}): {url}")
                data = await _scrape_page(page, url)

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
                        "images": str(data.get("images", [])),
                        "images_count": data.get("images_count"),
                        "specifications_json": json.dumps(data.get("specs", {}), ensure_ascii=False)
                    }

                    async with lock:
                        df_row = pd.DataFrame([row])
                        if not os.path.exists(output_csv):
                            df_row.to_csv(output_csv, index=False, encoding="utf-8-sig")
                        else:
                            df_row.to_csv(output_csv, mode='a', header=False, index=False, encoding="utf-8-sig")
                    counters["success"] += 1
                    print(f"  [Worker {worker_id}] Saved: {data.get('title', 'OK')}")
                else:
                    counters["failed"] += 1
                    print(f"  [Worker {worker_id}] Failed: {url}")

                if i < len(urls) - 1:
                    await asyncio.sleep(random.uniform(1.0, 2.0))
        finally:
            await browser.close()

async def run(links_csv: str, output_csv: str, workers: int = 3):
    print("\n" + "="*50)
    print(f"STEP 2: Scraping product pages ({workers} workers)...")
    print("="*50)

    if not os.path.exists(links_csv):
        print(f"ERROR: '{links_csv}' not found!")
        return {"success": 0, "failed": 0}

    urls = pd.read_csv(links_csv)["product_url"].tolist()
    print(f"Loaded {len(urls)} URLs")

    scraped_urls = set()
    if os.path.exists(output_csv):
        try:
            existing = pd.read_csv(output_csv)
            if "product_url" in existing.columns:
                scraped_urls = set(existing["product_url"].dropna().tolist())
                print(f"Skipping {len(scraped_urls)} already scraped")
        except Exception:
            pass

    urls_to_scrape = [u for u in urls if u not in scraped_urls]
    print(f"Remaining: {len(urls_to_scrape)} URLs")

    if not urls_to_scrape:
        print("All URLs already scraped!")
        return {"success": 0, "failed": 0}


    chunks = [urls_to_scrape[i::workers] for i in range(workers)]

    lock = asyncio.Lock()
    counters = {"success": 0, "failed": 0}

    await asyncio.gather(*[
        _worker(worker_id=i+1, urls=chunks[i], output_csv=output_csv, lock=lock, counters=counters)
        for i in range(workers)
    ])

    print(f"\nSTEP 2 DONE: {counters['success']} OK, {counters['failed']} failed")
    return counters