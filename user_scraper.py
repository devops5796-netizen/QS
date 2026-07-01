import json
import time
import pandas as pd
import sys
from scrapling import StealthyFetcher
import requests as req
from PIL import Image
import io
from r2_uploader import upload_buffer
import sys
from datetime import datetime, timezone, timedelta

API_URL = "https://production-api.qatarsale.com/api/ApplicantProfile/Search"
BASE_PROFILE_URL = "https://qatarsale.com/ar/jobs/user/profile"
PAGE_SIZE = 15

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://qatarsale.com/",
    "Origin": "https://qatarsale.com",
}


def get_all_users(start_page: int = 0, end_page: int = None) -> list[dict]:
    all_users = []

    if end_page is None:
        payload = {
            "currentPage": 0, "pageSize": PAGE_SIZE, "sortBy": 0,
            "employmentTypes": [], "searchTerm": "", "yearsOfExperience": [],
            "cities": [], "countries": [], "degrees": [], "languages": [],
            "opportunityUri": None, "skills": [], "workFields": [], "workSpecialities": [],
            "isFavorite": False
        }
        r = req.post(API_URL, json=payload, headers=HEADERS, timeout=30)
        data = r.json()
        end_page = data.get("pagesCount", 1) - 1
        print(f"  Detected {end_page + 1} pages | {data.get('count', 0)} total users")

    for page in range(start_page, end_page + 1):
        payload = {
            "currentPage": page, "pageSize": PAGE_SIZE, "sortBy": 0,
            "employmentTypes": [], "searchTerm": "", "yearsOfExperience": [],
            "cities": [], "countries": [], "degrees": [], "languages": [],
            "opportunityUri": None, "skills": [], "workFields": [], "workSpecialities": [],
            "isFavorite": False
        }
        try:
            r = req.post(API_URL, json=payload, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()
            users = data.get("list", [])
            if not users:
                break
            print(f"  Page {page}: {len(users)} users")
            all_users.extend(users)
            time.sleep(1)
        except Exception as e:
            print(f"  [ERROR] Page {page}: {e}")
            break

    return all_users


def parse_user_details(url: str) -> dict:
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

        if "jobsUser" not in data:
            return {}

        user = data["jobsUser"]
        row = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
               for k, v in user.items()}
        row["profile_url"] = url
        return row

    except Exception as e:
        print(f"  [ERROR] {url}: {e}")
        return {}

def download_and_upload_image(img_url: str, user_uri: str) -> str:
    if not img_url:
        return ""
    try:
        r = req.get(img_url, timeout=15)
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content))
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="PNG")
            filename = f"{user_uri}.png"
            r2_key = upload_buffer(
                output_buffer,
                filename=filename,
                folder_name="qatarsale",
                category="users",
                file_type="images",
                content_type="image/png"
            )
            return r2_key or ""
        return ""
    except Exception as e:
        print(f"  [ERROR] Image upload failed for {user_uri}: {e}")
        return ""

def filter_yesterday_links(users: list[dict]) -> dict:
    """
    Filter users to keep only those with activatedAt equal to yesterday's date.
    Returns dict with total, yesterday count, and filtered list.
    """
    # Convert list to DataFrame for easier filtering
    df = pd.DataFrame(users)
    
    # Check if activatedAt column exists (using activatedAt as in the API response)
    if "activatedAt" not in df.columns:
        print("⚠️ No activatedAt column found, using all users")
        return {
            "total": len(df), 
            "yesterday": len(df),
            "filtered_users": users  # return all users if no date column
        }

    # Parse dates - same logic as original
    df["date_parsed"] = pd.to_datetime(df["activatedAt"], format="ISO8601", utc=True)
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    mask = df["date_parsed"].dt.date == yesterday
    df_yesterday = df[mask].drop(columns=["date_parsed"])

    print(f"  Total users:     {len(df)}")
    print(f"  Yesterday users: {len(df_yesterday)}")

    # Convert filtered DataFrame back to list of dicts
    filtered_users = df_yesterday.to_dict('records')
    
    return {
        "total": len(df), 
        "yesterday": len(df_yesterday),
        "filtered_users": filtered_users
    }

def run(output_excel: str = "users.xlsx", start_page: int = 0, end_page: int = None) -> dict:
    print("=" * 50)
    print("QatarSale Users Scraper")
    print("=" * 50)

    start_time = time.time()

    print("\nSTEP 1: Fetching users from API...")
    raw_users = get_all_users(start_page=start_page, end_page=end_page)
    print(f"Total users fetched: {len(raw_users)}")

    if not raw_users:
        print("No users found!")
        return {"total": 0, "success": 0, "failed": 0}

    print("\nSTEP 2: Filtering & Scraping user details for yesterday...")
    results = []
    failed  = []
    uri_map = {f"{BASE_PROFILE_URL}/{user.get('uriCode', '')}": user for user in raw_users}

    for i, user in enumerate(raw_users, 1):
        uri = user.get("uriCode", "")
        url = f"{BASE_PROFILE_URL}/{uri}" if uri else ""
        uri_map[url] = user
        print(f"  [{i}/{len(raw_users)}] {url}")

        data = parse_user_details(url) if url else {}

        if data:
            # Filter by activatedAt here
            filter_result = filter_yesterday_links([data])
            filtered_data = filter_result["filtered_users"]
            
            if filtered_data:
                # Only process if it's yesterday's user
                img_url  = user.get("personalPictureUrl", "")
                r2_image = download_and_upload_image(img_url, uri)
                data["image_r2_key"] = r2_image
                results.append(data)
                print(f"    ✓ {data.get('fullName', 'OK')}")
            else:
                print(f"      Skipped (not yesterday): {data.get('fullName', 'N/A')}")
        else:
            failed.append(url)
            print(f"    ✗ Failed")

    # Retry
    if failed:
        print(f"\nRetrying {len(failed)} failed URLs...")
        still_failed = []
        for url in failed:
            data = parse_user_details(url)
            if data:
                user = uri_map.get(url, {})
                img_url  = user.get("personalPictureUrl", "")
                uri      = user.get("uriCode", "")
                r2_image = download_and_upload_image(img_url, uri)
                data["image_r2_key"] = r2_image
                results.append(data)
                print(f"  ✓ {url}")
            else:
                still_failed.append(url)
                print(f"  ✗ {url}")

        failed = still_failed

    print(f"\nSTEP 4: Saving {len(results)} users to Excel...")
    df = pd.DataFrame(results)
    df.to_excel(output_excel, index=False, sheet_name="users")
    print(f"Saved: {output_excel}")

    if failed:
        with open("failed_urls.txt", "w", encoding="utf-8") as f:
            f.write(f"Total Failed URLs: {len(failed)}\n\n")
            for u in failed:
                f.write(u + "\n")

    elapsed = time.time() - start_time
    print(f"\nDONE: {len(results)} users | {len(failed)} failed | {int(elapsed//60)}m {int(elapsed%60)}s")

    return {
        "total":   len(raw_users),
        "success": len(results),
        "failed":  len(failed),
        "failed_urls": failed
    }


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end   = int(sys.argv[2]) if len(sys.argv) > 2 else None

    run(
        output_excel=f"users_{start}_{end}.xlsx",
        start_page=start,
        end_page=end
    )