import sys
import time
import Common_files.excel_writer as excel_writer
from Common_files.detect_utils import analyze_category_with_products
from datetime import datetime, timezone, timedelta
import pandas as pd
from Common_files.request_tracker import tracker
import Common_files.links_scraper as links_scraper
import Common_files.products_scraper as products_scraper
import Common_files.flatten as flatten
from dotenv import load_dotenv
load_dotenv()


def filter_yesterday_links(links_csv: str, filtered_csv: str) -> dict:
    df = pd.read_csv(links_csv)

    if "startDate" not in df.columns:
        print("⚠️ No startDate column found, using all links")
        df.to_csv(filtered_csv, index=False, encoding="utf-8")
        return {"total": len(df), "yesterday": len(df)}

    df["date_parsed"] = pd.to_datetime(df["startDate"], format="ISO8601", utc=True)
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    mask = df["date_parsed"].dt.date == yesterday
    df_yesterday = df[mask].drop(columns=["date_parsed"])

    print(f"  Total links:     {len(df)}")
    print(f"  Yesterday links: {len(df_yesterday)}")

    df_yesterday.to_csv(filtered_csv, index=False, encoding="utf-8")
    return {"total": len(df), "yesterday": len(df_yesterday)}


def run_category_pages(category: str, category_path: str, start: int, end: int):
    links_csv     = f"links_{category}_{start}_{end}.csv"
    filtered_csv  = f"links_yesterday_{category}_{start}_{end}.csv"
    products_json = f"products_{category}_{start}_{end}.jsonl"
    output_excel  = f"{category}_{start}_{end}.xlsx"

    elapsed_start = time.time()
    print(f"QatarSale Scraper - Category: {category} | Pages: {start} to {end}")

    s1 = links_scraper.run(category_path, start, end, links_csv)
    if s1['total_links'] == 0:
        print(f"⚠️ No links found for '{category}' — skipping.")
        return None

    print("\n" + "="*50)
    print("STEP 1.5: Filtering yesterday's links...")
    print("="*50)
    s_filter = filter_yesterday_links(links_csv, filtered_csv)

    if s_filter["yesterday"] == 0:
        print("\n" + "="*60)
        print("No listings found for yesterday.")
        print("Skipping product scraping and flattening.")
        print("="*60)

        elapsed = time.time() - elapsed_start
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        print("\n" + "="*60)
        print("FINAL SUMMARY")
        print("="*60)
        print(f"STEP 1   - Links:    {s1['success']} pages OK | {s1['failed']} failed | {s1['total_links']} total")
        print(f"STEP 1.5 - Filter:   0 yesterday / {s_filter['total']} total")
        print("STEP 2   - Products: Skipped")
        print("STEP 3   - Flatten:  Skipped")
        print(f"Total Time: {minutes}m {seconds}s")
        print("="*60)
        return None

    s2 = products_scraper.run(filtered_csv, products_json, workers=2, category=category)
    if s2['success'] == 0:
        print(f"⚠️ No products scraped for '{category}' — skipping.")
        return None

    s3 = flatten.run(products_json)
    df = s3["df"]
    COLUMNS_TO_DROP = [
        "categoryId", "categoryName", "_CategoryPath", "categoryUri", "createdBy", "thumbnailImages"
    ]
    df = df.drop(columns=COLUMNS_TO_DROP)

    excel_writer.write_split_by_subcategory(df, output_excel, category_column="categoryPath")

    elapsed = time.time() - elapsed_start
    print(f"\nDONE: {s1['total_links']} links | {s2['success']} scraped | {int(elapsed//60)}m {int(elapsed%60)}s")
    stats_file = f"request_stats_{start}_{end}.json"
    stats = tracker.save(stats_file)

    print(f"\n--- Combined Request Stats ---")
    print(f"Total: {stats['total_requests']} req | {stats['total_req_per_min']} req/min")
    print(f"By source: {stats['per_source']}")
    for worker, s in stats["per_worker"].items():
        print(f"  {worker}: {s['requests']} req | {s['req_per_min']} req/min")
    
    return output_excel


def main():
    if len(sys.argv) == 5:
        category      = sys.argv[1]
        category_path = sys.argv[2]
        start         = int(sys.argv[3])
        end           = int(sys.argv[4])
        run_category_pages(category, category_path, start, end)
    else:
        print("Usage:")
        print("  python main.py <category> <category_path> <start> <end>")
        sys.exit(1)


if __name__ == "__main__":
    main()