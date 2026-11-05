"""Plotly visualization of the existing LASSO BIC forecast results."""
import plotly.graph_objects as go
from variables.nonfarm_employment.forecasting import in_emp
from config import PLOT_START, COLORS, CHART_HEIGHT


# This function draws the chart in the right-hand results panel.
# Inputs are already-computed Indiana employment series, in thousands.
# Colors, starting date, and height are configured in config.py.
def forecast_figure(spf, user=None):
    fig = go.Figure()
    # Dark line: observed Indiana employment. PLOT_START controls its first month.
    actual = in_emp.loc[PLOT_START:]
    fig.add_trace(go.Scatter(x=actual.index, y=actual.values, mode="lines", name="Actual Indiana nonfarm employment", line={"color": COLORS["actual"], "width": 2.5}))
    # Both forecast lines start at the last observed Indiana value so
    # that the historical and forecast segments connect visually.
    origin = actual.index[-1]
    anchor = float(actual.iloc[-1])
    # Blue line: Indiana forecast under the SPF U.S. employment path.
    fig.add_trace(go.Scatter(
        x=[origin, *spf.index], y=[anchor, *spf.values],
        mode="lines+markers", name="SPF baseline",
        line={"color": COLORS["spf"], "width": 2.5, "dash": "solid"}, marker={"size": 5},
    ))
    # Orange line: Indiana forecast under the user-defined U.S. path.
    if user is not None:
        fig.add_trace(go.Scatter(
            x=[origin, *user.index], y=[anchor, *user.values],
        mode="lines+markers", name="Counterfactual",
            line={"color": COLORS["counterfactual"], "width": 2.5, "dash": "solid"}, marker={"size": 5},
        ))
    # Dotted vertical line marks the boundary between actuals and forecasts.
    fig.add_vline(x=origin.timestamp() * 1000, line_dash="dot", line_color=COLORS["forecast_start"])
    # Plot dimensions, axis titles, legend placement, and hover behavior.
    # Edit here to change labels/layout; edit config.py for CHART_HEIGHT.
    fig.update_layout(template="plotly_white", margin={"l": 20, "r": 20, "t": 28, "b": 20}, height=CHART_HEIGHT,
                      xaxis_title="Month", yaxis_title="Indiana nonfarm employment (thousands)", legend={"orientation": "h", "y": 1.14, "x": 0}, hovermode="x unified")
    return fig
