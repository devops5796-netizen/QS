import sys
import time
import links_scraper
import products_scraper
import flatten
import analyze_data
from r2_uploader import upload_final_batch_assets

from dotenv import load_dotenv
load_dotenv()

# ============================================================
# CONFIG
# ============================================================
LISTING_URL       = "https://qatarsale.com/ar/products/cars_for_sale"
START_PAGE        = 1
END_PAGE          = 10
IMAGES_FOLDER     = "images"
# ============================================================

def main():
    if len(sys.argv) == 3:
        start = int(sys.argv[1])
        end = int(sys.argv[2])
    else:
        start = START_PAGE
        end = END_PAGE

    links_csv         = f"all_car_links_{start}_{end}.csv"
    products_json     = f"all_products_{start}_{end}.jsonl"
    products_flat_csv = f"all_products_flat_{start}_{end}.csv"

    elapsed_start = time.time()
    summary = {}

    print("QatarSale Scraper - Full Pipeline")
    print(f"URL: {LISTING_URL} | Pages: {start} to {end}")

    summary["links"]    = links_scraper.run(LISTING_URL, start, end, links_csv)
    summary["products"] = products_scraper.run(links_csv, products_json, workers=4)
    summary["flatten"]  = flatten.run(products_json, products_flat_csv)
    summary["r2"]       = upload_final_batch_assets(IMAGES_FOLDER, products_flat_csv)    
    analyze_data.analyze_scraped_data(products_flat_csv)

    elapsed = time.time() - elapsed_start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    print(f"STEP 1 - Links:    {summary['links']['success']} pages OK | {summary['links']['failed']} failed | {summary['links']['total_links']} total links")
    print(f"STEP 2 - Products: {summary['products']['success']} scraped | {summary['products']['failed']} failed")
    print(f"STEP 3 - Flatten:  {summary['flatten']['columns']} columns")
    print(f"STEP 4 - R2 Upload: {summary['r2']['uploaded']} uploaded | {summary['r2']['failed']} failed")
    print(f"Total Time: {minutes}m {seconds}s")
    print("="*60)


if __name__ == "__main__":
    main()