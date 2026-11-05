"""unemployment_rate forecast data adapter."""
from shared.laus_data import load_laus_forecasts

def load_forecasts():
    return load_laus_forecasts("unemployment_rate")
