import os
import pandas as pd


def analyze_scraped_data(csv_file: str = "all_products.csv"):

    # Check if the file exists before reading
    if not os.path.exists(csv_file):
        print(
            f"❌ Error: '{csv_file}' not found in the current directory! Please make sure the data scraper has generated it."
        )
        return

    # Load the CSV file
    df = pd.read_csv(csv_file)

    total_rows = len(df)

    print("\n" + "=" * 60)
    print("📊 SCRAPED DATA QUALITY SUMMARY REPORT")
    print("=" * 60)
    print(f"📈 Total Rows (Products) Processed: {total_rows}")
    print("=" * 60)

    # Dictionary to store formatting or information
    report_data = []

    # Loop through each column to calculate missing values
    for column in df.columns:
        # Count rows where data is completely missing (NaN or None)
        missing_count = df[column].isna().sum()

        # Count rows where data might be an empty string '' (common in web scraping)
        empty_str_count = (df[column] == "").sum()

        # Total actual empty cells
        total_empty = missing_count + empty_str_count

        # Calculate percentage
        missing_percentage = (total_empty / total_rows) * 100

        report_data.append(
            {
                "Column Name": column,
                "Empty Cells Count": total_empty,
                "Missing Percentage": f"{missing_percentage:.2f}%",
            }
        )

    # Convert to DataFrame just for beautiful tabular printing
    report_df = pd.DataFrame(report_data)
    print(report_df.to_string(index=False))

    print("=" * 60)
    print("💡 Note: 0.00% means the column is perfect with NO empty data.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    analyze_scraped_data()