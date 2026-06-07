import asyncio
import time
import links_scraper
import products_scraper
import flatten
import image_downloader
import analyze_data

# ============================================================
# CONFIG
# ============================================================
LISTING_URL        = "https://qatarsale.com/ar/products/cars_for_sale"
START_PAGE         = 1
END_PAGE           = 1
IMAGES_FOLDER      = "images"
LINKS_CSV          = "all_car_links.csv"
PRODUCTS_CSV       = "all_products.csv"
PRODUCTS_FLAT_CSV  = "all_products_flat.csv"
PRODUCTS_FINAL_CSV = "all_products_final.csv"
# ============================================================

async def main():
    start = time.time()
    summary = {}

    print("QatarSale Scraper - Full Pipeline")
    print(f"URL: {LISTING_URL} | Pages: {START_PAGE} to {END_PAGE}")

    summary["links"]    = links_scraper.run(LISTING_URL, START_PAGE, END_PAGE, LINKS_CSV)
    summary["products"] = await products_scraper.run(LINKS_CSV, PRODUCTS_CSV)
    summary["flatten"]  = flatten.run(PRODUCTS_CSV, PRODUCTS_FLAT_CSV)
    summary["images"]   = image_downloader.run(PRODUCTS_FLAT_CSV, PRODUCTS_FINAL_CSV, IMAGES_FOLDER)
    analyze_data.analyze_scraped_data(PRODUCTS_CSV)

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    print(f"STEP 1 - Links:    {summary['links']['success']} pages OK | {summary['links']['failed']} failed | {summary['links']['total_links']} total links")
    print(f"STEP 2 - Products: {summary['products']['success']} scraped | {summary['products']['failed']} failed")
    print(f"STEP 3 - Flatten:  {summary['flatten']['columns']} columns")
    print(f"STEP 4 - Images:   {summary['images']['downloaded']} downloaded | {summary['images']['failed']} failed")
    print(f"Total Time: {minutes}m {seconds}s")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())