import json
import os
import pandas as pd


def run(input_json: str, output_csv: str = None):

    if not os.path.exists(input_json):
        print(f"ERROR: '{input_json}' not found!")
        return {"columns": 0, "df": pd.DataFrame()}


    rows = []

    with open(input_json, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass


    if not rows:
        print("ERROR: No data found in file!")
        return {"columns": 0, "df": pd.DataFrame()}


    # keep original columns
    df = pd.DataFrame(rows)


    # flatten specs and keep original specs column
    if "specs" in df.columns:

        specs_flat = pd.json_normalize(
            df["specs"].apply(
                lambda x: x if isinstance(x, dict) else {}
            )
        )

        specs_flat.columns = [
            f"specs_{col}" for col in specs_flat.columns
        ]

        df = pd.concat(
            [
                df.reset_index(drop=True),
                specs_flat.reset_index(drop=True)
            ],
            axis=1
        )


    if output_csv:
        df.to_csv(
            output_csv,
            index=False,
            encoding="utf-8-sig"
        )

    print(
        f"STEP 3 DONE: {len(df)} rows, {len(df.columns)} columns"
    )

    return {
        "columns": len(df.columns),
        "df": df
    }