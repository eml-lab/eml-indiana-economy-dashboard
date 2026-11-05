"""Generate the single selected LASSO BIC forecast without modifying estimation."""
from dash import Input, Output, State, no_update, html
from variables.nonfarm_employment.forecasting import run_comparison
from variables.nonfarm_employment.charts import forecast_figure


def register_forecast_callbacks(app):
    @app.callback(
        Output("comparison", "figure"), Output("message", "children"), Output("implied", "children"),
        Input("run", "n_clicks"), State("format", "value"), State("forecast-table", "data"),
        prevent_initial_call=True,
    )
    def generate(n, fmt, rows):
        values = [r.get("value") for r in rows]
        if not values or any(v is None or v == "" for v in values):
            return no_update, "Enter a value for every selected month.", no_update
        try:
            # Employment levels are already in the backend's original units (thousands).
            # Growth-rate inputs remain percentages.
            model_values = [float(str(v).replace(",", "")) for v in values]
            converted, pairs = run_comparison(model_values, fmt, ["bic"])
            spf, user = pairs["bic"]
            fig = forecast_figure(spf, user)
            table_rows_out = [html.Tr([html.Td(r.month.strftime("%b %Y")), html.Td(f"{r.employment_level:,.3f}"), html.Td(f"{r.mom_growth:.4f}%")]) for r in converted.itertuples(index=False)]
            table = html.Div([html.H3("Implied U.S. nonfarm employment path"), html.Table([html.Thead(html.Tr([html.Th("Month"), html.Th("Level (thousands)"), html.Th("MoM growth")])), html.Tbody(table_rows_out)])])
            return fig, f"Forecast generated through {converted.month.iloc[-1]:%b %Y} using LASSO BIC.", table
        except Exception as exc:
            return no_update, f"Forecast could not be generated: {exc}", no_update
