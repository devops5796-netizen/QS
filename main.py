import sys
import time
import links_scraper
import products_scraper
import flatten
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv()

LISTING_URL   = "https://qatarsale.com/ar/products/cars_for_sale?basic_search:StatusFilter=0"
START_PAGE    = 1
END_PAGE      = 10

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


def main():
    if len(sys.argv) == 3:
        start = int(sys.argv[1])
        end   = int(sys.argv[2])
    else:
        start = START_PAGE
        end   = END_PAGE

    links_csv         = f"all_car_links_{start}_{end}.csv"
    filtered_csv      = f"all_car_links_yesterday_{start}_{end}.csv"
    products_json     = f"all_products_{start}_{end}.jsonl"
    products_flat_csv = f"all_products_flat_{start}_{end}.csv"
    category          = "cars_for_sale"

    elapsed_start = time.time()
    summary = {}

    print("QatarSale Scraper - Full Pipeline")
    print(f"URL: {LISTING_URL} | Pages: {start} to {end}")

    summary["links"]    = links_scraper.run(LISTING_URL, start, end, links_csv)

    print("\n" + "="*50)
    print("STEP 1.5: Filtering yesterday's links...")
    print("="*50)
    
    summary["filter"]   = filter_yesterday_links(links_csv, filtered_csv)
    
    if summary["filter"]["yesterday"] == 0:
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
        print(f"STEP 1   - Links:    {summary['links']['success']} pages OK | {summary['links']['failed']} failed | {summary['links']['total_links']} total")
        print(f"STEP 1.5 - Filter:   0 yesterday / {summary['filter']['total']} total")
        print("STEP 2   - Products: Skipped")
        print("STEP 3   - Flatten:  Skipped")
        print(f"Total Time: {minutes}m {seconds}s")
        print("="*60)

        return
    
    summary["products"] = products_scraper.run(filtered_csv, products_json, workers=6, category=category)
    summary["flatten"]  = flatten.run(products_json, products_flat_csv)

    elapsed = time.time() - elapsed_start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    print(f"STEP 1 - Links:    {summary['links']['success']} pages OK | {summary['links']['failed']} failed | {summary['links']['total_links']} total links")
    print(f"STEP 1.5 - Filter:   {summary['filter']['yesterday']} yesterday / {summary['filter']['total']} total")
    print(f"STEP 2   - Products: {summary['products']['success']} scraped | {summary['products']['failed']} failed")
    print(f"STEP 3   - Flatten:  {summary['flatten']['columns']} columns")
    print(f"Total Time: {minutes}m {seconds}s")
    print("="*60)

if __name__ == "__main__":
    main()