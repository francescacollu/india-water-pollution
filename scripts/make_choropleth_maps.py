"""
Static choropleth infographics of Indian state-level sewage treatment stats.

For each of three metrics in sources/india_sewage_treatment_by_state.csv, renders
a PNG with:
  - a choropleth map of India (states colored by the metric), and
  - a companion ranked bar chart (same color scale) so exact values can be
    read directly rather than guessed from color alone.

Metrics rendered:
  - actual_treated_pct_of_generation        ("how much is actually treated")
  - installed_capacity_pct_of_generation    ("nominal capacity vs. need")
  - actual_treated_pct_of_installed_capacity ("efficiency: is built capacity used")

Usage:
    python scripts/make_choropleth_maps.py

Requires: pandas, plotly, kaleido (for PNG export).
Geo source: geo/india_states.geojson (state boundaries, property "ST_NM").
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
DATA_CSV = ROOT / "sources" / "india_sewage_treatment_by_state.csv"
GEOJSON_PATH = ROOT / "geo" / "india_states.geojson"
OUTPUT_DIR = ROOT / "output"

# ---------------------------------------------------------------------------
# Design tokens (dataviz skill reference palette — light mode)
# ---------------------------------------------------------------------------

SURFACE = "#fcfcfb"
PAGE_PLANE = "#f9f9f7"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
NO_DATA_FILL = "#e1e0d9"
BORDER = "rgba(11,11,11,0.10)"

# Sequential "blue" ramp, steps 100 -> 700, light -> dark (references/palette.md)
BLUE_RAMP = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281",
    "#0d366b",
]
SEQUENTIAL_COLORSCALE = [
    [i / (len(BLUE_RAMP) - 1), hex_] for i, hex_ in enumerate(BLUE_RAMP)
]

# ---------------------------------------------------------------------------
# State name -> GeoJSON "ST_NM" mapping
#
# The CSV and the GeoJSON spell some states/UTs differently. Only names that
# differ need an entry; identical names pass through unchanged. "Total" is a
# summary row, not a state, and is dropped before mapping.
# ---------------------------------------------------------------------------

CSV_TO_GEOJSON_NAME = {
    "Andaman & Nicobar Islands": "Andaman & Nicobar",
    "Daman Diu Dadra & Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "NCT of Delhi": "Delhi",
}

METRICS = [
    {
        "column": "actual_treated_pct_of_generation",
        "title": "Sewage Actually Treated",
        "subtitle": "Share of generated sewage that is actually treated, by state",
        "colorbar_title": "% of generation<br>treated",
        "bar_axis_title": "% of sewage generation actually treated",
        "output": "map_actual_treated_pct_of_generation.png",
        "zmax_mode": "headroom",  # can exceed 100%
    },
    {
        "column": "installed_capacity_pct_of_generation",
        "title": "Treatment Capacity Installed",
        "subtitle": "Installed STP capacity as a share of sewage generated, by state",
        "colorbar_title": "% of generation<br>(capacity)",
        "bar_axis_title": "% of sewage generation covered by installed capacity",
        "output": "map_installed_capacity_pct_of_generation.png",
        "zmax_mode": "headroom",  # can exceed 100%
    },
    {
        "column": "actual_treated_pct_of_installed_capacity",
        "title": "Treatment Plant Efficiency",
        "subtitle": (
            "Sewage actually treated as a share of installed capacity "
            "— how fully existing plants are used"
        ),
        "colorbar_title": "% of installed<br>capacity used",
        "bar_axis_title": "% of installed capacity actually used",
        "output": "map_actual_treated_pct_of_installed_capacity.png",
        "zmax_mode": "fixed100",  # a utilization rate; 100% is the natural ceiling
    },
]


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_CSV)
    df = df[df["state"] != "Total"].copy()
    df["geo_name"] = df["state"].map(lambda s: CSV_TO_GEOJSON_NAME.get(s, s))
    return df


def load_geojson() -> dict:
    import json

    with open(GEOJSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def check_name_mapping(df: pd.DataFrame, geojson: dict) -> None:
    """Fail loudly if the CSV and GeoJSON state names don't line up 1:1."""
    geo_names = {f["properties"]["ST_NM"] for f in geojson["features"]}
    csv_names = set(df["geo_name"])
    unmatched = csv_names - geo_names
    if unmatched:
        raise ValueError(
            f"CSV state names with no matching GeoJSON feature: {sorted(unmatched)}"
        )


def zmax_for(df: pd.DataFrame, metric: dict) -> float:
    if metric["zmax_mode"] == "fixed100":
        return 100
    data_max = df[metric["column"]].max()
    import math

    return max(100, math.ceil(data_max / 10) * 10)


