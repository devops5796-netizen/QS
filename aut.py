import os
from datetime import datetime, timedelta, timezone
import pandas as pd
import boto3
from io import BytesIO

CF_R2_ACCESS_KEY = os.getenv('CF_R2_ACCESS_KEY_ID')
CF_R2_SECRET_KEY = os.getenv('CF_R2_SECRET_ACCESS_KEY')
CF_R2_ENDPOINT_URL = os.getenv('CF_R2_ENDPOINT_URL')
BUCKET_NAME = os.getenv('CF_R2_BUCKET_NAME', '')

# ===== Setup S3 client for Cloudflare R2 =====
s3 = boto3.client(
    "s3",
    endpoint_url=CF_R2_ENDPOINT_URL,
    aws_access_key_id=CF_R2_ACCESS_KEY,
    aws_secret_access_key=CF_R2_SECRET_KEY,
    region_name="auto"
)

def read_previous_data(category):
    
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

    date_obj = datetime.strptime(yesterday, "%Y-%m-%d")

    year = date_obj.year
    month = date_obj.month
    day = date_obj.day

    file_key = f"qatarsale/year={year}/month={month}/day={day}/{category}/excel/{category}.xlsx"
    obj = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=file_key
    )
    excel_file = BytesIO(obj["Body"].read())
    df = pd.read_excel(excel_file, sheet_name=None)

    return df

def compare_data(current_df: pd.DataFrame, previous_df: pd.DataFrame) -> Dict:
    
    current_urls = set(current_df['product_url'].tolist())
    previous_urls = set(previous_df['product_url'].tolist())
    
    new_urls = current_urls - previous_urls
    removed_urls = previous_urls - current_urls
    
    common_urls = current_urls & previous_urls
    
    previous_status = dict(zip(previous_df['product_url'], previous_df['status']))
    current_status = dict(zip(current_df['product_url'], current_df['status']))
    
    changed_links = []
    no_change_links = []
    
    for url in common_urls:
        if previous_status.get(url) != current_status.get(url):
            changed_links.append({
                "product_url": url,
                "old_status": previous_status.get(url),
                "new_status": current_status.get(url)
            })
        else:
            no_change_links.append(url)
    
    new_links_data = current_df[current_df['product_url'].isin(new_urls)].to_dict('records')
    removed_links_data = previous_df[previous_df['product_url'].isin(removed_urls)].to_dict('records')
    
    return {
        "new_links": new_links_data,
        "removed_links": removed_links_data,
        "changed_links": changed_links,
        "no_change_links": no_change_links
    }


def run(links_csv, products_json, workers=6, category=category, output_csv: str):
    print("\n" + "="*50)
    print(f"STEP 2: Scraping product pages ({workers} workers)...")
    print("="*50)

    if not os.path.exists(links_csv):
        print(f"ERROR: '{links_csv}' not found!")
        return {"success": 0, "failed": 0}
    
    current_df = pd.read_csV(links_csv)

    previous_df = read_previous_data(category)

    """comparison_results = compare_data(current_df, previous_df)

    print("\n📈 COMPARISON SUMMARY:")
    print(f"  • New links:     {len(comparison_results['new_links'])}")
    print(f"  • Removed links: {len(comparison_results['removed_links'])}")
    print(f"  • Changed links: {len(comparison_results['changed_links'])}")
    print(f"  • No change:     {len(comparison_results['no_change_links'])}")"""

    urls = pd.read_csv(links_csv)["product_url"].tolist()
    print(f"Loaded {len(urls)} URLs")

    #Extract products of yesterday
    current_df['date_parsed'] = pd.to_datetime(current_df['startDate'],format='ISO8601', utc=True)
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    mask = current_df['date_parsed'].dt.date == yesterday
    df_yesterday = current_df[mask]
    print(f"Number of products yesterday: {len(df_yesterday)}")

    df_yesterday.to_csv(output_csv, index=False, encoding="utf-8")

    return {f"Number of products yesterday: {len(df_yesterday)}"}

    

    

    