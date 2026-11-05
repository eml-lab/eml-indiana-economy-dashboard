"""Indiana STATE population counterfactual, faithfully adapted from Pop_forecast.ipynb.

The model, bandwidth selection, fixed ECM lags, and recursive estimation
are unchanged. County forecasts are not recomputed here.
"""
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LassoLarsIC
from sklearn.preprocessing import StandardScaler

POP_FILE = Path(__file__).resolve().parents[2] / "data" / "population" / "Pop.xlsx"
EST_START, FC_END = 1970, 2029
TAU, TRIM, MAXLAG = 5, 0.05, 5
FC_LAGS = ["dy_lag1", "dy_lag2", "dy_lag5", "dln_US_lag4", "dln_US_lag5"]
Y, X = "ln_IN", "ln_US"

def epanechnikov(u):
    return np.where(np.abs(u) <= 1.0, 0.75 * (1.0 - u ** 2), 0.0)

def make_df(x_series, y_end, in_pop):
    yrs = range(EST_START, int(x_series.index.max()) + 1)
    d = pd.DataFrame({"Year": list(yrs)})
    d[Y] = np.log(in_pop.reindex(yrs).where(lambda s: s.index <= y_end)).values
    d[X] = np.log(x_series.reindex(yrs)).values
    return d

def _local_ls(W, Xm, y, cond_max=1e12):
    n, k = Xm.shape
    S = (W @ (Xm[:, :, None] * Xm[:, None, :]).reshape(n, k * k)).reshape(-1, k, k)
    b = W @ (Xm * y[:, None]); beta = np.full(b.shape, np.nan)
    ok = (W.sum(axis=1) > 0) & (np.linalg.cond(S) < cond_max)
    if ok.any(): beta[ok] = np.linalg.solve(S[ok], b[ok][..., None])[..., 0]
    return beta

def _design(df):
    y = df[Y].astype(float).values; x = df[X].astype(float).values
    return y, np.column_stack([np.ones(len(y)), x - x.mean()])

def select_bw(df, tau=TAU, trim=TRIM, n_grid=60):
    # LMCV: leave-(2 tau + 1)-out CV, trimmed; grid floor 3(tau+2)/n
    y, Xm = _design(df); n = len(y); r = np.arange(1, n + 1) / n; idx = np.arange(n)
    w = (r >= trim) & (r <= 1 - trim); grid = np.geomspace(max(3.0 * (tau + 2) / n, 0.02), 1.0, n_grid)
    def cv(bw):
        W = epanechnikov((r[:, None] - r[None, :]) / bw); W[np.abs(idx[:, None] - idx[None, :]) <= tau] = 0.0
        e = y[w] - np.sum(_local_ls(W[w], Xm, y) * Xm[w], axis=1)
        return np.sum(e ** 2) / n if np.all(np.isfinite(e)) else np.inf
    return grid[np.argmin([cv(b) for b in grid])] * n            # bandwidth in years

def fit_cr(df, bwy):
    y, Xm = _design(df); n = len(y); r = np.arange(1, n + 1) / n
    B = _local_ls(epanechnikov((r[:, None] - r[None, :]) / (bwy / n)), Xm, y)
    return pd.Series(y - np.sum(B * Xm, axis=1), index=df.index)  # u_hat

def fit_ecm(df, u_hat, crit=None, fixed=None, max_lag=MAXLAG):
    dy, dx = df[Y].diff(), df[X].diff()
    e = pd.DataFrame({"dy": dy, "u_lag1": u_hat.shift(1)}, index=df.index)
    lag_cols = []
    for i in range(1, max_lag + 1): e[f"dy_lag{i}"] = dy.shift(i); lag_cols.append(f"dy_lag{i}")
    for j in range(1, max_lag + 1): e[f"d{X}_lag{j}"] = dx.shift(j); lag_cols.append(f"d{X}_lag{j}")
    e = e.dropna()
    if fixed is None:     # LASSO after partialling out constant and u_lag1, standardized lags
        F = sm.add_constant(e[["u_lag1"]], has_constant="add").values
        res = lambda a: np.asarray(a, float) - F @ np.linalg.lstsq(F, np.asarray(a, float), rcond=None)[0]
        Z = StandardScaler().fit_transform(e[lag_cols])
        coef = LassoLarsIC(criterion=crit, fit_intercept=False).fit(
            np.column_stack([res(Z[:, k]) for k in range(Z.shape[1])]), res(e["dy"])).coef_
        sel = [c for c, b in zip(lag_cols, coef) if abs(b) > 1e-8]
    else:
        sel = list(fixed)
    mod = sm.OLS(e["dy"], sm.add_constant(e[["u_lag1"] + sel], has_constant="add")).fit()
    mod.selected_lags = sel
    return mod

