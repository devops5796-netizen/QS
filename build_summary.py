import ast
import json
from datetime import datetime, timedelta

import pandas as pd


def parse_category_path(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, SyntaxError):
            return []
    return []


def build_category_summary(df: pd.DataFrame, dt: datetime) -> dict:
    """
    Groups by categoryPath[1] (the level-1 subcategory). categoryPath[2]
    (level 2, when present) is collected into `subcategories`, deduped,
    insertion order preserved -- same shape as the DKSA summary.json.
    QatarSale's API doesn't provide an Arabic category name, so name_ar
    stays empty.
    """
    groups: dict[str, dict] = {}

    for _, row in df.iterrows():
        cat_path = parse_category_path(row.get("categoryPath"))

        if len(cat_path) < 2 or not isinstance(cat_path[1], dict):
            key = "uncategorized"
            name_en = "Uncategorized"
            slug = "uncategorized"
            sub_name = None
        else:
            cat1 = cat_path[1]
            slug = cat1.get("uri") or "uncategorized"
            name_en = cat1.get("name") or "Uncategorized"
            key = slug
            cat2 = cat_path[2] if len(cat_path) > 2 and isinstance(cat_path[2], dict) else None
            sub_name = cat2.get("name") if cat2 else None

        group = groups.setdefault(key, {
            "name_ar": "",
            "name_en": name_en,
            "slug": slug,
            "listings_count": 0,
            "_sub_seen": set(),
            "subcategories": [],
        })
        group["listings_count"] += 1
        if sub_name and sub_name not in group["_sub_seen"]:
            group["_sub_seen"].add(sub_name)
            group["subcategories"].append(sub_name)

    subcategories = [
        {
            "name_ar": g["name_ar"],
            "name_en": g["name_en"],
            "slug": g["slug"],
            "listings_count": g["listings_count"],
            "has_subcategories": bool(g["subcategories"]),
            "subcategories": g["subcategories"],
        }
        for g in groups.values()
    ]

    return {
        "scraped_at": dt.isoformat(),
        "data_scraped_date": (dt - timedelta(days=1)).strftime("%Y-%m-%d"),
        "saved_to_R2_date": dt.strftime("%Y-%m-%d"),
        "total_subcategories": len(subcategories),
        "total_listings": int(len(df)),
        "subcategories": subcategories,
    }