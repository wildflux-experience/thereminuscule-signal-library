"""
Process raw CSV data into a clean signal.csv file for the Thereminuscule Dataplayer.

The generic steps are configured in parameters.json:
- load raw data from raw_path
- sort and optionally slice by a numeric column
- remove rows with missing required values
- keep and optionally rename selected columns
- save raw/raw_preprocessed.csv and signal.csv
"""

#%%

from pathlib import Path
import csv
import re
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

# Load raw data in  JPL Horizons format (long metadata header, a fixed-width data block between $$SOE and $$EOE, and values like RA/DEC split into several space-separated fields.)

HORIZONS_COLUMNS = [
    "Date__(UT)__HR:MN",
    "R.A._____(ICRF)_____DEC",
    "APmag",
    "S-brt",
    "delta",
    "deldot",
    "S-O-T /r",
    "S-T-O",
    "Sky_motion",
    "Sky_mot_PA",
    "RelVel-ANG",
    "Lun_Sky_Brt",
    "sky_SNR",
]


def clean_horizons_observer_table(raw_path, clean_path=None):
    """
    Extract the ephemeris table from a NASA/JPL Horizons text export
    and convert it to a normal CSV-like structure.

    Returns a pandas DataFrame.
    Optionally writes a cleaned CSV file if clean_path is provided.
    """

    with open(raw_path, encoding="utf-8-sig") as f:
        lines = f.readlines()

    # Keep only lines after $$SOE and before $$EOE, if present.
    in_data = False
    rows = []

    for line in lines:
        line = line.strip()

        if line == "$$SOE":
            in_data = True
            continue

        if line == "$$EOE":
            break

        if not in_data:
            continue

        if not line:
            continue

        # Keep only data rows starting with a Horizons date.
        if not re.match(r"^\d{4}-[A-Za-z]{3}-\d{2}\s+\d{2}:\d{2}", line):
            continue

        parts = line.split()

        # Example:
        # 2026-Jun-03 00:00
        # 02 34 35.09
        # +14 30 34.4
        # then numeric fields...
        date_ut = f"{parts[0]} {parts[1]}"
        ra_icrf_dec = " ".join(parts[2:8])

        remaining = parts[8:]

        row = {
            "Date__(UT)__HR:MN": date_ut,
            "R.A._____(ICRF)_____DEC": ra_icrf_dec,
            "APmag": remaining[0],
            "S-brt": remaining[1],
            "delta": remaining[2],
            "deldot": remaining[3],
            "S-O-T /r": f"{remaining[4]} {remaining[5]}",
            "S-T-O": remaining[6],
            "Sky_motion": remaining[7],
            "Sky_mot_PA": remaining[8],
            "RelVel-ANG": remaining[9],
            "Lun_Sky_Brt": remaining[10],
            "sky_SNR": remaining[11],
        }

        rows.append(row)

    df = pd.DataFrame(rows, columns=HORIZONS_COLUMNS)

    # Replace Horizons missing values.
    df = df.replace({"n.a.": pd.NA, "N.A.": pd.NA, "": pd.NA})

    # Convert numeric columns where possible.
    numeric_cols = [
        "APmag",
        "S-brt",
        "delta",
        "deldot",
        "S-T-O",
        "Sky_motion",
        "Sky_mot_PA",
        "RelVel-ANG",
        "Lun_Sky_Brt",
        "sky_SNR",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if clean_path is not None:
        df.to_csv(clean_path, index=False)

    return df

df = clean_horizons_observer_table(raw_paths[0])

#%%

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
keep_columns = params["keep_columns"]
rename_columns = params.get("rename_columns", {})
output_columns = [rename_columns.get(column, column) for column in keep_columns]

# Keep only selected columns and apply optional renaming.
df = df[keep_columns].rename(columns=rename_columns)

# Save generic preprocessed data for checking/debugging.
# df.to_csv(preprocessed_path, index=False)

# Specific signal processing can be added here if needed.
def smooth(series, window=5, method="mean"):
    if method == "median":
        return series.rolling(window, center=True, min_periods=1).median()
    return series.rolling(window, center=True, min_periods=1).mean()


# Example:
# df["atmospheric-temperature"] = smooth(df["atmospheric-temperature"].astype(float), window=5)
# df["atmospheric-pressure"] = smooth(df["atmospheric-pressure"].astype(float), window=5)

# Save final signal file used by the Dataplayer.
df = df[output_columns]
df.to_csv(signal_path, index=False)

print(f"Saved {len(df)} rows to {signal_path.name}")
