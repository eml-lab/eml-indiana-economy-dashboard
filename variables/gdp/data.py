"""Published quarterly Indiana GDP forecast and associated U.S. path (million dollars)."""
from functools import lru_cache
from pathlib import Path
import pandas as pd

@lru_cache(maxsize=1)
def load_gdp_forecasts():
    path = Path(__file__).resolve().parents[2] / 'data' / 'gdp' / 'GDP_IN_forecast.xlsx'
    frame = pd.read_excel(path, sheet_name='IN_forecast_2026Q3_2029Q4')
    frame = frame.loc[frame['type'].astype(str).str.casefold().eq('forecast'),
                      ['Quarter', 'Indiana', 'US path']].copy()
    frame['Quarter'] = frame['Quarter'].astype(str).str.strip()
    for col in ('Indiana', 'US path'):
        frame[col] = pd.to_numeric(frame[col], errors='coerce')
    if frame['Quarter'].duplicated().any():
        raise ValueError('Duplicate GDP forecast quarters')
    return frame.reset_index(drop=True)