def recursive_forecast(df, H, bwy, crit="bic", fixed=None, max_lag=MAXLAG):
    # lags chosen once on the T0 sample (or fixed), then CR + ECM re-estimated each step on data known so far
    d = df.reset_index(drop=True).copy(); T0 = int(d[Y].notna().sum()); dx = d[X].diff()
    sel = fixed if fixed is not None else fit_ecm(d.iloc[:T0], fit_cr(d.iloc[:T0], bwy), crit=crit, max_lag=max_lag).selected_lags
    for step in range(H):
        T = T0 + step; known = d.iloc[:T]; u = fit_cr(known, bwy)
        mod = fit_ecm(known, u, fixed=sel, max_lag=max_lag); dy = known[Y].diff()
        row = {"const": 1.0, "u_lag1": u.iloc[-1],
               **{f"dy_lag{i}": dy.iloc[-i] for i in range(1, max_lag + 1)},
               **{f"d{X}_lag{j}": dx.iloc[T - j] for j in range(1, max_lag + 1)}}
        d.loc[T, Y] = known[Y].iloc[-1] + float(mod.predict(pd.DataFrame([row]).reindex(columns=mod.params.index)).iloc[0])
    return d, sel

fmt_lags = lambda sel: "dy " + (",".join(c[6:] for c in sel if c.startswith("dy_")) or "-") + " / dx " + \
                       (",".join(c.split("_lag")[1] for c in sel if c.startswith(f"d{X}")) or "-")

@lru_cache(maxsize=1)
def _historical_inputs():
    pop = pd.read_excel(POP_FILE, sheet_name="Sheet1", index_col=0)
    us_act = pop["US_actual"].dropna()
    us_proj = pop["US_forecast"].dropna()
    in_pop = pop["Indiana"].dropna()
    last = int(us_act.index.max())
    # Original notebook: shift the U.S. projection to the last actual level in logs.
    shift = np.log(us_act.loc[last]) - np.log(us_proj.loc[last])
    us_path = pd.concat([us_act, np.exp(np.log(us_proj.loc[last + 1:FC_END]) + shift)])
    historical = make_df(us_path.loc[:FC_END], last, in_pop)
    bandwidth = select_bw(historical.iloc[:int(historical[Y].notna().sum())])
    return us_act, in_pop, us_path, last, float(bandwidth)


def run_state_population_counterfactual(alternative_us):
    """Return Indiana levels indexed by forecast year for a complete alternative U.S. path.

    alternative_us: mapping year -> U.S. population in persons, 2026–2029.
    No extrapolation, model changes, or county forecasts.
    """
    us_act, in_pop, us_path, last, bandwidth = _historical_inputs()
    years = list(range(last + 1, FC_END + 1))
    if set(map(int, alternative_us)) != set(years):
        raise ValueError(f"Provide U.S. population levels for all forecast years: {years}.")
    values = pd.Series({int(k): float(v) for k, v in alternative_us.items()}).sort_index()
    if not np.isfinite(values.to_numpy()).all() or (values <= 0).any():
        raise ValueError("All U.S. population levels must be finite and positive.")
    path = pd.concat([us_act, values])
    d = make_df(path.loc[:FC_END], last, in_pop)
    n = int(d[Y].notna().sum())
    result, _ = recursive_forecast(d, len(d) - n, bandwidth, fixed=FC_LAGS)
    return np.exp(result.set_index("Year")[Y]).loc[years]
