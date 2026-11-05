"""Forecast input columns, values, and difference formatting."""
from variables.nonfarm_employment.data_view import months, spf_levels, spf_mom

# Defines the four headers in the U.S. premise spreadsheet.
# fmt="levels" uses thousands; fmt="mom" uses percent/percentage points.
# Column ids (month/spf/value/difference) are used by Dash callbacks and
# must remain synchronized with callbacks/nonfarm_editor.py and callbacks/nonfarm_forecast.py.
def editor_columns(fmt):
    unit = "thousands" if fmt == "levels" else "%"
    return [
        {"name": "Month", "id": "month", "editable": False},
        {"name": f"SPF ({unit})", "id": "spf", "editable": False},
        {"name": f"Yours ({unit})", "id": "value", "type": "numeric", "editable": True},
        {"name": "Difference (thousands)" if fmt == "levels" else "Difference (pp)",
         "id": "difference", "editable": False},
    ]

# Calculates the read-only Difference column: Yours minus SPF.
# Called when building the table and when editing or filling cells.
def format_difference(value, i, fmt):
    """Display user minus SPF in the units of the selected input format."""
    if value is None or str(value).strip() == "":
        return ""
    try:
        # Use the unrounded SPF reference, not its formatted display string.
        benchmark = float(spf_levels.iloc[i]) if fmt == "levels" else float(spf_mom[i])
        difference = float(str(value).replace(",", "")) - benchmark
        return f"{difference:+,.3f}" if fmt == "levels" else f"{difference:+.4f}"
    except (TypeError, ValueError):
        return ""


# Constructs the visible table rows, from the first forecast month through
# the selected endpoint (inclusive). saved stores entries separately by
# format; each row uses the same keys as editor_columns().
def table_rows(end, saved, fmt):
    # The SPF column is display-only; "value" is the editable user input.
    # "difference" is derived from that input, not stored independently.
    values = saved.get(fmt, {})
    return [{"month": months[i].strftime("%b %Y"),
             "spf": f"{spf_levels.iloc[i]:,.3f}" if fmt == "levels" else f"{spf_mom[i]:.4f}%",
             "value": values.get(str(i)),
             "difference": format_difference(values.get(str(i)), i, fmt)}
            for i in range(end + 1)]
