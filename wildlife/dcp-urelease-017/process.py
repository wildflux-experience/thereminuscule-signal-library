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
from datetime import datetime
from glob import has_magic
import json
import numpy as np
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


def parse_range_value(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

# Load raw CSV rows as dictionaries.
rows = []
for raw_path in raw_paths:
    with open(raw_path, newline="", encoding="utf-8-sig") as file:
        rows.extend(csv.DictReader(file))

# Keep only rows matching configured exact-value filters.
for column, expected_value in params.get("row_filters", {}).items():
    rows = [row for row in rows if row.get(column) == str(expected_value)]

# Sort data by time or another ordered index.
sort_column = params.get("sort_column")
if sort_column:
    rows = sorted(rows, key=lambda row: row[sort_column] if row[sort_column] else "9999")

# Keep only the configured numeric range when range_min or range_max is set.
range_column = params.get("range_column")
range_min = params.get("range_min")
range_max = params.get("range_max")
if range_column and (range_min is not None or range_max is not None):
    range_min = parse_range_value(range_min) if range_min is not None else None
    range_max = parse_range_value(range_max) if range_max is not None else None

    filtered_rows = []
    for row in rows:
        if row[range_column] == "":
            continue

        value = parse_range_value(row[range_column])
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
keep_columns = params["keep_columns"] + ["ehpe"]
rename_columns = params.get("rename_columns", {})
output_columns = [rename_columns.get(column, column) for column in keep_columns]

print("Keeping output cols :", output_columns)

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

# >>> Specific signal processing can be added here if needed.

# signal_rows = processed_rows # <-- default: doing nothing

###### Merge GPS and sensor data
# Step 1 : create an interpolator from a subset where we keep only _time, latitude, longitude and drop all empty rows
# Step 2 : Create a data subset where we have only _time, press , temp data
# Step 3 : create new columns for this subset nammed latitude and longitude where value are interpolated based on the _time columns

# Save final signal file used by the Dataplayer (Pandas version)
df = pd.DataFrame(processed_rows).replace("", np.nan)
print("DEBUG df.cols = ", df.columns)

df["time"] = pd.to_datetime(df["time"], utc=True)

gps_df = df[["time", "latitude", "longitude","ehpe"]].dropna().sort_values("time")
gps_df["latitude"] = pd.to_numeric(gps_df["latitude"])
gps_df["longitude"] = pd.to_numeric(gps_df["longitude"])
gps_df["ehpe"] = pd.to_numeric(gps_df["ehpe"])
gps_df = gps_df[gps_df.latitude != 0]
gps_df = gps_df[gps_df.longitude != 0]
gps_df = gps_df[gps_df.ehpe > 0]
gps_df = gps_df[gps_df.ehpe <= 40]

sensor_columns = [column for column in output_columns if column not in ("latitude", "longitude")]
signal_df = df[sensor_columns].dropna(
    subset=["time", "atmospheric-pressure", "atmospheric-temperature"]
).sort_values("time")
signal_df["atmospheric-pressure"] = pd.to_numeric(signal_df["atmospheric-pressure"])
signal_df["atmospheric-temperature"] = pd.to_numeric(signal_df["atmospheric-temperature"])

if gps_df.empty:
    raise ValueError("No GPS rows available for latitude/longitude interpolation")
if signal_df.empty:
    raise ValueError("No sensor rows available for signal processing")

gps_time = gps_df["time"].astype("int64")
signal_time = signal_df["time"].astype("int64")

signal_df["latitude"] = np.interp(signal_time, gps_time, gps_df["latitude"])
signal_df["longitude"] = np.interp(signal_time, gps_time, gps_df["longitude"])
signal_df = signal_df[output_columns]

###### Apply smooth filter to temperature and pressure data
# Step 1 : Define smoothing filter function as local func with ap parameters to choose the filter form
# Step 2 : Apply it to temp and press cols

def smooth(series, window=5, method="mean"):
    if method == "median":
        return series.rolling(window, center=True, min_periods=1).median()
    return series.rolling(window, center=True, min_periods=1).mean()


signal_df["atmospheric-pressure"] = smooth(signal_df["atmospheric-pressure"], window=5)
signal_df["atmospheric-temperature"] = smooth(signal_df["atmospheric-temperature"], window=5)

##### Compute metric on speed and sisplacement
# Step 1 : from GPS col calculate average lat,lon and compute the relative instant displacement in meter from this point (haversine ?)
# Step 2 : Compute the Speed m/s from GPS columns (here apply a avg/smoothing filter to)

def haversine_m(lat1, lon1, lat2, lon2):
    radius_m = 6371000
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * radius_m * np.arcsin(np.sqrt(a))


center_lat = signal_df["latitude"].mean()
center_lon = signal_df["longitude"].mean()
signal_df["mean-displacement"] = haversine_m(
    center_lat,
    center_lon,
    signal_df["latitude"],
    signal_df["longitude"],
)

distance_m = haversine_m(
    signal_df["latitude"].shift(),
    signal_df["longitude"].shift(),
    signal_df["latitude"],
    signal_df["longitude"],
)
dt_s = signal_df["time"].diff().dt.total_seconds()
signal_df["speed"] = distance_m / dt_s
signal_df["speed"] = signal_df["speed"].replace([np.inf, -np.inf], np.nan).fillna(0)
signal_df["speed"] = smooth(signal_df["speed"], window=5)

#### Drop some col at the end
signal_df = signal_df.drop('ehpe', axis=1)


# Save final signal file used by the Dataplayer (Pandas version)
signal_df.to_csv(signal_path, index=False)
print(f"Saved {len(signal_df)} rows to {signal_path.name}")

# Save final signal file used by the Dataplayer (Dict version)
# with open(signal_path, "w", newline="", encoding="utf-8") as file:
#     writer = csv.DictWriter(file, fieldnames=output_columns)
#     writer.writeheader()
#     writer.writerows(signal_rows)

# print(f"Saved {len(signal_rows)} rows to {signal_path.name}")
