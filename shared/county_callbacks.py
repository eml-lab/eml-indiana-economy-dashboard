"""County map, search, reset and published forecast display for LAUS variables."""
from dash import Input, Output, State, ctx, no_update, html
from shared.county_map import load_indiana_counties, county_id_lookup
from shared.county_map import county_selection_figure
from shared.county_forecast import forecast_figure, forecast_table, get_forecasts
from shared.laus_data import load_laus_forecasts

def register_laus_callbacks(app):
    for variable in ("total_employment", "unemployment_rate", "wages_salaries"):
        register_variable(app, variable)

def register_variable(app, variable):
    @app.callback(
        Output(f"{variable}-county-controls", "style"),
        Input(f"{variable}-geography", "value"),
    )
    def toggle(geography):
        return {} if geography == "county" else {"display": "none"}

    @app.callback(
        Output(f"{variable}-counties", "data"),
        Output(f"{variable}-county-search", "value"),
        Input(f"{variable}-county-map", "clickData"),
        Input(f"{variable}-county-search", "value"),
        Input(f"{variable}-reset-counties", "n_clicks"),
        State(f"{variable}-counties", "data"),
        prevent_initial_call=True,
    )
    def select_counties(click, searched, reset_clicks, selected):
        selected = list(selected or [])
        trigger = ctx.triggered_id
        if trigger == f"{variable}-reset-counties":
            return [], None
        if trigger == f"{variable}-county-search":
            if not searched:
                return no_update, no_update
            _, county = get_forecasts(variable)
            if searched not in county.index:
                return no_update, None
            if searched not in selected:
                selected.append(searched)
            return selected, None
        if trigger == f"{variable}-county-map":
            if not click or not click.get("points"):
                return no_update, no_update
            fips = str(click["points"][0]["location"]).zfill(5)
            _, county = get_forecasts(variable)
            mapping = county_id_lookup(load_indiana_counties(), county.index)
            name = {code: name for name, code in mapping.items()}.get(fips)
            if name is None:
                return no_update, no_update
            if name in selected:
                selected.remove(name)
            else:
                selected.append(name)
            return selected, no_update
        return no_update, no_update

    @app.callback(
        Output(f"{variable}-county-map", "figure"),
        Output(f"{variable}-selected-label", "children"),
        Input(f"{variable}-counties", "data"),
    )
    def update_map(selected):
        _, county = get_forecasts(variable)
        selected = selected or []
        label = f"Selected: {', '.join(selected)}" if selected else "No counties selected"
        return county_selection_figure(selected, county.index), label

    @app.callback(
        Output(f"{variable}-chart", "figure"),
        Output(f"{variable}-table", "children"),
        Input(f"{variable}-geography", "value"),
        Input(f"{variable}-counties", "data"),
    )
    def update_display(geography, selected):
        state, county = get_forecasts(variable)
        if geography == "state":
            months = list(state.index)
            series = {"Indiana forecast": state["Indiana"].tolist()}
            return forecast_figure(months, series, variable), forecast_table(months, series, variable)
        selected = list(dict.fromkeys(selected or []))
        if not selected:
            return forecast_figure(list(county.columns), {}, variable), html.P(
                "Select at least one county to display its forecast.", className="subtle")
        if set(selected) - set(county.index):
            return forecast_figure(list(county.columns), {}, variable), "Unknown county selection."
        series = {name: county.loc[name].tolist() for name in selected}
        total = variable in ("total_employment", "wages_salaries") and len(selected) > 1
        return (forecast_figure(list(county.columns), series, variable),
                forecast_table(list(county.columns), series, variable, total=total))
