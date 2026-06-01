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
import ast
import csv
from glob import has_magic
import json
import pandas as pd


# Use paths relative to this signal folder.
folder = Path(__file__).resolve().parent

# Load processing parameters.
with open(folder / "parameters.json", encoding="utf-8") as file:
    params = json.load(file)

# Resolve input and output files.
raw_path_pattern = params["raw_path"]
if has_magic(raw_path_pattern):
    raw_paths = sorted(folder.glob(raw_path_pattern))
else:
    raw_paths = [folder / raw_path_pattern]

if not raw_paths:
    raise FileNotFoundError(f"No raw files matched: {raw_path_pattern}")

preprocessed_path = folder / params["preprocessed_path"]
signal_path = folder / params["signal_path"]

# Load raw CSV rows as dictionaries.
rows = []
for raw_path in raw_paths:
    with open(raw_path, newline="", encoding="utf-8-sig") as file:
        rows.extend(csv.DictReader(file))

df = pd.DataFrame(rows).replace("", pd.NA)

# Keep only rows matching configured exact-value filters.
for column, expected_value in params.get("row_filters", {}).items():
    df = df[df[column] == str(expected_value)]

# Sort data by time or another ordered index.
sort_column = params.get("sort_column")
if sort_column:
    sort_values = pd.to_numeric(df[sort_column], errors="coerce")
    if sort_values.isna().all():
        sort_values = pd.to_datetime(df[sort_column], utc=True, errors="coerce")
    df = df.assign(_sort_value=sort_values).sort_values("_sort_value").drop(columns="_sort_value")

# Keep only the configured numeric range when range_min or range_max is set.
range_column = params.get("range_column")
range_min = params.get("range_min")
range_max = params.get("range_max")
if range_column and (range_min is not None or range_max is not None):
    range_values = pd.to_numeric(df[range_column], errors="coerce")
    range_min_value = pd.to_numeric(pd.Series([range_min]), errors="coerce").iloc[0] if range_min is not None else None
    range_max_value = pd.to_numeric(pd.Series([range_max]), errors="coerce").iloc[0] if range_max is not None else None

    if range_values.isna().all():
        range_values = pd.to_datetime(df[range_column], utc=True, errors="coerce")
        range_min_value = pd.to_datetime(range_min, utc=True) if range_min is not None else None
        range_max_value = pd.to_datetime(range_max, utc=True) if range_max is not None else None

    if range_min_value is not None:
        df = df[range_values >= range_min_value]
    if range_max_value is not None:
        df = df[range_values <= range_max_value]

# Drop rows with missing values in important columns.
df = df.dropna(subset=params.get("required_columns", []))

# Prepare output column names.
keep_columns = list(dict.fromkeys(params["keep_columns"] + ["profile_tstep_s"] + ["is_consecutive"]))
rename_columns = params.get("rename_columns", {})
output_columns = list(dict.fromkeys(rename_columns.get(column, column) for column in keep_columns))

# Keep only selected columns and apply optional renaming.
df = df[keep_columns].rename(columns=rename_columns)

# Save generic preprocessed data for checking/debugging.
df.to_csv(preprocessed_path, index=False)

# Specific signal processing can be added here if needed.
def smooth(series, window=5, method="mean"):
    if method == "median":
        return series.rolling(window, center=True, min_periods=1).median()
    return series.rolling(window, center=True, min_periods=1).mean()

##### Unfold high-res profile data
# Objective : The real profile data are strored in raw file as litteral string that reflect a python list definition (ex: [1.1, 1.2, 1.4, 1.2, 1.2, 1.2, 1.1, 0.7, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
#             In each rows, each records in the profile_m list is spaced by profile_tstep_s, the timestamps in the time columns correspond to the end of a profile.
# Step1 : par each row to convert profile_m string to list
# Step2 : rebuild a new data containing an unfolded version of profile data with columns : "time", "depth" but keep track of the original index (which should be the same for each profile record in a original row)
# Step 3 : Use index tracking to populate unfolded dive dataframe with all col value found in the initial dataframe (before processing), like temperature, avg/max depth, ...

profile_df = df.reset_index(drop=True).copy()
unfolded_rows = []

for source_index, row in profile_df.iterrows():
    if pd.isna(row["dive-depth"]):
        continue

    depths = ast.literal_eval(row["dive-depth"])
    end_time = pd.to_datetime(row["time"], utc=True)
    tstep_s = float(row["profile_tstep_s"])
    dive_duration_s = float(row["dive-duration"])
    if tstep_s > 0:
        sample_count = min(len(depths), max(1, int(dive_duration_s // tstep_s) + 1))
    else:
        sample_count = len(depths)
    depths = depths[:sample_count]
    start_time = end_time - pd.to_timedelta(dive_duration_s, unit="s")

    for sample_index, depth in enumerate(depths):
        if sample_count == 1:
            sample_time = end_time
        else:
            sample_time = start_time + pd.to_timedelta(
                sample_index * dive_duration_s / (sample_count - 1),
                unit="s",
            )
        unfolded_rows.append({
            "_source_index": source_index,
            "time": sample_time,
            "dive-depth": float(depth),
        })

    unfolded_rows.append({
        "_source_index": source_index,
        "time": end_time + pd.to_timedelta(2, unit="s"),
        "dive-depth": 0.0,
    })

df = pd.DataFrame(unfolded_rows)
metadata_columns = [column for column in output_columns if column not in ("time", "dive-depth")]
df = df.join(profile_df[metadata_columns], on="_source_index")
df = df[output_columns].sort_values("time")


# Save final signal file used by the Dataplayer.
df = df[output_columns]

#### Drop some col at the end
df = df.drop('profile_tstep_s', axis=1)
df = df.drop('is_consecutive', axis=1)

df.to_csv(signal_path, index=False)

print(f"Saved {len(df)} rows to {signal_path.name}")
