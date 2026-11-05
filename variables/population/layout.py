"""Population page: geography controls, annual forecast chart, and forecast table."""
from dash import dcc, html
import plotly.graph_objects as go
from config import CHART_HEIGHT
from plotly.subplots import make_subplots
from variables.population.data import load_population_forecasts
from shared.county_map import load_indiana_counties, county_id_lookup


def population_layout():
    # County forecasts are display-only; statewide population supports a U.S. path counterfactual.
    _, county = load_population_forecasts()
    return html.Div(className="population-page", children=[
        # PAGE HEADER: matches the employment page's eyebrow, title, and subtitle.
        # Span both grid columns so the heading sits above the two forecast panels.
        html.Header(className="header", style={"gridColumn": "1 / -1"}, children=[
            html.Div("POPULATION FORECASTING", className="eyebrow"),
            html.H1("Indiana Population Forecasts"),
            html.P("Explore annual population forecasts for Indiana and its counties, including comparisons with the U.S. population path."),
        ]),
        html.Section(className="panel", children=[
            html.H2("Population forecasts"),
            html.P("Annual forecasts for Indiana and its counties; statewide scenarios can use an alternative U.S. population path.", className="subtle"),
            html.Label("Geography", className="field-label"),
            dcc.RadioItems(id="population-geography", options=[
                {"label": "Indiana", "value": "state"},
                {"label": "Counties", "value": "county"},
            ], value="state", inline=True, className="format-toggle"),
            # State-only counterfactual inputs. Defaults are the published, adjusted U.S. path.
            html.Div(id="population-state-controls", children=[
                html.H3("Alternative U.S. population path"),
                html.P("Enter U.S. population levels (millions of persons) for every forecast year, then generate the Indiana counterfactual. The baseline is shown until you run a scenario.", className="subtle"),
                html.Div([
                    html.Div([
                        html.Label(str(year), className="field-label"),
                        dcc.Input(id={"type": "population-us-input", "year": int(year)},
                                  type="text",
                                  placeholder=f"Baseline: {float(value) / 1_000_000:,.3f}",
                                  style={"width": "100%"}),
                    ], style={"flex": "1 1 130px"})
                    for year, value in load_population_forecasts()[0]["US path"].items()
                ], style={"display": "flex", "flexWrap": "wrap", "gap": "10px"}),
                html.Button("Generate population counterfactual", id="population-run", n_clicks=0,
                            className="primary", style={"marginTop": "14px"}),
                html.Button("Reset population counterfactual", id="population-reset-scenario", n_clicks=0,
                            className="month-button", style={"marginTop": "14px", "marginLeft": "8px", "padding": "8px 12px"}),
                html.Div(id="population-scenario-message", role="status", className="message"),
            ]),
            dcc.Store(id="population-scenario", data=None),
            # County selection is visible only when geography = county.
            # The selected counties are stored separately from the map's click event.
            # This makes each map click toggle the county on/off.
            dcc.Store(id="population-counties", data=[]),
            html.Div(id="population-county-controls", children=[
                # Search adds a county to the same selection used by the map.
                html.Label("Search County", className="field-label"),
                dcc.Dropdown(
                    id="population-county-search",
                    options=[{"label": name, "value": name} for name in sorted(county.index)],
                    placeholder="Type a county name...",
                    searchable=True,
                    clearable=True,
                ),
                html.Button("Reset Counties", id="population-reset-counties", n_clicks=0,
                            className="month-button", style={"marginTop": "12px"}),
                html.Label("Select counties on the map", className="field-label"),
                html.P("Click a county to select it; click again to remove it.", className="subtle"),
                dcc.Graph(id="population-county-map", config={"displaylogo": False},
                          style={"height": "520px"}),
                html.Div(id="population-selected-label", className="subtle"),
            ], style={"display": "none"}),
        ]),
        html.Section(className="panel", children=[
            html.H2("Annual population forecast"),
            dcc.Graph(id="population-chart", config={"displaylogo": False}),
            html.Div(id="population-table", className="implied"),
        ]),
    ])