def build_figure(df: pd.DataFrame, geojson: dict, metric: dict) -> go.Figure:
    column = metric["column"]
    zmax = zmax_for(df, metric)

    fig = make_subplots(
        rows=2,
        cols=1,
        row_heights=[0.34, 0.66],
        specs=[[{"type": "geo"}], [{"type": "xy"}]],
        vertical_spacing=0.05,
    )

    # -- Base layer: every state in neutral gray, so states with no CSV match
    #    (e.g. Ladakh, split out of J&K after this data was compiled) read as
    #    "no data" rather than a hole in the map.
    all_geo_names = [f["properties"]["ST_NM"] for f in geojson["features"]]
    fig.add_trace(
        go.Choropleth(
            geojson=geojson,
            featureidkey="properties.ST_NM",
            locations=all_geo_names,
            z=[0] * len(all_geo_names),
            colorscale=[[0, NO_DATA_FILL], [1, NO_DATA_FILL]],
            showscale=False,
            marker_line_color=SURFACE,
            marker_line_width=0.6,
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )

    # -- Data layer
    fig.add_trace(
        go.Choropleth(
            geojson=geojson,
            featureidkey="properties.ST_NM",
            locations=df["geo_name"],
            z=df[column],
            zmin=0,
            zmax=zmax,
            colorscale=SEQUENTIAL_COLORSCALE,
            marker_line_color=SURFACE,
            marker_line_width=0.6,
            colorbar=dict(
                title=dict(text=metric["colorbar_title"], font=dict(size=12, color=INK_SECONDARY), side="top"),
                tickfont=dict(size=11, color=INK_MUTED),
                ticksuffix="%",
                orientation="v",
                len=0.30,
                thickness=14,
                x=0.86,
                xanchor="left",
                y=0.84,
                yanchor="middle",
            ),
            customdata=df["state"],
            hovertemplate="%{customdata}: %{z}%<extra></extra>",
        ),
        row=1,
        col=1,
    )

    fig.update_geos(
        visible=False,
        fitbounds="locations",
        bgcolor=SURFACE,
        row=1,
        col=1,
    )

    # -- Ranked bar chart panel (direct labels — avoids reading value from color alone)
    ranked = df.sort_values(column, ascending=True)
    fig.add_trace(
        go.Bar(
            x=ranked[column],
            y=ranked["state"],
            orientation="h",
            marker=dict(
                color=ranked[column],
                cmin=0,
                cmax=zmax,
                colorscale=SEQUENTIAL_COLORSCALE,
                line=dict(color=SURFACE, width=0.5),
            ),
            text=[f"{v:g}%" for v in ranked[column]],
            textposition="outside",
            textfont=dict(size=10, color=INK_SECONDARY),
            cliponaxis=False,
            hovertemplate="%{y}: %{x}%<extra></extra>",
        ),
        row=2,
        col=1,
    )

    fig.update_xaxes(
        title=dict(text=metric["bar_axis_title"], font=dict(size=11, color=INK_MUTED)),
        range=[0, zmax * 1.12],
        showgrid=True,
        gridcolor=GRIDLINE,
        gridwidth=1,
        zeroline=True,
        zerolinecolor=INK_MUTED,
        zerolinewidth=1,
        tickfont=dict(size=10, color=INK_MUTED),
        row=2,
        col=1,
    )
    fig.update_yaxes(
        tickfont=dict(size=10, color=INK_PRIMARY),
        showgrid=False,
        automargin=True,
        tickmode="linear",
        dtick=1,
        row=2,
        col=1,
    )

    fig.update_layout(
        paper_bgcolor=PAGE_PLANE,
        plot_bgcolor=SURFACE,
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"),
        width=1600,
        height=1900,
        margin=dict(l=20, r=40, t=120, b=130),
        title=dict(
            text=(
                f"<b style='color:{INK_PRIMARY}'>{metric['title']}</b>"
                f"<br><span style='font-size:14px;color:{INK_SECONDARY}'>{metric['subtitle']}</span>"
            ),
            x=0.02,
            xanchor="left",
            y=0.97,
        ),
        showlegend=False,
        annotations=[
            dict(
                text=(
                    "Source: india_sewage_treatment_by_state.csv &nbsp;·&nbsp; "
                    "Gray states = no data in source &nbsp;·&nbsp; "
                    "Bars ranked low → high, same color scale as map"
                ),
                x=0.02,
                y=-0.045,
                xref="paper",
                yref="paper",
                xanchor="left",
                yanchor="top",
                showarrow=False,
                font=dict(size=11, color=INK_MUTED),
            )
        ],
    )

    return fig


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    df = load_data()
    geojson = load_geojson()
    check_name_mapping(df, geojson)

    for metric in METRICS:
        fig = build_figure(df, geojson, metric)
        out_path = OUTPUT_DIR / metric["output"]
        fig.write_image(str(out_path), width=1600, height=1900, scale=2)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
