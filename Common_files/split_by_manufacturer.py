import pandas as pd
import re
from pathlib import Path


INVALID_CHARS = re.compile(r'[\\/*?:\[\]]')

def clean_name(name: str, max_len: int = 31) -> str:
    return INVALID_CHARS.sub('_', str(name))[:max_len]


def write_manufacturer_excel(manufacturer: str, df_mfr: pd.DataFrame, output_dir: Path):
    filepath = output_dir / f"{clean_name(manufacturer)}.xlsx"

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:

        # Sheet
        for model in sorted(df_mfr["Class"].unique(), key=str):
            df_model = df_mfr[df_mfr["Class"] == model].reset_index(drop=True)
            sheet_name = clean_name(str(model))
            df_model.to_excel(writer, sheet_name=sheet_name, index=False)

    return filepath

def run(input_csv: str = "cars_for_sale.csv", output_dir: str = "excel_by_manufacturer"):
    print(f"Reading {input_csv}...")
    df = pd.read_excel(input_csv)
    print(f"Total rows: {len(df)}")

    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    df["Make"] = df["Make"].fillna("NA")
    df["Class"]  = df["Class"].fillna("NA")

    manufacturers = df["Make"].unique()
    print(f"Found {len(manufacturers)} manufacturers\n")

    results = []
    for mfr in sorted(manufacturers, key=str):
        df_mfr = df[df["Make"] == mfr].copy()
        filepath = write_manufacturer_excel(str(mfr), df_mfr, out)
        n_models = df_mfr["Class"].nunique()
        print(f"  ✓ {mfr}: {len(df_mfr)} rows | {n_models} models → {filepath.name}")
        results.append({"manufacturer": mfr, "rows": len(df_mfr), "models": n_models, "file": filepath.name})

    print(f"Done. {len(manufacturers)} Excel files in '{output_dir}/'")

if __name__ == "__main__":
    import sys
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "cars_for_sale.csv"
    out_path  = sys.argv[2] if len(sys.argv) > 2 else "excel_by_manufacturer"
    run(csv_path, out_path)