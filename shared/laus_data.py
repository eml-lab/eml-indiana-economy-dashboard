"""Read the published LAUS forecast sheets only. Missing cells stay missing."""
from functools import lru_cache
from pathlib import Path
import pandas as pd
from shared.county_map import _county_name_to_fips

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SPECS = {
    "total_employment": ("LAUS_E_IN_county_forecast.xlsx", "IN_forecast_2026-10_2029-09",
                         "County_forecast_2026-10_2029-09", "Indiana"),
    "unemployment_rate": ("LAUS_UR_IN_county_forecast.xlsx", "IN_UR_forecast_2026-10_2029-09",
                          "Cty_UR_forecast_2026-10_2029-09", "Indiana UR"),
}

@lru_cache(maxsize=2)
def load_laus_forecasts(variable):
    filename, state_sheet, county_sheet, state_col = SPECS[variable]
    file = DATA_DIR / variable / filename
    state_raw = pd.read_excel(file, sheet_name=state_sheet)
    state_raw = state_raw.loc[state_raw["type"].astype(str).str.lower().eq("forecast"),
                              ["Month", state_col]].copy()
    state_raw["Month"] = pd.to_datetime(state_raw["Month"].astype(str), format="%Y-%m")
    state_raw[state_col] = pd.to_numeric(state_raw[state_col], errors="coerce")
    state = state_raw.set_index("Month")[[state_col]].sort_index()
    state.columns = ["Indiana"]

    county_raw = pd.read_excel(file, sheet_name=county_sheet)
    forecast_cols = [col for col in county_raw if str(col).endswith(" forecast")]
    months = pd.to_datetime([str(col).removesuffix(" forecast") for col in forecast_cols],
                            format="%Y-%m")
    county = county_raw.loc[county_raw["County"].notna(), ["County", *forecast_cols]].copy()
    county = county.set_index("County")
    county.index = county.index.astype(str).str.strip().str.removesuffix(" County")
    county = county.apply(pd.to_numeric, errors="coerce")
    county.columns = months
    # Some sheets append a statewide summary row; only retain the 92 counties.
    valid_counties = set(_county_name_to_fips())
    county = county.loc[county.index.isin(valid_counties)]
    county = county.loc[~county.index.duplicated(keep="first")]
    if len(county) != 92:
        raise ValueError(f"Expected 92 county rows for {variable}, found {len(county)}")
    # Align the displayed horizon to the state forecast months.
    county = county.reindex(columns=state.index)
    return state, county
