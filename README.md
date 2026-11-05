# Indiana forecasting dashboard

Run `pip install -r requirements.txt` then `python app.py` from this directory.

## Forecast variables

- **Nonfarm Employment**: existing monthly statewide counterfactual and LASSO BIC model, unchanged mathematically.
- **Population**: statewide annual counterfactual and county forecasts, unchanged.
- **Total Employment**: not yet implemented; reserve this as a separate future variable/model.

## Nonfarm employment files

- `nonfarm_forecasting.py` — original `forecasting.py`, renamed without altering its calculations.
- `nonfarm_data_view.py` — original `data_view.py`.
- `components/nonfarm_layout.py`, `nonfarm_calendar.py`, `nonfarm_spreadsheet.py`, `nonfarm_charts.py` — nonfarm employment UI.
- `callbacks/nonfarm_editor.py`, `nonfarm_forecast.py` — nonfarm employment callbacks.
- `CES_Employment.xlsx`, `SPF_median.xlsx` — original model inputs; filenames preserved to avoid changing data loading.

## Population files

- `population_data.py`, `population_counterfactual.py`, `county_map.py`
- `components/population.py`, `callbacks/population.py`
- `data/Pop.xlsx`, `data/Pop_IN_county_forecast.xlsx`, `data/indiana_counties.geojson`, `data/indiana_county_fips.json`

## Shared files

- `app.py`, `config.py`, `components/dashboard.py`, `callbacks/navigation.py`, `assets/`

The variable selector uses the internal value `nonfarm_employment` (not `employment`) to distinguish it from future Total Employment. The existing spreadsheet/callback IDs remain unchanged to preserve behavior.


## Additional LAUS forecast pages
Select **Total Employment** or **Unemployment Rate** in the variable selector.
Both pages use only the `forecast` sheets in the corresponding workbooks under `data/`,
showing monthly October 2026–September 2029 forecasts (not OOS or September 2026 actuals).
Statewide and county views are available. County selection supports the existing map,
search and reset interactions. Total Employment sums selected county forecasts only
when every selected county has a reported value for that month; otherwise the total
is `N/A`. Unemployment rates are never summed. Missing values remain `N/A`.
No counterfactuals are calculated for these two variables.

New code: `laus_data.py`, `components/laus.py`, `callbacks/laus.py`.
New data: `data/LAUS_E_IN_county_forecast.xlsx`,
`data/LAUS_UR_IN_county_forecast.xlsx`.

## GDP forecast page
The **GDP** selector displays quarterly Indiana GDP forecasts and the corresponding U.S. path for 2026Q3–2029Q4, both in **millions of dollars**. The chart uses separate Indiana and U.S. vertical axes and the table reports the same forecast values. Data are read from `data/GDP_IN_forecast.xlsx`, sheet `IN_forecast_2026Q3_2029Q4`, excluding its 2026Q2 actual row and all OOS sheets. This page is display-only, without county forecasts or counterfactuals. Modules: `gdp_data.py`, `components/gdp.py`.

## Wages and Salaries
Select **Wages and Salaries** for quarterly 2026Q2–2029Q1 state and county forecasts.
Only the forecast sheets of `data/QCEW_W_IN_county_forecast.xlsx` are used; OOS and
2026Q1 actuals are excluded. Units are provisionally **millions of dollars** as supplied.
County map, search, and reset reuse the existing interface. Selected county wages
can be summed; a combined value is N/A if any selected county forecast is missing.
The three summary rows in the county sheet are excluded from the county selector.
No counterfactual calculations are performed.


## Modular project layout (November 2026)

- `app.py`, `config.py`: entry point and shared settings. Run `python app.py` from the project root.
- `variables/<variable>/`: variable-specific layout, data loader, callbacks, and model where present.
- `shared/dashboard.py`, `shared/navigation.py`: variable selector and page visibility.
- `shared/county_map.py`: geographic lookup and reusable interactive county map.
- `shared/county_forecast.py`, `shared/county_callbacks.py`: common county/state display and interactions for total employment, unemployment rate, and wages/salaries.
- `shared/laus_data.py`: shared LAUS workbook reader, with adapters under `variables/total_employment/` and `variables/unemployment_rate/`.
- `data/<variable>/`: original workbooks, grouped by forecast variable; `data/geography/` contains map resources.
- `assets/`: existing Dash CSS and JavaScript, unchanged.

This refactor changes file locations and imports only; forecasting calculations and Dash component IDs remain unchanged.
