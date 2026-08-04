import ast
import json
from datetime import datetime, timedelta

import pandas as pd


def parse_category_path(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            try:
                parsed = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                return []
        return parsed if isinstance(parsed, list) else []
    return []


def build_category_summary(df: pd.DataFrame, dt: datetime, name_key: str = "name", level: int = 1) -> dict:
    """
    level=1 (default): groups by categoryPath[1] (subcategory), collects
    categoryPath[2] names into `subcategories` -- for sources with a
    top-level + subcategory + sub-subcategory tree (Jobs/Users/cars_for_sale,
    Sub Categories, Sub Sub Categories).

    level=0: groups by categoryPath[0] (the category itself) -- for flat
    single-level sources with no subcategory tree (Categories workflow, e.g.
    cars_for_rent). `subcategories` stays empty in this mode since there's
    no deeper level to collect.

    name_key: the dict key holding the display name inside each
    categoryPath entry. "name" for QatarSale (default). QatarSale has no
    separate Arabic name field, so name_ar stays empty here.
    """
    groups: dict[str, dict] = {}

    for _, row in df.iterrows():
        cat_path = parse_category_path(row.get("categoryPath"))

        if len(cat_path) <= level or not isinstance(cat_path[level], dict):
            key = "uncategorized"
            name_en = "Uncategorized"
            slug = "uncategorized"
            sub_name = None
        else:
            cat_main = cat_path[level]
            slug = cat_main.get("uri") or cat_main.get("slug") or "uncategorized"
            name_en = cat_main.get(name_key) or "Uncategorized"
            key = slug
            cat_sub = cat_path[level + 1] if len(cat_path) > level + 1 and isinstance(cat_path[level + 1], dict) else None
            sub_name = cat_sub.get(name_key) if cat_sub else None

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
        "data_scraped_date": (dt - timedelta(days=2)).strftime("%Y-%m-%d"),
        "saved_to_R2_date": dt.strftime("%Y-%m-%d"),
        "total_subcategories": len(subcategories),
        "total_listings": int(len(df)),
        "subcategories": subcategories,
    }