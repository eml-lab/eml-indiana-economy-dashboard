"""Calendar, editable input preservation, and drag-to-fill callbacks."""
from dash import Input, Output, State, ALL, ctx, no_update, Patch
from variables.nonfarm_employment.data_view import months
from variables.nonfarm_employment.spreadsheet import editor_columns, table_rows, format_difference


def register_editor_callbacks(app):
    @app.callback(
        Output("forecast-table", "data"),
        Output("saved-values", "data"),
        Output("selected-end", "data"),
        Output("active-format", "data"),
        Output("forecast-table", "columns"),
        Input({"type": "month", "index": ALL}, "n_clicks"),
        Input("format", "value"),
        Input("forecast-table", "data_timestamp"),
        Input("fill-event", "data"),
        State("forecast-table", "data"),
        State("saved-values", "data"),
        State("selected-end", "data"),
        State("active-format", "data"),
        prevent_initial_call=True,
    )
    def update_editor(_clicks, fmt, _edited, fill_event, current_rows, saved, end, previous_fmt):
        saved = {"levels": dict((saved or {}).get("levels", {})),
                 "mom": dict((saved or {}).get("mom", {}))}
        # Capture current visible edits before changing horizon or input format.
        for i, row in enumerate(current_rows or []):
            value = row.get("value")
            if value is None or value == "":
                saved[previous_fmt].pop(str(i), None)
            else:
                saved[previous_fmt][str(i)] = value

        triggered = ctx.triggered_id
        if triggered == "fill-event":
            # Copy the source cell's value into every cell along the dragged range.
            # Never interpolate or extrapolate a sequence.
            source, target = int(fill_event["source"]), int(fill_event["target"])
            if (0 <= source < len(current_rows or []) and
                    0 <= target < len(current_rows or [])):
                source_value = current_rows[source].get("value")
                if source_value is not None and source_value != "":
                    filled = [dict(row) for row in current_rows]
                    for i in range(min(source, target), max(source, target) + 1):
                        filled[i]["value"] = source_value
                        filled[i]["difference"] = format_difference(source_value, i, previous_fmt)
                        saved[previous_fmt][str(i)] = source_value
                    return filled, saved, no_update, no_update, no_update
            return no_update, saved, no_update, no_update, no_update
        if isinstance(triggered, dict) and triggered.get("type") == "month":
            end = int(triggered["index"])
        columns = editor_columns(fmt)
        # A table edit only needs to update the saved state; do not overwrite the
        # DataTable while someone is typing or pasting into it.
        if triggered == "forecast-table":
            # Refresh read-only differences without replacing an actively edited cell.
            return no_update, saved, no_update, no_update, no_update
        return table_rows(end, saved, fmt), saved, end, fmt, columns


    @app.callback(
        Output({"type": "month", "index": ALL}, "className"),
        Output("selection-summary", "children"),
        Input("selected-end", "data"),
    )
    def show_selection(end):
        classes = ["month-button selected" if i <= end else "month-button" for i in range(len(months))]
        return classes, f"{months[0]:%B %Y} - {months[end]:%B %Y} - {end + 1} months"


    # Compute the read-only difference immediately after edits and drag-to-fill.
    # This callback updates only the difference cells through a patch, preserving
    # the active editable value cell and its focus.
    @app.callback(
        Output("forecast-table", "data", allow_duplicate=True),
        Input("forecast-table", "data_timestamp"),
        State("forecast-table", "data"),
        State("format", "value"),
        prevent_initial_call=True,
    )
    def refresh_differences(_timestamp, rows, fmt):
        from dash import Patch
        patch = Patch()
        for i, row in enumerate(rows or []):
            difference = format_difference(row.get("value"), i, fmt)
            if row.get("difference") != difference:
                patch[i]["difference"] = difference
        return patch
