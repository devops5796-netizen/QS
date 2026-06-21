import json
import time
import requests
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

    # STEP 1: detect total pages
    if end_page is None:
        payload = {
            "currentPage": 0,
            "pageSize": PAGE_SIZE,
            "sortBy": 0,
            "workFields": [], "workSpecialities": [], "employmentTypes": [],
            "workplaceTypes": [], "searchTerm": "", "experiences": [],
            "countries": [], "languages": [], "cities": [], "degrees": [],
            "skills": [], "userId": None, "isFavorite": False, "yearsOfExperience": []
        }
        r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
        data = r.json()
        end_page = data.get("pagesCount", 1) - 1
        print(f"  Detected {end_page + 1} pages | {data.get('count', 0)} total jobs")

    for page in range(start_page, end_page + 1):
        payload = {
            "currentPage": page,
            "pageSize": PAGE_SIZE,
            "sortBy": 0,
            "workFields": [], "workSpecialities": [], "employmentTypes": [],
            "workplaceTypes": [], "searchTerm": "", "experiences": [],
            "countries": [], "languages": [], "cities": [], "degrees": [],
            "skills": [], "userId": None, "isFavorite": False, "yearsOfExperience": []
        }
        try:
            r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
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


def parse_job_from_api(job: dict) -> dict:
    # salary
    salary_type = job.get("salaryType", 0)
    if salary_type == 2:
        salary = "قابل للتفاوض"
    else:
        min_s    = job.get("minSalary", "")
        max_s    = job.get("maxSalary", "")
        currency = job.get("currencyName", "")
        if min_s and max_s:
            salary = f"{min_s} - {max_s} {currency}"
        elif min_s:
            salary = f"{min_s} {currency}"
        else:
            salary = ""

    employment_types = ", ".join([e.get("name", "") for e in job.get("employmentTypes", [])])
    workplace        = job.get("workplaceType", {}).get("name", "") if job.get("workplaceType") else ""

    uri     = job.get("uri", "")
    job_url = f"{BASE_JOB_URL}/{uri}" if uri else ""

    created_at = job.get("createdAt", "")
    if created_at:
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    approved_at = job.get("approvedAt", "")
    if approved_at:
        try:
            approved_at = datetime.fromisoformat(approved_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    return {
        "job_url":         job_url,
        "title":           job.get("jobTitle", ""),
        "company":         job.get("companyName", "").strip(),
        "city":            job.get("cityName", ""),
        "country":         job.get("countryName", ""),
        "salary":          salary,
        "salary_type":     salary_type,
        "min_salary":      job.get("minSalary", ""),
        "max_salary":      job.get("maxSalary", ""),
        "currency":        job.get("currencyName", ""),
        "employment_type": employment_types,
        "workplace_type":  workplace,
        "views_count":     job.get("viewsCount", 0),
        "created_at":      created_at,
        "approved_at":     approved_at,
        "status":          job.get("status", ""),
        "published":       job.get("published", ""),
        "company_picture": job.get("companyPicture", ""),
    }


def parse_job_details(url: str) -> dict:
    try:
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=60000,
            wait_for_idle_network_timeout=10000
        )

        # title
        title_el = page.find("[class*='name']")
        title = title_el.text.strip() if title_el else ""

        # company
        company_el = page.css(".data .row .p3")
        company = company_el[0].get_all_text(strip=True) if company_el else ""

        # location
        location_el = page.find("[data-testid='at-jobs-opportunity-details-location-text']")
        location = location_el.text.strip() if location_el else ""

        # posted_date
        date_el = page.find("[data-testid='at-jobs-opportunity-details-time-text']")
        posted_date = date_el.text.strip() if date_el else ""

        salary = ""
        # nigotiable
        negotiable_el = page.find("[data-testid='at-jobs-opportunity-details-salaryType-nigotiable-text']")
        # range
        range_el = page.find("[data-testid='at-jobs-opportunity-details-salaryType-range-text']")
        # fixed
        fixed_el = page.find("[data-testid='at-jobs-opportunity-details-salaryType-fixed-text']")

        if negotiable_el:
            salary = negotiable_el.text.strip()
        elif range_el:
            salary = range_el.get_all_text(strip=True)
        elif fixed_el:
            salary = fixed_el.get_all_text(strip=True)

        # employment_types
        employment_types = []
        for el in page.css("[data-testid^='at-jobs-opportunity-details-employmentTypes-text']"):
            t = el.text.strip()
            if t:
                employment_types.append(t)

        # workplace
        workplace_el = page.find("[data-testid='at-jobs-opportunity-details-workplaceType-text']")
        workplace = workplace_el.text.strip() if workplace_el else ""

        # description
        desc_el = page.css(".left-container .list span")
        description = desc_el[0].get_all_text(strip=True) if desc_el else ""

        # experiences
        experiences = []
        for el in page.css("[data-testid^='at-jobs-opportunity-details-experience-']"):
            title_span = el.find(".title")
            desc_span  = el.find(".description")
            if title_span:
                experiences.append({
                    "role":  title_span.text.strip(),
                    "years": desc_span.text.strip() if desc_span else ""
                })

        # skills
        skills = []
        for el in page.css("[data-testid^='at-jobs-opportunity-details-skill-']"):
            title_span = el.find(".title")
            desc_span  = el.find(".description")
            if title_span:
                skills.append({
                    "skill": title_span.text.strip(),
                    "level": desc_span.text.strip() if desc_span else ""
                })

        return {
            "job_url":         url,
            "title":           title,
            "company":         company,
            "location":        location,
            "posted_date":     posted_date,
            "salary":          salary,
            "employment_type": ", ".join(employment_types),
            "workplace_type":  workplace,
            "description":     description,
            "experience":      json.dumps(experiences, ensure_ascii=False),
            "skills":          json.dumps(skills, ensure_ascii=False),
        }

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

    # STEP 1: Collect jobs url from API
    print("\nSTEP 1: Fetching jobs from API...")
    raw_jobs = get_all_jobs(start_page=start_page, end_page=end_page)
    print(f"Total jobs fetched: {len(raw_jobs)}")

    if not raw_jobs:
        print("No jobs found!")
        return {"total": 0, "success": 0, "failed": 0}
    
    #raw_jobs = raw_jobs[:15]
    #print(f"Testing with first {len(raw_jobs)} jobs...")

    # STEP 2: API + Scraping 
    print("\nSTEP 2: Parsing API data + Scraping details...")
    results = []
    failed  = []

    for i, job in enumerate(raw_jobs, 1):
        uri = job.get("uri", "")
        url = f"{BASE_JOB_URL}/{uri}" if uri else ""

        print(f"  [{i}/{len(raw_jobs)}] {url}")

        # API data
        api_data = parse_job_from_api(job)
        img_url  = job.get("companyPicture", "")
        uri      = job.get("uri", "")
        r2_image = download_and_upload_image(img_url, uri)
        api_data["image_r2_key"] = r2_image

        # Scraping data
        scraped_data = parse_job_details(url) if url else {}
        if scraped_data:
            print(f"    ✓ {api_data.get('title', 'N/A')} | {api_data.get('company', 'N/A')}")
        else:
            print(f"    ✗ Scraping failed")
            failed.append(url)

        merged = {}
        for k, v in api_data.items():
            merged[f"api_{k}"] = v
        for k, v in scraped_data.items():
            merged[f"scraped_{k}"] = v

        results.append(merged)
        time.sleep(1)

    # Retry failed
    if failed:
        print(f"\nRetrying {len(failed)} failed URLs...")
        still_failed = []
        for url in failed:
            scraped_data = parse_job_details(url)
            if scraped_data:
                for row in results:
                    if row.get("api_job_url") == url:
                        for k, v in scraped_data.items():
                            row[f"scraped_{k}"] = v
                print(f"  ✓ {url}")
            else:
                still_failed.append(url)
                print(f"  ✗ {url}")
        failed = still_failed

    print(f"\nSTEP 3: Saving {len(results)} jobs to Excel...")
    df = pd.DataFrame(results)

    columns_order = [
        'api_job_url', 'api_title', 'scraped_title', 'api_company', 'api_city', 'api_country', 'scraped_location',
        'api_salary', 'api_salary_type', 'api_min_salary', 'api_max_salary', 'api_currency',
        'scraped_salary', 'api_employment_type', 'scraped_employment_type', 'api_workplace_type',
        'scraped_workplace_type', 'api_views_count', 'api_created_at', 'api_approved_at', 'api_status',
        'api_published', 'scraped_description', 'scraped_experience', 'scraped_skills', 'api_image_r2_key'
    ]

    columns_order = [c for c in columns_order if c in df.columns]
    df = df[columns_order]

    df.to_excel(output_excel, index=False, sheet_name="jobs")
    print(f"Saved: {output_excel}")

    elapsed = time.time() - start_time
    print(f"\nDONE: {len(results)} jobs | {len(failed)} failed | {int(elapsed//60)}m {int(elapsed%60)}s")

    if failed:
        with open("failed_urls.txt", "w", encoding="utf-8") as f:
            f.write(f"Total Failed URLs: {len(failed)}\n\n")
            for u in failed:
                f.write(u + "\n")

    return {
        "total":       len(raw_jobs),
        "success":     len(results) - len(failed),
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