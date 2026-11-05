"""Quarterly QCEW wages and salaries forecasts (original workbook units: millions of dollars)."""
from functools import lru_cache
from pathlib import Path
import pandas as pd
from shared.county_map import _county_name_to_fips

WORKBOOK = Path(__file__).resolve().parents[2] / 'data' / 'wages_salaries' / 'QCEW_W_IN_county_forecast.xlsx'

@lru_cache(maxsize=1)
def load_wages_forecasts():
    state_raw = pd.read_excel(WORKBOOK, sheet_name='IN_forecast_2026Q2_2029Q1')
    state_raw = state_raw.loc[state_raw['type'].astype(str).str.lower().eq('forecast'), ['Quarter', 'Indiana']].copy()
    state_raw['Indiana'] = pd.to_numeric(state_raw['Indiana'], errors='coerce')
    state = state_raw.set_index('Quarter').sort_index()
    state.index = state.index.astype(str)

    raw = pd.read_excel(WORKBOOK, sheet_name='County_forecast_2026Q2_2029Q1')
    columns = [c for c in raw.columns if str(c).endswith(' forecast')]
    county = raw.set_index('County')[columns]
    county.index = county.index.astype(str).str.strip().str.removesuffix(' County')
    county = county.loc[county.index.isin(_county_name_to_fips())]
    county = county.loc[~county.index.duplicated(keep='first')]
    county = county.apply(pd.to_numeric, errors='coerce')
    county.columns = [str(c).removesuffix(' forecast') for c in columns]
    county = county.reindex(columns=state.index)
    if len(state) != 12 or county.shape != (92, 12):
        raise ValueError(f'Unexpected wages forecast dimensions: state={state.shape}, county={county.shape}')
    return state, county
