import requests

API_URL = "https://production-api.qatarsale.com/api/v2/Products"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://qatarsale.com/",
    "Origin": "https://qatarsale.com",
}


def analyze_category_with_products(url: str):
    path = url.replace("https://qatarsale.com", "").replace("https://www.qatarsale.com", "")

    payload = {
        "url": path,
        "includeFavs": False,
        "pageSize": 36
    }

    try:
        response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"  [ERROR] analyze_category_with_products: {e}")
        return 0, False

    if "code" in data and data.get("code") == 404:
        print(f"  ⚠️ Category not found (404): {data.get('description', '')}")
        return 0, False

    if "list" not in data:
        print(f"  ⚠️ Unexpected response shape: {list(data.keys())}")
        return 0, False

    total_count = data.get("totalCount", 0)
    pages_count = data.get("pagesCount", 0)

    if total_count == 0 or not data.get("list"):
        return 0, False

    return pages_count, True