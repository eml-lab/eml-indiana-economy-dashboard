"""Page composition. Edit this file to rearrange dashboard sections."""
import plotly.graph_objects as go
from dash import dcc, html, dash_table
from variables.nonfarm_employment.forecasting import us
from variables.nonfarm_employment.data_view import months
from config import APP_TITLE, DEFAULT_FORMAT, DEFAULT_END_INDEX
from variables.nonfarm_employment.calendar import month_calendar
from variables.nonfarm_employment.spreadsheet import editor_columns, table_rows
from variables.nonfarm_employment.charts import forecast_figure
from variables.nonfarm_employment.forecasting import get_spf_baselines


# Assembles the page only; interaction logic lives in callbacks/.
# Most className values below correspond to selectors in assets/style.css.
# Dash component ids (e.g., "format", "run", "comparison") are callback
# connections: do not rename them without updating the callbacks as well.
def build_layout():
    return html.Div(className="shell", children=[
        # PAGE HEADER: top eyebrow, main title, and explanatory subtitle.
        # Change these strings to change the visible heading text.
        html.Header(className="header", children=[
            html.Div("NONFARM EMPLOYMENT FORECASTING", className="eyebrow"),
            html.H1("Indiana Nonfarm Employment Scenarios"),
            html.P("Compare the SPF-based Indiana nonfarm employment forecast with a counterfactual based on your monthly U.S. nonfarm employment premise."),
        ]),
        # INVISIBLE STATE: keeps user inputs, selected horizon/format, and
        # drag-to-fill events available to the editor callbacks.
        dcc.Store(id="saved-values", data={"levels": {}, "mom": {}}),
        dcc.Store(id="selected-end", data=DEFAULT_END_INDEX),
        dcc.Store(id="active-format", data=DEFAULT_FORMAT),
        dcc.Store(id="fill-event"),
        # TWO-COLUMN BODY: "controls" on the left, "results" on the right.
        # Column widths and responsive stacking are in assets/style.css.
        html.Div(className="layout", children=[
            # LEFT PANEL: U.S. premise and the editable input spreadsheet.
            html.Section(className="panel controls", children=[
                html.H2("U.S. nonfarm employment premise"),
                html.P('What is a counterfactual? A counterfactual explores a hypothetical scenario: what would the forecast look like if certain economic conditions were different? Adjust the available inputs to compare the resulting forecast with the baseline forecast.', className="subtle"),
                # Blue information chips: latest U.S. actual and SPF endpoint.
                html.Div(className="meta", children=[
                    html.Span(f"Last U.S. actual: {float(us.iloc[-1]):,.3f} thousand ({us.index[-1]:%b %Y})"),
                    html.Span(f"SPF endpoint: {months[-1]:%b %Y}"),
                ]),
                html.Label("Input format", className="field-label"),
                # Levels/MoM toggle: visible labels and underlying format keys.
                # DEFAULT_FORMAT in config.py determines the initial choice.
                dcc.RadioItems(id="format", options=[
                    {"label": "Nonfarm employment levels (thousands)", "value": "levels"},
                    {"label": "MoM growth (%)", "value": "mom"},
                ], value=DEFAULT_FORMAT, className="format-toggle", inline=True),
                html.Label("Select the final forecast month", className="field-label"),
                # Month buttons are built in components/nonfarm_calendar.py.
                month_calendar(),
                # Dynamic date-range summary; callbacks/nonfarm_editor.py replaces text.
                html.Div(id="selection-summary", className="selection-summary",
                         children=f"October 2026 - {months[2]:%B %Y} - 3 months"),
                # Spreadsheet heading and instructions displayed above the table.
                html.Div(className="spreadsheet-heading", children=[
                    html.H3("Monthly U.S. nonfarm employment forecast"),
                    html.Span("Click a value cell to select it; double-click to edit. Press Enter to save. Drag the blue corner of a filled cell to copy its value.", className="subtle"),
                ]),
                # Editable U.S. forecast table. Column definitions and row values
                # come from components/nonfarm_spreadsheet.py. Styling below is local
                # to Dash DataTable; other table styling is in assets/style.css.
                dash_table.DataTable(
                    id="forecast-table",
                    columns=editor_columns(DEFAULT_FORMAT),
                    data=table_rows(2, {"levels": {}, "mom": {}}, DEFAULT_FORMAT),
                    editable=True,
                    cell_selectable=True,
                    style_table={"overflowX": "hidden", "width": "100%"},
                    style_header={"backgroundColor": "#f1f5f9", "fontWeight": "600", "border": "1px solid #e2e8f0"},
                    style_cell={"fontFamily": "Inter, Segoe UI, Arial, sans-serif", "fontSize": "13px", "padding": "10px 8px", "textAlign": "left", "border": "1px solid #e2e8f0", "minWidth": "0", "maxWidth": "none", "whiteSpace": "normal"},
                    # Width/background of each column, keyed by its column id.
                    style_cell_conditional=[
                        {"if": {"column_id": "month"}, "backgroundColor": "#f8fafc", "width": "18%"},
                        {"if": {"column_id": "spf"}, "backgroundColor": "#eff6ff", "color": "#475569", "width": "25%"},
                        {"if": {"column_id": "value"}, "width": "28%"},
                        {"if": {"column_id": "difference"}, "backgroundColor": "#f8fafc", "color": "#334155", "width": "29%"},
                    ],
                ),
                # RUN BUTTON: callbacks/nonfarm_forecast.py responds to id="run".
                html.Button("Generate forecast comparison", id="run", n_clicks=0, className="primary"),
                # Status/error text displayed after forecast generation.
                html.Div(id="message", role="status", className="message"),
            ]),
            # RIGHT PANEL: Indiana chart and implied U.S. employment table.
            html.Section(className="panel results", children=[
                html.H2("Indiana nonfarm employment forecast"),
                html.P("Compare the LASSO BIC baseline and counterfactual forecasts (thousands of nonfarm employees).", className="subtle"),
                # Show actual Indiana and the existing SPF/LASSO BIC baseline immediately.
                # The counterfactual is added only after the user runs a scenario.
                dcc.Loading(dcc.Graph(id="comparison", config={"displaylogo": False},
                                      figure=forecast_figure(get_spf_baselines()["bic"])), type="circle"),
                # Populated with the implied U.S. level/growth table after a run.
                html.Div(id="implied", className="implied"),

            ]),
        ]),
    ])

