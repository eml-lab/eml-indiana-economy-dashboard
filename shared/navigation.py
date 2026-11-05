"""Keep all six variable pages mounted; show only the selected page."""
from dash import Input, Output

PAGES = ("nonfarm-employment", "population", "total-employment", "unemployment-rate", "gdp", "wages-salaries")

def register_navigation_callbacks(app):
    @app.callback(
        *[Output(f"{page}-page", "style") for page in PAGES],
        Input("dashboard-variable", "value"),
    )
    def switch_page(variable):
        active = "nonfarm-employment" if variable == "nonfarm_employment" else variable.replace("_", "-")
        return tuple({} if page == active else {"display": "none"} for page in PAGES)
