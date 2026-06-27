import json
import os
import boto3
import pandas as pd
from datetime import datetime, timezone, timedelta
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["CF_R2_ENDPOINT_URL"],
    aws_access_key_id=os.environ["CF_R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["CF_R2_SECRET_ACCESS_KEY"],
    region_name="auto"
)
BUCKET_NAME = os.environ["CF_R2_BUCKET_NAME"]


def read_previous_data(category: str) -> pd.DataFrame:
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    year  = yesterday.year
    month = yesterday.month
    day   = yesterday.day

    file_key = f"qatarsale/year={year}/month={month}/day={day}/{category}/excel/{category}.xlsx"
    try:
        obj        = s3.get_object(Bucket=BUCKET_NAME, Key=file_key)
        excel_file = BytesIO(obj["Body"].read())
        sheets     = pd.read_excel(excel_file, sheet_name=None)
        df = pd.concat(sheets.values(), ignore_index=True)
        print(f"  Loaded {len(df)} rows from R2: {file_key}")
        return df
    except Exception as e:
        print(f"  ⚠️ Could not load previous data: {e}")
        return pd.DataFrame()


def compare_data(current_df: pd.DataFrame, previous_df: pd.DataFrame) -> dict:
    if previous_df.empty:
        print("  ⚠️ No previous data to compare")
        return {}

    current_urls  = set(current_df["product_url"].dropna().tolist())
    previous_urls = set(previous_df["product_url"].dropna().tolist())

    removed_urls = previous_urls - current_urls

    # status changes
    removed_details = []
    if not previous_df.empty and removed_urls:
        removed_rows = previous_df[previous_df["product_url"].isin(removed_urls)]
        for _, row in removed_rows.iterrows():
            removed_details.append({
                "product_url": row.get("product_url", ""),
                "title":       row.get("title", ""),
                "isSold":      row.get("isSold", None),
                "isExpired":   row.get("isExpired", None),
                "advertisedFor": row.get("advertisedFor", None),  # rent/sale
            })

    # column changes for common urls
    common_urls = current_urls & previous_urls
    changed_links = []

    WATCH_COLS = ["isSold", "isExpired", "advertisedFor"]

    if common_urls:
        current_common  = current_df[current_df["product_url"].isin(common_urls)].set_index("product_url")
        previous_common = previous_df[previous_df["product_url"].isin(common_urls)].set_index("product_url")

        for url in common_urls:
            if url not in current_common.index or url not in previous_common.index:
                continue
            changes = {}
            for col in WATCH_COLS:
                if col not in current_common.columns or col not in previous_common.columns:
                    continue
                curr_val = current_common.loc[url, col]
                prev_val = previous_common.loc[url, col]
                if curr_val != prev_val:
                    changes[col] = {"before": prev_val, "after": curr_val}
            if changes:
                changed_links.append({
                    "product_url": url,
                    "changes":     changes
                })

    result = {
        "date":                  datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_current":         len(current_urls),
        "total_previous":        len(previous_urls),
        "number_of_removed_links": len(removed_urls),
        "removed_links":         removed_details,
        "number_of_changed_links": len(changed_links),
        "changed_links":         changed_links,
    }

    return result


def run(links_csv: str, category: str, output_json: str = None) -> dict:
    print("\n" + "="*50)
    print("MONITOR: Comparing current vs previous data...")
    print("="*50)

    if not os.path.exists(links_csv):
        print(f"ERROR: '{links_csv}' not found!")
        return {}

    current_df  = pd.read_csv(links_csv)
    previous_df = read_previous_data(category)

    result = compare_data(current_df, previous_df)

    if result:
        print(f"  Removed links:  {result['number_of_removed_links']}")
        print(f"  Changed links:  {result['number_of_changed_links']}")

    if output_json is None:
        output_json = f"monitor_{category}.json"

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {output_json}")

    return result


if __name__ == "__main__":
    import sys
    category  = sys.argv[1] if len(sys.argv) > 1 else "cars_for_sale"
    links_csv = sys.argv[2] if len(sys.argv) > 2 else f"all_car_links_1_10.csv"
    run(links_csv=links_csv, category=category)