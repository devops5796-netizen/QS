import pandas as pd
import json
import ast
import re

INVALID_CHARS = r'[\\/*?:\[\]]'

def clean_name(name):
    return re.sub(INVALID_CHARS, "-", str(name))[:31]


def parse_category_path(category_path):
    if isinstance(category_path, str):
        try:
            return json.loads(category_path)
        except Exception:
            try:
                return ast.literal_eval(category_path)
            except Exception:
                return []
    return category_path if isinstance(category_path, list) else []


def get_last_name(category_path):
    """Name of the deepest element in the path."""
    path = parse_category_path(category_path)
    if len(path) >= 1:
        return path[-1].get("name", "Other")
    return "Other"


def get_last_uri(category_path):
    path = parse_category_path(category_path)
    if len(path) >= 1:
        return path[-1].get("uri", "other")
    return "other"


def get_main_uri(category_path):
    """URI of the top-level (index=0) element."""
    path = parse_category_path(category_path)
    if len(path) >= 1:
        return path[0].get("uri", "other")
    return "other"


def get_subcategory_file_uri(category_path):
    """
    For depth>=2 paths, returns the level-1 (index=1) uri with the
    top-level uri prefix stripped:
    "home_appliances-kitchen_appliances" -> "kitchen_appliances"
    "home_appliances-vacuums" -> "vacuums"
    """
    path = parse_category_path(category_path)
    if len(path) < 2:
        return get_main_uri(category_path)
    top_uri = path[0].get("uri", "")
    sub_uri = path[1].get("uri", "other")
    prefix = f"{top_uri}-"
    return sub_uri[len(prefix):] if sub_uri.startswith(prefix) else sub_uri


def flatten_specs(df):
    if "specs" not in df.columns:
        return df
    specs = pd.json_normalize(
        df["specs"].apply(lambda x: x if isinstance(x, dict) else {})
    )
    specs.columns = [f"specs_{c}" for c in specs.columns]
    return pd.concat([df.reset_index(drop=True), specs.reset_index(drop=True)], axis=1)


def write_excel_sheets(sheets, output_path):
    if not sheets:
        print(f"⚠️ No sheets to write to {output_path}")
        return

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet, df in sheets.items():
            if df.empty:
                continue
            df = flatten_specs(df)
            df.to_excel(writer, sheet_name=clean_name(sheet), index=False)
            print(f"  Sheet '{sheet}': {len(df)} rows")
    print(f"✅ Saved {output_path}")


def _write_grouped(df, category_column, file_uri_fn):
    df = df.copy()
    df["_file_uri"] = df[category_column].apply(file_uri_fn)
    df["_sheet_name"] = df[category_column].apply(get_last_name)

    for file_uri, group in df.groupby("_file_uri"):
        sheets = {
            name: sheet_df.drop(columns=["_depth", "_file_uri", "_sheet_name"])
            for name, sheet_df in group.groupby("_sheet_name")
        }
        write_excel_sheets(sheets, f"{clean_name(file_uri)}.xlsx")


def write_split_by_subcategory(df, output_path, category_column="categoryPath"):
    """
    Decision is based on the DEEPEST categoryPath found anywhere in this
    scraped category (not per-row), since one scraper run always covers a
    single top-level category:

    - max depth == 1 (simple category, e.g. glasses):
        one file named after the leaf uri, one sheet named after the leaf name.
        glasses.xlsx (sheet: Glasses)

    - max depth == 2 everywhere (sub category, no sub-subcategories anywhere,
      e.g. computers_and_parts):
        one file named after the top-level uri, one sheet per subcategory.
        computers_and_parts.xlsx (sheets: Laptops, Printers, ...)

    - max depth >= 3 present anywhere (sub category WITH sub-subcategories
      somewhere, e.g. home_appliances): every subcategory gets its own file
      (named after itself, prefix stripped), whether or not that particular
      subcategory has sub-subcategories. Sheet = leaf category name.
        kitchen_appliances.xlsx (sheet: Freezers)
        vacuums.xlsx (sheet: Vacuums)
    """
    if category_column not in df.columns:
        write_excel_sheets({"All": df}, output_path)
        return

    df = df.copy()
    df["_depth"] = df[category_column].apply(lambda x: len(parse_category_path(x)))
    valid = df[df["_depth"] >= 1]

    if valid.empty:
        write_excel_sheets({"All": df.drop(columns=["_depth"])}, output_path)
        return

    max_depth = valid["_depth"].max()

    # Simple category: depth == 1 only
    if max_depth <= 1:
        depth1 = valid[valid["_depth"] == 1].copy()
        depth1["_sheet_name"] = depth1[category_column].apply(get_last_name)
        file_uri = depth1[category_column].apply(get_last_uri).iloc[0]
        sheets = {
            name: group.drop(columns=["_depth", "_sheet_name"])
            for name, group in depth1.groupby("_sheet_name")
        }
        write_excel_sheets(sheets, f"{clean_name(file_uri)}.xlsx")
        return

    # Sub category only: depth == 2 everywhere, no sub-subcategories at all
    if max_depth == 2:
        depth2 = valid[valid["_depth"] == 2]
        _write_grouped(depth2, category_column, get_main_uri)
        return

    # Sub category + sub-subcategory mix: depth >= 3 present somewhere.
    # Every subcategory (depth2 or depth3+) becomes its own file.
    mixed = valid[valid["_depth"] >= 2]
    _write_grouped(mixed, category_column, get_subcategory_file_uri)

    # Edge case: stray depth1 rows inside an otherwise-mixed category --
    # file them under the top-level uri so they aren't silently dropped.
    depth1_stray = valid[valid["_depth"] == 1]
    if not depth1_stray.empty:
        _write_grouped(depth1_stray, category_column, get_main_uri)