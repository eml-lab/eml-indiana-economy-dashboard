Copy files into your existing indiana_forecasting_dashboard project, preserving paths:

  population_counterfactual.py       (new, beside app.py)
  components/population.py          (replace)
  callbacks/population.py           (replace)
  data/Pop.xlsx                     (new, historical model input from supplied Pop_1105 notebook)

The existing data/Pop_IN_county_forecast.xlsx remains required.
No changes to employment files, county geography files, or other callbacks.

STATE: Baseline from published workbook; user enters U.S. population levels in persons for all 2026–2029 years, clicks Generate, and gets recursively recomputed Indiana forecast.
COUNTIES: unchanged, display-only.
The original notebook's bandwidth selection, time-varying CR, fixed ECM lag specification, and recursive refitting are retained.
The 2026 U.S. input does not affect Indiana 2026; the 2029 U.S. input cannot affect Indiana within 2026–2029.
