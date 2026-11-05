"""Population page interactions: geography selection and published forecast display."""
import math
from dash import Input, Output, State, ALL, html, no_update, ctx
from variables.population.data import load_population_forecasts
from variables.population.counterfactual import run_state_population_counterfactual
from variables.population.layout import (
    population_figure, population_table, state_population_figure, state_population_table,
    county_selection_figure,
)


def register_population_callbacks(app):
    @app.callback(
        Output("population-state-controls", "style"),
        Input("population-geography", "value"),
    )
    def toggle_state(geography):
        return {} if geography == "state" else {"display": "none"}

    @app.callback(
        Output("population-scenario", "data"),
        Output("population-scenario-message", "children"),
        Output({"type": "population-us-input", "year": ALL}, "value"),
        Input("population-run", "n_clicks"),
        Input("population-reset-scenario", "n_clicks"),
        State({"type": "population-us-input", "year": ALL}, "value"),
        State({"type": "population-us-input", "year": ALL}, "id"),
        prevent_initial_call=True,
    )
    def update_scenario(run_clicks, reset_clicks, values, ids):
        if ctx.triggered_id == "population-reset-scenario":
            return None, "", [None] * len(ids)
        if ctx.triggered_id != "population-run":
            return no_update, no_update, [no_update] * len(ids)
        state, _ = load_population_forecasts()
        years = list(state.index)
        inputs = {int(item["year"]): value for item, value in zip(ids, values)}
        if set(inputs) != set(years) or any(inputs[year] is None or str(inputs[year]).strip() == "" for year in years):
            return no_update, "Enter a U.S. population level (millions) for every forecast year.", [no_update] * len(ids)
        try:
            # Convert displayed millions back to persons before calling the unchanged model.
            # Text inputs remove browser spinner controls; validate numerically here.
            levels = {year: float(inputs[year]) for year in years}
            if any(not math.isfinite(value) or value <= 0 for value in levels.values()):
                return no_update, "Enter a positive, finite U.S. population level (millions) for every forecast year.", [no_update] * len(ids)
            scenario_us = {year: levels[year] * 1_000_000 for year in years}
            scenario_in = run_state_population_counterfactual(scenario_us)
        except (ValueError, ArithmeticError, KeyError) as exc:
            return no_update, f"Unable to generate scenario: {exc}", [no_update] * len(ids)
        return {
            "us": [scenario_us[year] for year in years],
            "indiana": [float(scenario_in.loc[year]) for year in years],
            "years": years,
        }, "Counterfactual generated.", [no_update] * len(ids)

    @app.callback(
        Output("population-county-controls", "style"),
        Input("population-geography", "value"),
    )
    def toggle_counties(geography):
        return {} if geography == "county" else {"display": "none"}

    @app.callback(
        Output("population-counties", "data"),
        Output("population-county-search", "value"),
        Input("population-county-map", "clickData"),
        Input("population-county-search", "value"),
        Input("population-reset-counties", "n_clicks"),
        State("population-counties", "data"),
        prevent_initial_call=True,
    )
    def update_county_selection(click, searched, reset_clicks, selected):
        """Map toggles; search adds; Reset clears the shared county selection."""
        selected = list(selected or [])
        trigger = ctx.triggered_id

        if trigger == "population-reset-counties":
            return [], None

        if trigger == "population-county-search":
            if not searched:
                return no_update, no_update
            _, county = load_population_forecasts()
            if searched not in county.index:
                return no_update, None
            if searched not in selected:
                selected.append(searched)
            # Clear the search field so another county can be typed immediately.
            return selected, None

        if trigger == "population-county-map":
            if not click or not click.get("points"):
                return no_update, no_update
            fips = str(click["points"][0]["location"]).zfill(5)
            from shared.county_map import load_indiana_counties, county_id_lookup
            _, county = load_population_forecasts()
            name_to_id = county_id_lookup(load_indiana_counties(), county.index)
            id_to_name = {code: name for name, code in name_to_id.items()}
            name = id_to_name.get(fips)
            if name is None:
                return no_update, no_update
            if name in selected:
                selected.remove(name)
            else:
                selected.append(name)
            return selected, no_update

        return no_update, no_update

    @app.callback(
        Output("population-county-map", "figure"),
        Output("population-selected-label", "children"),
        Input("population-counties", "data"),
    )
    def update_county_map(selected):
        _, county = load_population_forecasts()
        selected = selected or []
        label = (f"Selected: {', '.join(selected)}" if selected
                 else "No counties selected")
        return county_selection_figure(selected, county.index), label

    @app.callback(
        Output("population-chart", "figure"),
        Output("population-table", "children"),
        Input("population-geography", "value"),
        Input("population-counties", "data"),
        Input("population-scenario", "data"),
    )
    def update_population(geography, selected, scenario):
        state, county = load_population_forecasts()
        if geography == "state":
            years = list(state.index)
            indiana = state["Indiana"].tolist()
            us_path = state["US path"].tolist()
            valid_scenario = scenario if scenario and scenario.get("years") == years else None
            alternative_indiana = valid_scenario["indiana"] if valid_scenario else None
            alternative_us = valid_scenario["us"] if valid_scenario else None
            return (
                state_population_figure(years, indiana, us_path, alternative_indiana, alternative_us),
                state_population_table(years, indiana, us_path, alternative_indiana, alternative_us),
            )

        selected = list(dict.fromkeys(selected or []))
        unknown = set(selected) - set(county.index)
        if unknown:
            return population_figure(list(county.columns), {}), "Unknown county selection."
        if not selected:
            return population_figure(list(county.columns), {}), html.P(
                "Select at least one county to display its forecast.", className="subtle"
            )
        years = list(county.columns)
        series = {name: [int(v) for v in county.loc[name, years]] for name in selected}
        return population_figure(years, series), population_table(years, series, show_total=len(selected) > 1)
