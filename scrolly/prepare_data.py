"""
Prepare web-ready data for the scrollytelling page.

Why this step exists
--------------------
The original geo/india_states.geojson is ~1 MB with very detailed borders.
On a web page nobody can see that detail, but every reader has to download it.
This script:
  1. simplifies the state shapes (fewer points, rounded coordinates),
  2. merges the sewage-treatment numbers from the CSV into each state,
  3. writes ONE small JSON file: scrolly/src/data/india_states.json

The build script (build.py) then pastes that JSON into the final HTML, so the
final page needs no separate data files.

Run it again whenever the CSV or GeoJSON changes:
    python scrolly/prepare_data.py

Requires: shapely (already installed for the analysis scripts).
"""

import csv
import json
from pathlib import Path

from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parent.parent
GEOJSON_IN = ROOT / "geo" / "india_states.geojson"
CSV_IN = ROOT / "sources" / "india_sewage_treatment_by_state.csv"
OUT = Path(__file__).resolve().parent / "src" / "data" / "india_states.json"

# How aggressively to simplify borders, in degrees (~0.02° ≈ 2 km).
# Bigger = smaller file, blockier borders.
SIMPLIFY_TOLERANCE = 0.02
COORD_DECIMALS = 3

# Same mapping as scripts/make_choropleth_maps.py: CSV spelling -> GeoJSON spelling.
CSV_TO_GEOJSON_NAME = {
    "Andaman & Nicobar Islands": "Andaman & Nicobar",
    "Daman Diu Dadra & Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "NCT of Delhi": "Delhi",
}

NUMERIC_COLUMNS = [
    "sewage_generation_mld",
    "installed_capacity_mld",
    "installed_capacity_pct_of_generation",
    "actual_treated_mld",
    "actual_treated_pct_of_generation",
    "actual_treated_pct_of_installed_capacity",
]


def round_coords(obj, nd):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(c, nd) for c in obj]
        return [round_coords(o, nd) for o in obj]
    return obj


def load_sewage():
    rows, national = {}, None
    with open(CSV_IN, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            values = {c: float(row[c]) for c in NUMERIC_COLUMNS}
            if row["state"] == "Total":
                national = values
            else:
                rows[CSV_TO_GEOJSON_NAME.get(row["state"], row["state"])] = values
    return rows, national


def main():
    geo = json.loads(GEOJSON_IN.read_text(encoding="utf-8"))
    sewage, national = load_sewage()

    features = []
    for feat in geo["features"]:
        name = feat["properties"]["ST_NM"]
        geom = shape(feat["geometry"]).simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        features.append({
            "type": "Feature",
            "properties": {"name": name, "sewage": sewage.get(name)},
            "geometry": {**mapping(geom), "coordinates": round_coords(mapping(geom)["coordinates"], COORD_DECIMALS)},
        })

    missing = set(sewage) - {f["properties"]["name"] for f in features}
    if missing:
        raise ValueError(f"CSV states with no matching shape: {sorted(missing)}")

    out = {
        "type": "FeatureCollection",
        "features": features,
        "national_sewage": national,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB, {len(features)} states)")


if __name__ == "__main__":
    main()
