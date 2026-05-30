"""
Make simple plots and a small report from signal.csv.

The script is generic:
- load paths and columns from parameters.json
- load signal.csv
- plot numeric columns against the time/index column
- save HTML files in assets/
"""

from pathlib import Path
import json

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


# Style options.
font = "Consolas, monospace"

# >>> Common Plotly palettes:
# palette = px.colors.qualitative.Plotly   # generic
# palette = px.colors.qualitative.Vivid    # color
# palette = px.colors.qualitative.G10           # muted professional
# >>> More Plotly sequential palettes:
# palette = px.colors.sequential.Turbo
# palette = px.colors.sequential.Plasma
# palette = px.colors.sequential.Viridis

# Note : Apply [::-1] to revert color palette

palette = px.colors.sequential.Viridis #  [::-1]

# Use one color for all plots, or None to use the palette.
# line_color = None
# marker_color = None

line_color = "#000000"
marker_color = "#000000"

# Use paths relative to this signal folder.
root = Path(__file__).resolve().parent
name = root.name
assets = root / "assets"
assets.mkdir(exist_ok=True)

# Load parameters and signal data.
with open(root / "parameters.json", encoding="utf-8") as file:
    p = json.load(file)

df = pd.read_csv(root / p["signal_path"])

# Choose the x column.
xcol = p.get("range_column")
if xcol not in df.columns:
    xcol = df.columns[0]

# Keep only numeric columns for plotting.
for col in df.columns:
    if col != xcol:
        try:
            df[col] = pd.to_numeric(df[col])
        except ValueError:
            pass

ycols = []
for col in df.columns:
    if col != xcol and pd.api.types.is_numeric_dtype(df[col]):
        ycols.append(col)

# Make one stacked line plot.
if ycols:
    fig = make_subplots(rows=len(ycols), cols=1, shared_xaxes=True, subplot_titles=ycols)

    for i, col in enumerate(ycols, start=1):
        color = palette[(i - 1) % len(palette)]
        line = line_color or color
        marker = marker_color or color
        fig.add_trace(go.Scatter(x=df[xcol], y=df[col], mode="lines", name=col, line={"color": line}), row=i, col=1)
        fig.add_trace(
            go.Scatter(
                x=df[xcol],
                y=df[col],
                mode="markers",
                name=f"{col} points",
                marker={"color": marker},
                visible="legendonly",
            ),
            row=i,
            col=1,
        )

    fig.update_layout(height=max(400, 400 * len(ycols)), title=f"{name} | Data", font={"family": font})
else:
    fig = go.Figure()
    fig.update_layout(title=f"{name}: no numeric columns found", font={"family": font})

fig.write_html(assets / "plot.html")

# Make a short HTML report.
stats = df[ycols].describe().to_html() if ycols else "<p>No numeric columns found.</p>"

html = f"""
<html>
<head>
<title>{name}</title>
<style>
body {{ font-family: {font}; margin: 32px; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid #ccc; padding: 4px 8px; }}
</style>
</head>
<body>
<h1>{name}</h1>
<p><b>Rows:</b> {len(df)}</p>
<p><b>X column:</b> {xcol}</p>
<p><b>Y columns:</b> {", ".join(ycols)}</p>
{stats}
</body>
</html>
"""

with open(assets / "report.html", "w", encoding="utf-8") as file:
    file.write(html)

print("Saved assets/plot.html and assets/report.html")
