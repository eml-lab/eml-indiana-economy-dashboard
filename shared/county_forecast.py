"""Shared state/county forecast presentation for LAUS total employment and UR."""
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
from config import CHART_HEIGHT
from shared.laus_data import load_laus_forecasts
from variables.wages_salaries.data import load_wages_forecasts
from shared.county_map import county_selection_figure

META = {
    "total_employment": ("TOTAL EMPLOYMENT FORECASTING", "Indiana Total Employment Forecasts",
                         "Total employment", "Employment (persons)", False),
    "wages_salaries": ("WAGES AND SALARIES FORECASTING", "Indiana Wages and Salaries Forecasts",
                        "Wages and salaries", "Wages and salaries (millions of dollars)", False),
    "unemployment_rate": ("UNEMPLOYMENT RATE FORECASTING", "Indiana Unemployment Rate Forecasts",
                          "Unemployment rate", "Unemployment rate (%)", True),
}

def get_forecasts(variable):
    return load_wages_forecasts() if variable == "wages_salaries" else load_laus_forecasts(variable)

def page_layout(variable):
    eyebrow, title, label, unit, rate = META[variable]
    _, county = get_forecasts(variable)
    return html.Div(className="population-page", children=[
        html.Header(className="header", style={"gridColumn": "1 / -1"}, children=[
            html.Div(eyebrow, className="eyebrow"),
            html.H1(title),
            html.P(f"Explore the published {'quarterly' if variable == 'wages_salaries' else 'monthly'} Indiana and county forecasts."),
        ]),
        html.Section(className="panel", children=[
            html.H2(f"{label} forecasts"),
            html.P("Published forecasts only; no counterfactual inputs.", className="subtle"),
            html.Label("Geography", className="field-label"),
            dcc.RadioItems(id=f"{variable}-geography", options=[
                {"label": "Indiana", "value": "state"},
                {"label": "Counties", "value": "county"},
            ], value="state", inline=True, className="format-toggle"),
            dcc.Store(id=f"{variable}-counties", data=[]),
            html.Div(id=f"{variable}-county-controls", children=[
                html.Label("Search County", className="field-label"),
                dcc.Dropdown(id=f"{variable}-county-search",
                             options=[{"label": name, "value": name} for name in sorted(county.index)],
                             placeholder="Type a county name...", searchable=True, clearable=True),
                html.Button("Reset Counties", id=f"{variable}-reset-counties", n_clicks=0,
                            className="month-button", style={"marginTop": "12px", "padding": "8px 16px", "width": "auto"}),
                html.Label("Select counties on the map", className="field-label"),
                html.P("Click a county to select it; click again to remove it.", className="subtle"),
                dcc.Graph(id=f"{variable}-county-map", config={"displaylogo": False}, style={"height": "680px"}),
                html.Div(id=f"{variable}-selected-label", className="subtle"),
            ], style={"display": "none"}),
        ]),
        html.Section(className="panel", children=[
            html.H2(f"{'Quarterly' if variable == 'wages_salaries' else 'Monthly'} {label.lower()} forecast"),
            dcc.Graph(id=f"{variable}-chart", config={"displaylogo": False}),
            html.Div(id=f"{variable}-table", className="implied"),
        ]),
    ])

def forecast_figure(months, series, variable):
    _, _, _, unit, rate = META[variable]
    fig = go.Figure()
    for name, values in series.items():
        fig.add_trace(go.Scatter(x=months, y=values, mode="lines+markers",
                                 name=name, connectgaps=False))
    fig.update_layout(template="plotly_white", height=CHART_HEIGHT,
                      margin={"l": 20, "r": 20, "t": 35, "b": 20},
                      xaxis_title="Quarter" if variable == "wages_salaries" else "Month", yaxis_title=unit,
                      legend={"orientation": "h", "y": 1.14, "x": 0},
                      hovermode="x unified")
    fig.update_yaxes(tickformat=".2f" if rate else ",.2f" if variable == "wages_salaries" else ",.0f")
    return fig

def forecast_table(months, series, variable, total=False):
    rate = META[variable][4]
    names = list(series)
    headers = [html.Th("Quarter" if variable == "wages_salaries" else "Month"), *[html.Th(name) for name in names]]
    if total:
        headers.append(html.Th("Selected counties total"))
    rows = []
    for i, month in enumerate(months):
        vals = [series[name][i] for name in names]
        cells = [html.Td(str(month) if variable == "wages_salaries" else pd.Timestamp(month).strftime("%b %Y"))]
        for value in vals:
            cells.append(html.Td("N/A" if pd.isna(value) else
                                 (f"{float(value):.3f}%" if rate else f"{float(value):,.2f}" if variable == "wages_salaries" else f"{float(value):,.0f}")))
        if total:
            # Do not report a partial sum as a complete county total.
            cells.append(html.Td("N/A" if any(pd.isna(v) for v in vals)
                                 else (f"{sum(float(v) for v in vals):,.2f}" if variable == "wages_salaries" else f"{sum(float(v) for v in vals):,.0f}")))
        rows.append(html.Tr(cells))
    return html.Div(className="population-table-scroll", children=[
        html.Table([html.Thead(html.Tr(headers)), html.Tbody(rows)])
    ])
