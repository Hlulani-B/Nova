import io
import pandas as pd
import numpy as np

def generate_csv_overview(csv_data: str) -> str:
    """
    Takes raw CSV string data, lists all unique data types found across each column,
    identifies missing value row indices, and returns a comprehensive overview sentence.
    """
    try:
        # Load CSV data from string buffer
        df = pd.read_csv(io.StringIO(csv_data))
    except Exception as e:
        return f"Error parsing CSV data: {e}"

    row_count, col_count = df.shape
    columns = df.columns.tolist()

    col_details = []
    missing_summary = []

    for col in columns:
        # 1. Collect all unique data types present in this specific column
        column_types = set()
        for val in df[col]:
            if pd.isna(val):
                column_types.add("None/NaN")
            else:
                column_types.add(type(val).__name__)
        
        types_str = ", ".join(sorted(column_types))
        col_details.append(f"'{col}' [types: {types_str}]")

        # 2. Find row indices where missing values exist (1-based row numbers)
        missing_indices = df.index[df[col].isna()].tolist()
        if missing_indices:
            row_nums = [idx + 1 for idx in missing_indices]
            missing_summary.append(f"Column '{col}' has missing values at row(s) {row_nums}")

    # 3. Compile useful info
    columns_str = "; ".join(col_details)
    missing_str = " | ".join(missing_summary) if missing_summary else "No missing values found across any columns."
    duplicate_count = df.duplicated().sum()

    # 4. Construct the final overview sentence
    overview_sentence = (
        f"The dataset contains {row_count} rows and {col_count} columns [{columns_str}]. "
        f"Data quality insights: {missing_str}. "
        f"Additional info: Found {duplicate_count} duplicate rows."
    )

    return overview_sentence