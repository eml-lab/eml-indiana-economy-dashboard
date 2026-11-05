"""Top-level variable selector; each variable has its own independent page."""
from dash import dcc, html
from variables.nonfarm_employment.layout import build_layout as nonfarm_layout
from variables.population.layout import population_layout
from shared.county_forecast import page_layout as laus_layout
from variables.gdp.layout import gdp_layout


def build_dashboard():
    return html.Div([
        html.Div(className="variable-selector", children=[
            html.Label("Forecast variable", className="field-label"),
            dcc.Dropdown(id="dashboard-variable", options=[
                {"label": "Nonfarm Employment", "value": "nonfarm_employment"},
                {"label": "Population", "value": "population"},
                {"label": "Total Employment", "value": "total_employment"},
                {"label": "Unemployment Rate", "value": "unemployment_rate"},
                {"label": "GDP", "value": "gdp"},
                {"label": "Wages and Salaries", "value": "wages_salaries"},
            ], value="nonfarm_employment", clearable=False),
        ]),
        # Keep both pages mounted: nonfarm employment inputs and results are preserved
        # when the user switches to Population and then back.
        html.Div(id="nonfarm-employment-page", children=nonfarm_layout()),
        html.Div(id="population-page", children=population_layout(), style={"display": "none"}),
        html.Div(id="total-employment-page", children=laus_layout("total_employment"), style={"display": "none"}),
        html.Div(id="unemployment-rate-page", children=laus_layout("unemployment_rate"), style={"display": "none"}),
        html.Div(id="gdp-page", children=gdp_layout(), style={"display": "none"}),
        html.Div(id="wages-salaries-page", children=laus_layout("wages_salaries"), style={"display": "none"}),
    ])
