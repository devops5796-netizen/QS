import json
import time
import requests
import pandas as pd
from datetime import datetime
import sys
from scrapling import StealthyFetcher

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
        r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
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
            r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
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


def parse_user_from_api(user: dict) -> dict:
    employment_types = ", ".join([e.get("name", "") for e in user.get("employmentTypes", [])])
    uri = user.get("uriCode", "")
    profile_url = f"{BASE_PROFILE_URL}/{uri}" if uri else ""

    return {
        "profile_url":            profile_url,
        "full_name":              user.get("fullName", ""),
        "title":                  user.get("title", ""),
        "city":                   user.get("cityName", ""),
        "country":                user.get("countryName", ""),
        "total_experience_years": user.get("totalExperienceYears", ""),
        "employment_type":        employment_types,
        "views_count":            user.get("viewsCount", 0),
        "picture_url":            user.get("personalPictureUrl", ""),
    }


def parse_user_details(url: str) -> dict:
    try:
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=60000,
            wait_for_idle_network_timeout=10000
        )
        

        # name
        name_el = page.find(".data .name")
        name = name_el.text.strip() if name_el else ""

        # title
        rows = page.css(".data .row")
        title = rows[1].find(".p3").text.strip() if len(rows) > 1 else ""
        #print(f"titie: {title}")

        # location
        city_el    = page.find(".data .city.p3")
        city       = city_el.text.strip() if city_el else ""
        country_el = page.find(".data .county.p3")
        country    = country_el.text.strip() if country_el else ""

        # exp summary
        summary = ""
        for group in page.css(".right-container .group"):
            header = group.find(".header")
            if header and "الملخص" in header.text:
                span = group.find(".list span")
                summary = span.get_all_text(strip=True) if span else ""
                break

        # work_experience
        work_experience = []
        for group in page.css(".right-container .group"):
            header = group.find(".header")
            if not header or "التجربة العملية" not in header.text:
                continue
            for item in group.css("qs-jobs-user-profile-list-item .item"):
                title_span    = item.find("[data-testid='at--title-text']")
                location_span = item.find("[data-testid='at--country-city']")
                start_span    = item.find("[data-testid='at--startDate-text']")
                end_span      = item.find("[data-testid='at--endDate-text']")
                desc_span     = item.find("[data-testid='at--link-description-text']")
                

                work_experience.append({
                    "title":       title_span.text.strip()    if title_span    else "",
                    "location":    location_span.text.strip() if location_span else "",
                    "start_date":  start_span.text.strip()    if start_span    else "",
                    "end_date":    end_span.text.strip()      if end_span      else "",
                    "description": desc_span.get_all_text(strip=True) if desc_span else "",
                })

        # education
        education = []
        for group in page.css(".right-container .group"):
            header = group.find(".header")
            if not header or "التجربة العلمية" not in header.text:
                continue
            for item in group.css("qs-jobs-user-profile-list-item .item"):
                title_span    = item.find("[data-testid='at--title-text']")
                location_span = item.find("[data-testid='at--country-city']")
                start_span    = item.find("[data-testid='at--startDate-text']")
                end_span      = item.find("[data-testid='at--endDate-text']")
                description   = item.find("[data-testid='at--link-description-text']")
                education.append({
                    "degree":     title_span.text.strip()    if title_span    else "",
                    "location":   location_span.text.strip() if location_span else "",
                    "start_date": start_span.text.strip()    if start_span    else "",
                    "end_date":   end_span.text.strip()      if end_span      else "",
                    "description": description.get_all_text(strip=True) if description else "",
                })


        # availability
        availability_el    = page.find("[data-testid='at-jobs-user-profile-openToWork']")
        availability       = "متاح للعمل" if availability_el else ""
        availability_types = []
        for group in page.css(".group"):
            header = group.find(".header")
            if not header or "التوفر" not in header.text:
                continue
            for el in group.css("[data-testid^='at-jobs-user-profile-employmentTypes-']"):
                t = el.text.strip()
                if t:
                    availability_types.append(t)

        # skills
        skills = []
        for group in page.css(".group"):
            header = group.find(".header")
            if not header or "مهاراتي" not in header.text:
                continue
            for el in group.css("[data-testid='at-jobs-user-profile-skills-title']"):
                skill_title = el.text.strip()
                desc_el     = el.parent.find("[data-testid='at-jobs-user-profile-skills-description']")
                skills.append({
                    "skill": skill_title,
                    "level": desc_el.text.strip() if desc_el else ""
                })

        # languages
        languages = []
        for group in page.css(".group"):
            header = group.find(".header")
            if not header or "لغاتي" not in header.text:
                continue
            for item in group.css("qs-jobs-user-profile-sub-list-item .item"):
                title_span = item.find("[data-testid='at--title']")
                desc_span  = item.find("[data-testid='at--description']")
                if title_span:
                    languages.append({
                        "language": title_span.text.strip(),
                        "level":    desc_span.text.strip() if desc_span else ""
                    })

        # certifications
        certifications = []
        for group in page.css(".group"):
            header = group.find(".header")
            if not header or "التراخيص" not in header.text:
                continue
            for item in group.css("qs-jobs-user-profile-sub-list-item .item"):
                title_span = item.find("[data-testid='at--title']")
                desc_span  = item.find("[data-testid='at--description']")
                date_span  = item.find("[data-testid='at--startDate']")
                certifications.append({
                    "title":       title_span.text.strip() if title_span else "",
                    "institution": desc_span.text.strip()  if desc_span  else "",
                    "date":        date_span.text.strip()  if date_span  else "",
                })

        # social_links
        social_links = []
        for group in page.css(".group"):
            header = group.find(".header")
            if not header or "الحسابات" not in header.text:
                continue
            for el in group.css("i"):
                classes = el.attrib.get("class", "")
                if "fa-instagram" in classes:
                    social_links.append("instagram")
                elif "fa-linkedin" in classes:
                    social_links.append("linkedin")
                elif "fa-twitter" in classes:
                    social_links.append("twitter")
                elif "fa-facebook" in classes:
                    social_links.append("facebook")
                elif "fa-youtube" in classes:
                    social_links.append("youtube")
        

        return {
            "profile_url":        url,
            "name":               name,
            "title":              title, 
            "city":               city,
            "country":            country,
            "summary":            summary,
            "work_experience":    json.dumps(work_experience,  ensure_ascii=False),
            "education":          json.dumps(education,        ensure_ascii=False),
            "availability":       availability,
            "availability_types": ", ".join(availability_types),
            "skills":             json.dumps(skills,           ensure_ascii=False),
            "languages":          json.dumps(languages,        ensure_ascii=False),
            "certifications":     json.dumps(certifications,   ensure_ascii=False),
            "social_links":       ", ".join(social_links),
        }

    except Exception as e:
        print(f"  [ERROR] {url}: {e}")
        return {}


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

    #raw_users = raw_users[:3]
    #print(f"Testing with first {len(raw_users)} users...")

    print("\nSTEP 2: Parsing API data + Scraping details...")
    results = []
    failed  = []

    for i, user in enumerate(raw_users, 1):
        uri = user.get("uriCode", "")
        url = f"{BASE_PROFILE_URL}/{uri}" if uri else ""

        print(f"  [{i}/{len(raw_users)}] {url}")

        api_data     = parse_user_from_api(user)
        scraped_data = parse_user_details(url) if url else {}

        if scraped_data:
            print(f"    ✓ {api_data.get('full_name', 'N/A')}")
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

    # Retry
    if failed:
        print(f"\nRetrying {len(failed)} failed URLs...")
        still_failed = []
        for url in failed:
            scraped_data = parse_user_details(url)
            if scraped_data:
                for row in results:
                    if row.get("api_profile_url") == url:
                        for k, v in scraped_data.items():
                            row[f"scraped_{k}"] = v
                print(f"  ✓ {url}")
            else:
                still_failed.append(url)
                print(f"  ✗ {url}")
        failed = still_failed

    print(f"\nSTEP 3: Saving {len(results)} users to Excel...")
    df = pd.DataFrame(results)
    #print(df['scraped_title'])

    columns_order = [
        'api_profile_url', 'api_full_name', 'scraped_name',
        'api_title', 'scraped_title',
        'api_city', 'api_country', 'scraped_city', 'scraped_country',
        'api_total_experience_years', 'api_employment_type', 'api_views_count',
        'api_picture_url', 'scraped_availability', 'scraped_availability_types',
        'scraped_summary', 'scraped_work_experience', 'scraped_education',
        'scraped_skills', 'scraped_languages', 'scraped_certifications',
        'scraped_social_links'
    ]
    columns_order = [c for c in columns_order if c in df.columns]
    df = df[columns_order]

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
        "total":       len(raw_users),
        "success":     len(results) - len(failed),
        "failed":      len(failed),
        "failed_urls": failed
    }


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end   = int(sys.argv[2]) if len(sys.argv) > 2 else None

    #start = 0
    #end   = 0

    run(
        output_excel=f"users_{start}_{end}.xlsx",
        start_page=start,
        end_page=end
    )