"""
Interactive choropleth map of Indian state-level sewage treatment stats.

A single India map with a dropdown to switch between the three metrics in
sources/india_sewage_treatment_by_state.csv:
  - actual_treated_pct_of_generation         ("how much is actually treated")
  - installed_capacity_pct_of_generation     ("nominal capacity vs. need")
  - actual_treated_pct_of_installed_capacity ("efficiency: is built capacity used")

Hover any state for its exact value. No bar-chart panel (see
make_choropleth_maps.py for the static map+bars infographics).

Usage:
    python scripts/make_choropleth_interactive.py

Requires: pandas, plotly.
Geo source: geo/india_states.geojson (state boundaries, property "ST_NM").
"""

import math

import plotly.graph_objects as go

from make_choropleth_maps import (
    METRICS,
    NO_DATA_FILL,
    OUTPUT_DIR,
    PAGE_PLANE,
    SURFACE,
    check_name_mapping,
    load_data,
    load_geojson,
)

# ---------------------------------------------------------------------------
# Custom brand colorscale: pale tint -> #ff6d00 (orange) -> #3c096c (purple)
#
# Requested brand colors are used as the mid and high anchors of a sequential
# ramp. A near-white low anchor is derived from the orange (rather than
# starting the scale ON a fully saturated color) so that near-zero states
# recede toward the map background instead of reading as "loud" — otherwise
# a state with 0% would look just as vivid as one with 50%. Interpolation is
# done in OKLab (perceptual) space so the ramp doesn't muddy through gray
# where orange and purple mix, the same technique behind colormaps like
# viridis/plasma.
# ---------------------------------------------------------------------------

BRAND_ORANGE = "#ff6d00"
BRAND_PURPLE = "#3c096c"


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb)


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    c = max(0.0, c)
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _rgb_to_oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = math.copysign(abs(l) ** (1 / 3), l), math.copysign(abs(m) ** (1 / 3), m), math.copysign(abs(s) ** (1 / 3), s)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return (L, a, b2)


