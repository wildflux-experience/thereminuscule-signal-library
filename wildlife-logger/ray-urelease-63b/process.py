"""
Process raw CSV data into a clean signal.csv file for the Thereminuscule Dataplayer.

The generic steps are configured in parameters.json:
- load raw data from raw_path
- sort and optionally slice by a numeric column
- remove rows with missing required values
- keep and optionally rename selected columns
- save raw/raw_preprocessed.csv and signal.csv
"""

from pathlib import Path
import csv
import json


# Use paths relative to this signal folder.
folder = Path(__file__).resolve().parent

# Load processing parameters.
with open(folder / "parameters.json", encoding="utf-8") as file:
    params = json.load(file)

# Resolve input and output files.
raw_path = folder / params["raw_path"]
preprocessed_path = folder / params["preprocessed_path"]
signal_path = folder / params["signal_path"]

# Load raw CSV rows as dictionaries.
with open(raw_path, newline="", encoding="utf-8-sig") as file:
    rows = list(csv.DictReader(file))

# Sort data by time or another ordered index.
sort_column = params.get("sort_column")
if sort_column:
    rows = sorted(rows, key=lambda row: float(row[sort_column]) if row[sort_column] else float("inf"))

# Keep only the configured numeric range when range_min or range_max is set.
range_column = params.get("range_column")
range_min = params.get("range_min")
range_max = params.get("range_max")
if range_column and (range_min is not None or range_max is not None):
    filtered_rows = []
    for row in rows:
        if row[range_column] == "":
            continue

        value = float(row[range_column])
        if range_min is not None and value < range_min:
            continue
        if range_max is not None and value > range_max:
            continue

        filtered_rows.append(row)
    rows = filtered_rows

# Drop rows with missing values in important columns.
for column in params.get("required_columns", []):
    rows = [row for row in rows if row.get(column) not in ("", None)]

# Prepare output column names.
keep_columns = params["keep_columns"]
rename_columns = params.get("rename_columns", {})
output_columns = [rename_columns.get(column, column) for column in keep_columns]

# Keep only selected columns and apply optional renaming.
processed_rows = []
for row in rows:
    processed_row = {}
    for column in keep_columns:
        output_column = rename_columns.get(column, column)
        processed_row[output_column] = row.get(column, "")
    processed_rows.append(processed_row)

# Save generic preprocessed data for checking/debugging.
# with open(preprocessed_path, "w", newline="", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=output_columns)
#     writer.writeheader()
#     writer.writerows(processed_rows)

# Specific signal processing can be added here if needed.
signal_rows = processed_rows

# Save final signal file used by the Dataplayer.
with open(signal_path, "w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=output_columns)
    writer.writeheader()
    writer.writerows(signal_rows)

print(f"Saved {len(signal_rows)} rows to {signal_path.name}")
