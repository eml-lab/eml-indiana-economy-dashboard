"""Indiana forecasting dashboard: variable-specific pages, shared navigation."""
from dash import Dash
from config import APP_TITLE
from shared.dashboard import build_dashboard
from variables.nonfarm_employment.editor import register_editor_callbacks
from variables.nonfarm_employment.callbacks import register_forecast_callbacks
from shared.navigation import register_navigation_callbacks
from variables.population.callbacks import register_population_callbacks
from shared.county_callbacks import register_laus_callbacks

app = Dash(__name__)
app.title = APP_TITLE
app.layout = build_dashboard()
register_editor_callbacks(app)
register_forecast_callbacks(app)
register_navigation_callbacks(app)
register_population_callbacks(app)
register_laus_callbacks(app)

if __name__ == "__main__":
    app.run(debug=False)