def population_figure(years, series):
    """Plot one line per selected geography; population values are persons."""
    fig = go.Figure()
    for label, values in series.items():
        fig.add_trace(go.Scatter(x=years, y=values, mode="lines+markers", name=label))
    fig.update_layout(template="plotly_white", height=CHART_HEIGHT,
                      margin={"l": 20, "r": 20, "t": 28, "b": 20},
                      xaxis_title="Forecast year", yaxis_title="Population (persons)",
                      xaxis={"tickmode": "array", "tickvals": list(years)},
                      legend={"orientation": "h", "y": 1.14, "x": 0}, hovermode="x unified")
    return fig



def state_population_figure(years, indiana, us_path, alternative_indiana=None, alternative_us=None):
    """Independent Indiana and U.S. panels, retaining counterfactual comparisons."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.16,
                        subplot_titles=("Indiana population forecast", "U.S. population path"))
    def millions(values):
        return [float(v) / 1_000_000 for v in values]
    fig.add_trace(go.Scatter(x=years, y=millions(indiana), mode="lines+markers",
                             name="Indiana forecast", line={"color": "#2563eb", "width": 2.5}), row=1, col=1)
    fig.add_trace(go.Scatter(x=years, y=millions(us_path), mode="lines+markers",
                             name="U.S. path", line={"color": "#ea580c", "width": 2.5}), row=2, col=1)
    if alternative_indiana is not None:
        fig.add_trace(go.Scatter(x=years, y=millions(alternative_indiana), mode="lines+markers",
                                 name="Indiana counterfactual", line={"color": "#16a34a", "width": 2.5}), row=1, col=1)
    if alternative_us is not None:
        fig.add_trace(go.Scatter(x=years, y=millions(alternative_us), mode="lines+markers",
                                 name="Alternative U.S. path", line={"color": "#9333ea", "width": 2}), row=2, col=1)
    fig.update_layout(template="plotly_white", height=700,
                      margin={"l": 75, "r": 30, "t": 65, "b": 50},
                      legend={"orientation": "h", "y": 1.13, "x": 0}, hovermode="x unified")
    fig.update_yaxes(title_text="Indiana population (millions)", tickformat=",.3f", row=1, col=1)
    fig.update_yaxes(title_text="U.S. population (millions)", tickformat=",.3f", row=2, col=1)
    fig.update_xaxes(tickmode="array", tickvals=list(years))
    fig.update_xaxes(title_text="Forecast year", row=2, col=1)
    return fig


def state_population_table(years, indiana, us_path, alternative_indiana=None, alternative_us=None):
    """State forecast table, displayed in millions (model data remain in persons)."""
    headers = [html.Th("Year"), html.Th("Indiana forecast (millions)"), html.Th("U.S. path (millions)")]
    if alternative_indiana is not None:
        headers += [html.Th("Indiana counterfactual (millions)"), html.Th("Alternative U.S. path (millions)")]
    rows = []
    for i, year in enumerate(years):
        cells = [html.Td(str(year)), html.Td(f"{float(indiana[i]) / 1_000_000:,.3f}"), html.Td(f"{float(us_path[i]) / 1_000_000:,.3f}")]
        if alternative_indiana is not None:
            cells += [html.Td(f"{float(alternative_indiana[i]) / 1_000_000:,.3f}"),
                      html.Td(f"{float(alternative_us[i]) / 1_000_000:,.3f}")]
        rows.append(html.Tr(cells))
    return html.Div(className="population-table-scroll", children=[
        html.Table([html.Thead(html.Tr(headers)), html.Tbody(rows)])
    ])


def population_table(years, series, show_total=False):
    """Each county is a separate column; the optional final column sums selected counties."""
    labels = list(series)
    headers = [html.Th("Year"), *[html.Th(name) for name in labels]]
    if show_total:
        headers.append(html.Th("Selected counties total"))
    rows = []
    for i, year in enumerate(years):
        values = [int(series[name][i]) for name in labels]
        cells = [html.Td(str(year)), *[html.Td(f"{v:,}") for v in values]]
        if show_total:
            cells.append(html.Td(f"{sum(values):,}"))
        rows.append(html.Tr(cells))
    return html.Div(className="population-table-scroll", children=[
        html.Table([html.Thead(html.Tr(headers)), html.Tbody(rows)])
    ])


from shared.county_map import county_selection_figure
