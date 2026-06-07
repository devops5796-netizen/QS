import json
import pandas as pd

def run(input_csv: str, output_csv: str):
    print("\n" + "="*50)
    print("STEP 3: Flattening specifications JSON...")
    print("="*50)

    df = pd.read_csv(input_csv)
    specs_expanded = pd.json_normalize(
        df["specifications_json"].apply(
            lambda x: json.loads(x) if pd.notna(x) and x != "" else {}
        )
    )
    df = pd.concat([df, specs_expanded], axis=1)
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"STEP 3 DONE: Saved to '{output_csv}' with {len(df.columns)} columns")
    
    return {
        "columns": len(df.columns)
    }