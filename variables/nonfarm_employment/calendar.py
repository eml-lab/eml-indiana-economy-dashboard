"""Forecast-end month calendar."""
from dash import html
from variables.nonfarm_employment.data_view import months

# Builds the month buttons shown under "Select the final forecast month".
# To change their visual styling, edit .calendar*, .month-grid, and
# .month-button rules in assets/style.css.
# The selection behavior is handled by callbacks/nonfarm_editor.py.
def month_calendar():
    # Year groups (e.g., 2026 and 2027) come from the available SPF months.
    years = sorted(set(months.year))
    return html.Div(className="calendar", children=[
        html.Div(className="calendar-year", children=[
            html.Div(str(year), className="year-label"),
            html.Div(className="month-grid", children=[
                # Button text: abbreviated month ("Oct"); title: full month/year.
                # The pattern-matching id tells editor.py which month was clicked.
                html.Button(month.strftime("%b"), id={"type": "month", "index": i},
                            # Initial highlighting covers the first three months;
                            # editor.py updates these classes after selection.
                            n_clicks=0, className="month-button selected" if i < 3 else "month-button",
                            title=month.strftime("%B %Y"))
                for i, month in enumerate(months) if month.year == year
            ])
        ]) for year in years
    ])
