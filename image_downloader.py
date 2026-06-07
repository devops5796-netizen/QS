import os
import ast
import random
import time
import requests
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def _download_single(url: str, images_folder: str) -> tuple:
    filename = url.split("/")[-1]
    local_path = os.path.join(images_folder, filename)

    if os.path.exists(local_path):
        return local_path, "exists"
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": "https://qatarsale.com/",
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    }
    
    # retry 3 مرات لو فشل
    for attempt in range(3):
        try:
            time.sleep(random.uniform(0.3, 0.8))  # delay صغير بين كل request
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(response.content)
                return local_path, "downloaded"
            
            elif response.status_code == 429:  # Too Many Requests
                wait = (attempt + 1) * 5
                print(f"  Rate limited! Waiting {wait}s...")
                time.sleep(wait)
                
            else:
                return "", "failed"
                
        except Exception as e:
            if attempt == 2:
                return "", "failed"
            time.sleep(2)

    return "", "failed"

def run(input_csv: str, output_csv: str, images_folder: str, workers: int = 5):
    print("\n" + "="*50)
    print(f"STEP 4: Downloading images ({workers} workers)...")
    print("="*50)

    Path(images_folder).mkdir(exist_ok=True)
    df = pd.read_csv(input_csv)

    all_tasks = []
    for idx, row in df.iterrows():
        try:
            urls = ast.literal_eval(row.get("images", "[]"))
        except Exception:
            urls = []
        for url in urls:
            all_tasks.append((idx, url))

    print(f"Total images to download: {len(all_tasks)}")

    results = {}
    downloaded_count = 0
    failed_count = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_download_single, url, images_folder): (idx, url)
            for idx, url in all_tasks
        }
        for future in as_completed(futures):
            idx, url = futures[future]
            local_path, status = future.result()

            if idx not in results:
                results[idx] = []
            results[idx].append(local_path)

            if status == "downloaded":
                downloaded_count += 1
                print(f"  Downloaded: {url.split('/')[-1]}")
            elif status == "failed":
                failed_count += 1
                print(f"  Failed: {url.split('/')[-1]}")

    df["images_local_paths"] = [str(results.get(idx, [])) for idx in df.index]
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")

    print(f"\nSTEP 4 DONE: {downloaded_count} downloaded | {failed_count} failed")
    return {"downloaded": downloaded_count, "failed": failed_count}