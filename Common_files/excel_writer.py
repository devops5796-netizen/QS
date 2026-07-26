import pandas as pd
import json
import ast


def extract_sheet_name(category_path) -> str:
    if isinstance(category_path, str):
        try:
            category_path = json.loads(category_path)
        except (json.JSONDecodeError, TypeError):
            try:
                category_path = ast.literal_eval(category_path)
            except Exception:
                return "Other"

    if not isinstance(category_path, list) or len(category_path) == 0:
        return "Other"

    if len(category_path) == 1:
        return category_path[0].get("name", "Other")

    subcategory_name = category_path[1].get("name", "Other")

    if len(category_path) >= 3:
        sub_subcategory_name = category_path[2].get("name", "")
        return f"{subcategory_name} ({sub_subcategory_name})"

    return subcategory_name


def write(sheets: dict, output_path: str) -> None:
    if not sheets:
        print("Empty sheets, no Excel created.")
        return
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            if df is None or df.empty:
                print(f"  Skipping '{sheet_name}' — no data")
                continue
            safe = sheet_name.replace("/", "-").replace("\\", "-").replace("*", "").replace("?", "").replace(":", "-")
            df.to_excel(writer, sheet_name=safe, index=False)
            print(f"  Sheet '{safe}': {len(df)} rows")
    print(f"Excel saved: {output_path}")


def write_single(df: pd.DataFrame, sheet_name: str, output_path: str) -> None:
    write({sheet_name: df}, output_path)


def write_split_by_subcategory(df: pd.DataFrame, output_path: str, category_column: str = "categoryPath") -> None:
    if category_column not in df.columns:
        print(f"⚠️ Column '{category_column}' not found, saving as single sheet.")
        write_single(df, "All", output_path)
        return

    df = df.copy()
    df["_sheet_name"] = df[category_column].apply(extract_sheet_name)

    sheets = {}
    for sheet_name, group_df in df.groupby("_sheet_name"):
        group_df = group_df.drop(columns=["_sheet_name"])
        sheets[sheet_name] = group_df

    write(sheets, output_path)