def _oklab_to_rgb(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    L, a, b2 = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b2
    m_ = L - 0.1055613458 * a - 0.0638541728 * b2
    s_ = L - 0.0894841775 * a - 1.2914855480 * b2
    l, m, s = l_**3, m_**3, s_**3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return tuple(_linear_to_srgb(c) for c in (r, g, b))


def _oklab_lerp(hex_a: str, hex_b: str, t: float) -> str:
    a = _rgb_to_oklab(_hex_to_rgb(hex_a))
    b = _rgb_to_oklab(_hex_to_rgb(hex_b))
    mixed = tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
    return _rgb_to_hex(_oklab_to_rgb(mixed))


# Near-white anchor: mostly white, a hint of the brand orange
BRAND_LIGHT = _oklab_lerp("#ffffff", BRAND_ORANGE, 0.14)

_ANCHORS = [(0.0, BRAND_LIGHT), (0.5, BRAND_ORANGE), (1.0, BRAND_PURPLE)]


def build_brand_colorscale(steps: int = 32) -> list:
    """Perceptually-interpolated colorscale: pale tint -> orange -> purple."""
    scale = []
    for i in range(steps + 1):
        t = i / steps
        # find surrounding anchor pair
        for (p0, c0), (p1, c1) in zip(_ANCHORS, _ANCHORS[1:]):
            if p0 <= t <= p1:
                local_t = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
                scale.append([t, _oklab_lerp(c0, c1, local_t)])
                break
    return scale


BRAND_COLORSCALE = build_brand_colorscale()

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"


def zmax_for(df, metric: dict) -> float:
    if metric["zmax_mode"] == "fixed100":
        return 100
    data_max = df[metric["column"]].max()
    return max(100, math.ceil(data_max / 10) * 10)


def title_html(metric: dict) -> str:
    return (
        f"<b style='color:{INK_PRIMARY}'>{metric['title']}</b>"
        f"<br><span style='font-size:13px;color:{INK_SECONDARY}'>{metric['subtitle']}</span>"
    )


def build_figure() -> go.Figure:
    df = load_data()
    geojson = load_geojson()
    check_name_mapping(df, geojson)

    all_geo_names = [f["properties"]["ST_NM"] for f in geojson["features"]]

    fig = go.Figure()

    # Base layer: every state, neutral gray, so unmatched states (Ladakh —
    # split out of J&K after this data was compiled) read as "no data".
    fig.add_trace(
        go.Choropleth(
            geojson=geojson,
            featureidkey="properties.ST_NM",
            locations=all_geo_names,
            z=[0] * len(all_geo_names),
            colorscale=[[0, NO_DATA_FILL], [1, NO_DATA_FILL]],
            showscale=False,
            marker_line_color=SURFACE,
            marker_line_width=0.7,
            hoverinfo="skip",
            name="",
        )
    )

    # One trace per metric; only the first is visible at load.
    for i, metric in enumerate(METRICS):
        zmax = zmax_for(df, metric)
        fig.add_trace(
            go.Choropleth(
                geojson=geojson,
                featureidkey="properties.ST_NM",
                locations=df["geo_name"],
                z=df[metric["column"]],
                zmin=0,
                zmax=zmax,
                colorscale=BRAND_COLORSCALE,
                marker_line_color=SURFACE,
                marker_line_width=0.7,
                visible=(i == 0),
                colorbar=dict(
                    title=dict(text=metric["colorbar_title"], font=dict(size=12, color=INK_SECONDARY)),
                    tickfont=dict(size=11, color=INK_MUTED),
                    ticksuffix="%",
                    len=0.56,
                    thickness=16,
                    x=1.0,
                    y=0.40,
                ),
                customdata=df["state"],
                hovertemplate=f"<b>%{{customdata}}</b><br>{metric['colorbar_title'].replace('<br>', ' ')}: %{{z}}%<extra></extra>",
                name=metric["title"],
            )
        )

    fig.update_geos(
        visible=False,
        projection_type="mercator",
        lonaxis_range=[66.5, 98.5],
        lataxis_range=[5.5, 38.5],
        bgcolor=SURFACE,
        domain=dict(x=[0, 1], y=[0, 0.80]),
    )

    buttons = []
    for i, metric in enumerate(METRICS):
        visible_mask = [True] + [j == i for j in range(len(METRICS))]
        buttons.append(
            dict(
                label=metric["title"],
                method="update",
                args=[{"visible": visible_mask}, {"title.text": title_html(metric)}],
            )
        )

    fig.update_layout(
        paper_bgcolor=PAGE_PLANE,
        plot_bgcolor=SURFACE,
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"),
        width=1000,
        height=1080,
        margin=dict(l=20, r=40, t=110, b=60),
        title=dict(text=title_html(METRICS[0]), x=0.02, xanchor="left", y=0.965),
        updatemenus=[
            dict(
                type="dropdown",
                direction="down",
                buttons=buttons,
                active=0,
                x=0.02,
                xanchor="left",
                y=0.90,
                yanchor="top",
                bgcolor=SURFACE,
                bordercolor="rgba(11,11,11,0.15)",
                font=dict(size=12, color=INK_PRIMARY),
            )
        ],
        annotations=[
            dict(
                text=(
                    "Source: india_sewage_treatment_by_state.csv &nbsp;·&nbsp; "
                    "Gray states = no data in source (e.g. Ladakh, split from J&K after this data was compiled) &nbsp;·&nbsp; "
                    "Hover a state for its value"
                ),
                x=0.02,
                y=-0.03,
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
    fig = build_figure()
    out_path = OUTPUT_DIR / "india_sewage_choropleth_interactive.html"
    fig.write_html(
        str(out_path),
        include_plotlyjs=True,
        full_html=True,
        config={"scrollZoom": True, "displaylogo": False},
    )
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
