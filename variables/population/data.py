"""Read published annual population forecasts. No forecasts are calculated here."""
from pathlib import Path
import pandas as pd

POPULATION_FILE = Path(__file__).resolve().parents[2] / "data" / "population" / "Pop_IN_county_forecast.xlsx"


def load_population_forecasts():
    """Return state and county forecasts, excluding OOS sheets and actual-year rows."""
    state_raw = pd.read_excel(POPULATION_FILE, sheet_name="IN_forecast_2026-2029")
    state_raw = state_raw.loc[state_raw["type"].eq("forecast"), ["Year", "US path", "Indiana"]].copy()
    state_raw["Year"] = state_raw["Year"].astype(int)
    for column in ("US path", "Indiana"):
        state_raw[column] = pd.to_numeric(state_raw[column], errors="raise")
    state = state_raw.set_index("Year")[["Indiana", "US path"]].sort_index()

    county_raw = pd.read_excel(POPULATION_FILE, sheet_name="County_forecast_2026-2029")
    forecast_columns = [col for col in county_raw.columns if str(col).endswith(" forecast")]
    county = county_raw.loc[county_raw["County"].notna() &
                            county_raw["County"].ne("Sum of counties"),
                            ["County", *forecast_columns]].copy()
    county = county.set_index("County")
    county.columns = [int(str(col).split()[0]) for col in forecast_columns]
    county = county.apply(pd.to_numeric, errors="raise").sort_index()
    if county.index.has_duplicates:
        raise ValueError("Duplicate county names in population workbook.")
    return state, county
