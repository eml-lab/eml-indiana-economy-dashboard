"""Indiana county boundaries and county-name-to-FIPS matching for the map.

The Plotly boundary GeoJSON identifies counties by FIPS but does not include
county names. A separate Census county listing supplies the name-to-FIPS map.
Both resources are cached locally after the first successful download.
"""
import json
from pathlib import Path
from urllib.request import urlopen

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "geography"
SOURCE_URL = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
CENSUS_URL = "https://api.census.gov/data/2020/dec/pl?get=NAME&for=county:*&in=state:18"
CACHE_FILE = DATA_DIR / "indiana_counties.geojson"
NAME_CACHE_FILE = DATA_DIR / "indiana_county_fips.json"


def load_indiana_counties():
    """Return the 92 Indiana county polygons, indexed by five-digit FIPS ID."""
    if CACHE_FILE.exists():
        with CACHE_FILE.open(encoding="utf-8") as f:
            geojson = json.load(f)
    else:
        try:
            with urlopen(SOURCE_URL, timeout=25) as response:
                source = json.load(response)
        except Exception as exc:
            raise RuntimeError(
                "County boundaries could not be downloaded. Connect to the internet "
                "for the first run, or provide data/indiana_counties.geojson."
            ) from exc
        features = [feature for feature in source["features"]
                    if str(feature.get("id", "")).zfill(5).startswith("18")]
        geojson = {"type": "FeatureCollection", "features": features}
        if len(features) != 92:
            raise ValueError(f"Expected 92 Indiana county boundaries; found {len(features)}")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(geojson), encoding="utf-8")

    if len(geojson["features"]) != 92:
        raise ValueError("The Indiana county boundary file must contain 92 counties.")
    return geojson


def _county_name_to_fips():
    """Load the Census county-name lookup; cache it for subsequent launches."""
    if NAME_CACHE_FILE.exists():
        with NAME_CACHE_FILE.open(encoding="utf-8") as f:
            return json.load(f)

    try:
        with urlopen(CENSUS_URL, timeout=25) as response:
            rows = json.load(response)
    except Exception as exc:
        raise RuntimeError(
            "County names could not be downloaded from the U.S. Census Bureau. "
            "Connect to the internet for the first run, or provide "
            "data/indiana_county_fips.json."
        ) from exc

    # Census returns columns: NAME, state, county (e.g. Adams County, Indiana / 18 / 001).
    header = rows[0]
    name_i, state_i, county_i = (header.index(k) for k in ("NAME", "state", "county"))
    lookup = {
        row[name_i].split(",")[0].removesuffix(" County").strip():
            row[state_i] + row[county_i]
        for row in rows[1:]
    }
    if len(lookup) != 92:
        raise ValueError(f"Expected 92 Indiana county names from Census; found {len(lookup)}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    NAME_CACHE_FILE.write_text(json.dumps(lookup, indent=2), encoding="utf-8")
    return lookup


def county_id_lookup(geojson, county_names):
    """Match workbook county names to the polygon FIPS IDs (no GeoJSON name field)."""
    def normalize(name):
        return str(name).lower().replace(" county", "").replace(".", "").replace("'", "").strip()

    by_name = {normalize(name): fips for name, fips in _county_name_to_fips().items()}
    available_ids = {str(feature["id"]).zfill(5) for feature in geojson["features"]}
    missing = [name for name in county_names
               if normalize(name) not in by_name or by_name[normalize(name)] not in available_ids]
    if missing:
        raise ValueError(f"County names not found in map boundaries: {missing}")
    return {name: by_name[normalize(name)] for name in county_names}


import plotly.graph_objects as go

def county_selection_figure(selected, county_names):
    """Map colors indicate selection; clicks return a county FIPS in clickData."""
    geojson = load_indiana_counties()
    name_to_id = county_id_lookup(geojson, county_names)
    id_to_name = {fips: name for name, fips in name_to_id.items()}
    locations = list(id_to_name)
    selected_ids = {name_to_id[name] for name in selected if name in name_to_id}
    fig = go.Figure(go.Choropleth(
        geojson=geojson, locations=locations,
        z=[1 if fips in selected_ids else 0 for fips in locations],
        featureidkey="id", locationmode="geojson-id",
        text=[id_to_name[fips] for fips in locations],
        hovertemplate="%{text} County<extra></extra>",
        colorscale=[[0, "#e2e8f0"], [0.499, "#e2e8f0"],
                    [0.5, "#2563eb"], [1, "#2563eb"]],
        zmin=0, zmax=1, showscale=False,
        marker_line_color="#ffffff", marker_line_width=0.7,
    ))
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 5, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        clickmode="event",
        uirevision="indiana-county-map",
    )
    return fig
