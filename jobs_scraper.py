import json
import time
import pandas as pd
from datetime import datetime
from scrapling import StealthyFetcher
import requests as req
from PIL import Image
import io
from r2_uploader import upload_buffer
import sys

API_URL = "https://production-api.qatarsale.com/api/Opportunity/Search"
BASE_JOB_URL = "https://qatarsale.com/ar/jobs/opportunity"
PAGE_SIZE = 15

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://qatarsale.com/",
    "Origin": "https://qatarsale.com",
}


def get_all_jobs(start_page: int = 0, end_page: int = None) -> list[dict]:
    all_jobs = []

    if end_page is None:
        payload = {
            "currentPage": 0, "pageSize": PAGE_SIZE, "sortBy": 0,
            "workFields": [], "workSpecialities": [], "employmentTypes": [],
            "workplaceTypes": [], "searchTerm": "", "experiences": [],
            "countries": [], "languages": [], "cities": [], "degrees": [],
            "skills": [], "userId": None, "isFavorite": False, "yearsOfExperience": []
        }
        r = req.post(API_URL, json=payload, headers=HEADERS, timeout=30)
        data = r.json()
        end_page = data.get("pagesCount", 1) - 1
        print(f"  Detected {end_page + 1} pages | {data.get('count', 0)} total jobs")

    for page in range(start_page, end_page + 1):
        payload = {
            "currentPage": page, "pageSize": PAGE_SIZE, "sortBy": 0,
            "workFields": [], "workSpecialities": [], "employmentTypes": [],
            "workplaceTypes": [], "searchTerm": "", "experiences": [],
            "countries": [], "languages": [], "cities": [], "degrees": [],
            "skills": [], "userId": None, "isFavorite": False, "yearsOfExperience": []
        }
        try:
            r = req.post(API_URL, json=payload, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()
            jobs = data.get("list", [])
            if not jobs:
                break
            print(f"  Page {page}: {len(jobs)} jobs")
            all_jobs.extend(jobs)
            time.sleep(1)
        except Exception as e:
            print(f"  [ERROR] Page {page}: {e}")
            break

    return all_jobs


def parse_job_details(url: str) -> dict:
    try:
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=60000,
            wait_for_idle_network_timeout=10000
        )

        if "not-found" in str(page.url):
            print(f"  Redirected to not-found: {url}")
            return {}

        script = page.find("script#serverApp-state")
        if not script:
            return {}

        raw = (script.text
               .replace("&q;", '"')
               .replace("&l;", "<")
               .replace("&g;", ">")
               .replace("&a;", "&")
               .replace("&s;", "'"))

        data = json.loads(raw)

        if "jobsOpportunity" not in data or "data" not in data["jobsOpportunity"]:
            return {}

        job = data["jobsOpportunity"]["data"]
        row = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
               for k, v in job.items()}
        row["job_url"] = url
        return row

    except Exception as e:
        print(f"  [ERROR] {url}: {e}")
        return {}


def download_and_upload_image(img_url: str, job_uri: str) -> str:
    if not img_url:
        return ""
    try:
        r = req.get(img_url, timeout=15)
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content))
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="PNG")
            filename = f"{job_uri}.png"
            r2_key = upload_buffer(
                output_buffer,
                filename=filename,
                folder_name="qatarsale",
                category="jobs",
                file_type="images",
                content_type="image/png"
            )
            return r2_key or ""
        return ""
    except Exception as e:
        print(f"  [ERROR] Image upload failed for {job_uri}: {e}")
        return ""


def run(output_excel: str = "jobs.xlsx", start_page: int = 0, end_page: int = None) -> dict:
    print("=" * 50)
    print("QatarSale Jobs Scraper")
    print("=" * 50)

    start_time = time.time()

    print("\nSTEP 1: Fetching jobs from API...")
    raw_jobs = get_all_jobs(start_page=start_page, end_page=end_page)
    print(f"Total jobs fetched: {len(raw_jobs)}")

    if not raw_jobs:
        print("No jobs found!")
        return {"total": 0, "success": 0, "failed": 0, "failed_urls": []}

    print("\nSTEP 2: Scraping job details...")
    results = []
    failed  = []
    uri_map = {f"{BASE_JOB_URL}/{job.get('uri', '')}": job for job in raw_jobs}

    for i, job in enumerate(raw_jobs, 1):
        uri = job.get("uri", "")
        url = f"{BASE_JOB_URL}/{uri}" if uri else ""

        print(f"  [{i}/{len(raw_jobs)}] {url}")

        data = parse_job_details(url) if url else {}

        if data:
            img_url  = job.get("companyPicture", "")
            r2_image = download_and_upload_image(img_url, uri)
            data["image_r2_key"] = r2_image
            results.append(data)
            print(f"    ✓ {data.get('jobTitleName', 'N/A')} | {data.get('companyName', 'N/A')}")
        else:
            failed.append(url)
            print(f"    ✗ Failed")

        time.sleep(1)

    # Retry failed
    if failed:
        print(f"\nRetrying {len(failed)} failed URLs...")
        still_failed = []
        for url in failed:
            data = parse_job_details(url)
            if data:
                job = uri_map.get(url, {})
                img_url  = job.get("companyPicture", "")
                uri      = job.get("uri", "")
                r2_image = download_and_upload_image(img_url, uri)
                data["image_r2_key"] = r2_image
                results.append(data)
                print(f"  ✓ {url}")
            else:
                still_failed.append(url)
                print(f"  ✗ {url}")
        failed = still_failed

    print(f"\nSTEP 3: Saving {len(results)} jobs to Excel...")
    df = pd.DataFrame(results)
    df.to_excel(output_excel, index=False, sheet_name="jobs")
    print(f"Saved: {output_excel}")

    if failed:
        with open("failed_urls.txt", "w", encoding="utf-8") as f:
            f.write(f"Total Failed URLs: {len(failed)}\n\n")
            for u in failed:
                f.write(u + "\n")

    elapsed = time.time() - start_time
    print(f"\nDONE: {len(results)} jobs | {len(failed)} failed | {int(elapsed//60)}m {int(elapsed%60)}s")

    return {
        "total":       len(raw_jobs),
        "success":     len(results),
        "failed":      len(failed),
        "failed_urls": failed
    }


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end   = int(sys.argv[2]) if len(sys.argv) > 2 else None
    run(
        output_excel=f"jobs_{start}_{end}.xlsx",
        start_page=start,
        end_page=end
    )