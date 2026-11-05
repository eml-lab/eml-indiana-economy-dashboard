"""Forecasting backend. Estimation/LTHF functions copied verbatim from counterfactual(2).ipynb.
The only additions are filesystem setup, scenario orchestration, and validation.
"""
from pathlib import Path
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.api as sm
from sklearn.linear_model import LassoLarsIC
from sklearn.preprocessing import StandardScaler
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[2]
Path(ROOT / "Figure").mkdir(exist_ok=True)

# ===== ORIGINAL NOTEBOOK CELL 1 (UNCHANGED) =====
# ── settings ────────────────────────────────────────────────
CES_FILE = ROOT / "data" / "nonfarm_employment" / "CES_Employment.xlsx"
SPF_FILE = ROOT / "data" / "nonfarm_employment" / "SPF_median.xlsx"

US_ID = "CES0000000001"
IN_ID = "SMS18000000000000001"

SURVEY   = None      # None = most recent survey, or (YEAR, QUARTER) for a specific survey
USE_EMPB = True      # True = use Employment B (next-year annual) to add the implied 4th quarter
SAVE_FIG = True      # False: do not save figures
FIG_DIR  = "Figure"
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.3})

# Data load
#  row 1 = series_id header, row 2 = name → skip
ces = pd.read_excel(CES_FILE, sheet_name="Data", header=0, skiprows=[1], index_col=0)
ces.index = pd.to_datetime(ces.index)
us = ces[US_ID].astype(float).dropna()
us.index.freq = "MS"
last_obs = us.index[-1]
print(f"US monthly: {us.index[0]:%Y-%m} ~ {last_obs:%Y-%m}, {len(us)} obs")

# SPF
spf = pd.read_excel(SPF_FILE, sheet_name="EMP")
spf = spf.dropna(subset=["EMP2"])
row = spf.iloc[-1] if SURVEY is None else spf[(spf.YEAR == SURVEY[0]) & (spf.QUARTER == SURVEY[1])].iloc[0]
Y, Q = int(row.YEAR), int(row.QUARTER)
survey_q = pd.Period(f"{Y}Q{Q}", freq="Q")
print(f"SPF survey: {survey_q}")
row

in_emp = ces[IN_ID].dropna().astype(float)    # Indiana monthly total employment (thousands)

# ===== ORIGINAL NOTEBOOK CELL 2 (UNCHANGED) =====
# quarterly targets: EMPk → survey quarter + (k-2),  k = 2..6
qt = pd.DataFrame({
    "quarter": [survey_q + (k - 2) for k in range(2, 7)],
    "col": [f"EMP{k}" for k in range(2, 7)],
    "spf": [float(row[f"EMP{k}"]) for k in range(2, 7)],
}).set_index("quarter")

# annual target: next year only
at = pd.DataFrame({"col": ["EMPB"], "spf": [float(row.EMPB)]}, index=pd.Index([Y + 1], name="year"))

# actual quarterly averages (current vintage), with month counts
qa = us.groupby(us.index.to_period("Q")).agg(["mean", "count"])
qa.columns = ["actual_avg", "n_months"]
qt = qt.join(qa)

LTHF_P = 4          # number of lagged quarters (4 = 1 year)
EXCLUDE      = ("2020-04-01", "2020-06-01")
LTHF_EXCLUDE = None  # quarters overlapping this window (as target or lag) are excluded from estimation; None = no exclusion
QN = 3              # months per quarter

def quarter_wide(m):
    """monthly Series -> rows = quarter (Period), columns = position within quarter 1..3"""
    d = m.to_frame("y")
    d["q"] = d.index.to_period("Q")
    d["j"] = (d.index.month - 1) % 3 + 1
    return d.pivot(index="q", columns="j", values="y").reindex(columns=range(1, QN + 1))

def lag_names(p):
    return [f"L{k}_m{l}" for k in range(1, p + 1) for l in range(1, QN + 1)]

def lthf_panel(m, p=LTHF_P, exclude=LTHF_EXCLUDE):
    """estimation panel: only quarters where the target quarter and all p lagged quarters have all 3 months observed"""
    W = quarter_wide(m)
    full = W.dropna()
    ex = set()
    if exclude is not None:
        ex = set(pd.period_range(pd.Period(exclude[0], "Q"), pd.Period(exclude[1], "Q"), freq="Q"))
    rows = []
    for i in full.index:
        need = [i - k for k in range(0, p + 1)]
        if all(x in full.index for x in need) and not any(x in ex for x in need):
            lags = [full.loc[i - k, l] for k in range(1, p + 1) for l in range(1, QN + 1)]
            rows.append([i, *full.loc[i].values, full.loc[i].sum(), *lags])
    cols = ["q", *[f"y{j}" for j in range(1, QN + 1)], "y_tot", *lag_names(p)]
    return pd.DataFrame(rows, columns=cols).set_index("q")

def fit_model1(P, p=LTHF_P):
    """Model 1: alpha_j is equation-specific, beta_{k,l} is common -> stack the 3 equations and run OLS once"""
    Ym = P[[f"y{j}" for j in range(1, QN + 1)]].values          # (n, 3)
    tot = P["y_tot"].values
    L = P[lag_names(p)].values                                  # (n, 3p)
    n = len(P)
    X = np.zeros((n * QN, QN + L.shape[1]))
    for j in range(QN):
        X[j * n:(j + 1) * n, j] = tot                           # alpha_j column
        X[j * n:(j + 1) * n, QN:] = L                           # common beta column
    b = np.linalg.lstsq(X, Ym.T.reshape(-1), rcond=None)[0]
    alpha, beta = b[:QN], b[QN:]
    return dict(alpha=alpha, B=np.tile(beta, (QN, 1)), beta=beta)

def fit_model2(P, p=LTHF_P):
    """Model 2: separate OLS for each equation (same regressors: y_i and 3p lags)"""
    X = np.column_stack([P["y_tot"].values, P[lag_names(p)].values])
    coefs = np.array([np.linalg.lstsq(X, P[f"y{j}"].values, rcond=None)[0] for j in range(1, QN + 1)])
    return dict(alpha=coefs[:, 0], B=coefs[:, 1:])

def lthf_fitted(model, P, p=LTHF_P):
    F = model["alpha"][None, :] * P["y_tot"].values[:, None] + P[lag_names(p)].values @ model["B"].T
    return pd.DataFrame(F, index=P.index, columns=[f"y{j}" for j in range(1, QN + 1)])

def to_monthly(Qdf):
    """quarter x position table -> monthly Series"""
    s = Qdf.stack()
    idx = [pd.Timestamp(q.start_time) + pd.DateOffset(months=int(str(j)[-1]) - 1) for q, j in s.index]
    return pd.Series(s.values, index=pd.DatetimeIndex(idx)).sort_index()

def lthf_forecast(model, m_obs, targets, p=LTHF_P):
    """targets: Series (index = quarter Period, values = quarterly 'average' forecast)
    for each quarter in order: lags (actual or previously forecast months) -> y_hat, already observed months are held fixed,
    the remaining gap (3 x target - observed sum - unobserved y_hat sum) is spread evenly over the unobserved months"""
    W = quarter_wide(m_obs)
    out = []
    for qq, avg in targets.sort_index().items():
        tot = QN * avg
        obs = W.loc[qq] if qq in W.index else pd.Series(np.nan, index=range(1, QN + 1))
        if obs.notna().all():
            continue
        lagv = np.array([W.loc[qq - k, l] for k in range(1, p + 1) for l in range(1, QN + 1)])
        yhat = model["alpha"] * tot + model["B"] @ lagv
        rem = obs.isna().values
        gap = tot - obs[~rem].sum() - yhat[rem].sum()
        yhat_rem = yhat[rem] + gap / rem.sum()
        row = obs.values.copy(); row[rem] = yhat_rem
        W.loc[qq] = row
        out.append(pd.Series(yhat_rem, index=[pd.Timestamp(qq.start_time) + pd.DateOffset(months=int(j) - 1)
                                               for j in np.arange(1, QN + 1)[rem]]))
    return pd.concat(out).sort_index()

# estimation panel + forecast targets (SPF quarterly averages; if USE_EMPB, add the implied Q4 of next year)
P_q = lthf_panel(us)
targets_q = qt["spf"].copy()
if USE_EMPB:
    q_last = pd.Period(f"{Y+1}Q4", freq="Q")
    known = [targets_q[pd.Period(f"{Y+1}Q{i}", freq="Q")] for i in range(1, 4) if pd.Period(f"{Y+1}Q{i}", freq="Q") in targets_q.index]
    if q_last not in targets_q.index and len(known) == 3:
        targets_q[q_last] = 4 * at.loc[Y + 1, "spf"] - sum(known)
targets_q = targets_q.sort_index()
print(f"Estimation sample: {P_q.index[0]} ~ {P_q.index[-1]}, n = {len(P_q)} quarters (p = {LTHF_P}, excluded window = {LTHF_EXCLUDE})")
print(f"Forecast targets: {targets_q.index[0]} ~ {targets_q.index[-1]}")

# ===== ORIGINAL NOTEBOOK CELL 3 (UNCHANGED) =====
# compare
# Run first: 1 (settings), 3(us), the LTHF common cell above (function definitions: lthf_panel, fit_model2, lthf_fitted, to_monthly)
# Fitted value: y_ij_hat = alpha_j * y_i + sum_{k,l} beta_{j,k,l} * y_{i-k,l}

EXCLUDE = ("2020-04-01", "2020-06-01")  # quarters excluded from estimation (as target or lag)
EVAL_START  = "2010-01-01"                     # start of evaluation for tables/figures (estimation uses all of us)
TARGET_DROP = ("2020Q2", "2020Q2")

SPECS = {"excl (EXCLUDE)": (EXCLUDE, None),
         "all":            (None, None),
         "target-only":    (None, TARGET_DROP)}
col = {"excl (EXCLUDE)": "tab:red", "all": "tab:blue", "target-only": "tab:green"}

def est_panel(ex, drop):
    P = lthf_panel(us, exclude=ex)
    if drop is not None:
        a, b = pd.Period(drop[0], "Q"), pd.Period(drop[1], "Q")
        P = P.drop(index=[q for q in P.index if a <= q <= b])
    return P

P_full = lthf_panel(us, exclude=None)
act    = P_full[["y1", "y2", "y3"]]
mods, P_est = {}, {}
for name, (ex, drop) in SPECS.items():
    P_est[name] = est_panel(ex, drop)
    mods[name]  = fit_model2(P_est[name])
    print(f"{name:16s}: estimation quarters {len(P_est[name])} ({P_est[name].index[0]}~{P_est[name].index[-1]}), alpha = {np.round(mods[name]['alpha'], 4)}")

# monthly fit error (log %, fitted - actual)
ERR = {}
for name, mod in mods.items():
    fit = lthf_fitted(mod, P_full)
    ERR[name] = to_monthly((np.log(fit) - np.log(act)) * 100)
ERR = pd.DataFrame(ERR).loc[EVAL_START:]
q_of = ERR.index.to_period("Q")

def stats(e):
    return pd.Series({"MSE": (e ** 2).mean(), "RMSE": np.sqrt((e ** 2).mean()), "MAE": e.abs().mean(), "n": len(e)})

# quarters used in estimation by each model vs quarters not used
used = {}
for name in mods:
    in_est = np.isin(q_of, list(P_est[name].index))
    used[name] = pd.concat({"used in fit": stats(ERR.loc[in_est, name]),
                            "not used":    stats(ERR.loc[~in_est, name])}, axis=1).T

# ── zoom from 2025Q1: actual vs fitted ─────────────────────────────────────────────
ZOOM_START = pd.Timestamp("2025-01-01")
a0    = ZOOM_START - pd.DateOffset(months=1)
act_m = to_monthly(act).loc[a0:]
fit_m = {n: act_m * np.exp(ERR[n].reindex(act_m.index).fillna(0) / 100) for n in ERR}
lz = act_m.loc[ZOOM_START:].index
Z  = pd.DataFrame({n: ERR[n].loc[ZOOM_START:] for n in ERR})

# ── three panels in one row: (a) alpha_j, (b) level, (c) fit error ────────────────────
fig, axes = plt.subplots(1, 3, figsize=(26, 7), gridspec_kw={"width_ratios": [0.8, 1, 1]})

ax = axes[0]                                                     # (a) alpha comparison
names = list(mods); nm = len(names); w = 0.8 / nm
xi = np.arange(QN)
for i, n in enumerate(names):
    xs = xi + (i - (nm - 1) / 2) * w
    ax.bar(xs, mods[n]["alpha"], w, color=col[n], label=n)
    for x_, v in zip(xs, mods[n]["alpha"]):
        ax.text(x_, v + 0.005, f"{v:.3f}", ha="center", va="bottom", fontsize=8)
ax.axhline(1 / QN, color="gray", ls=":", lw=1, label="1/3 (equal split)")
ax.set_xticks(xi); ax.set_xticklabels([f"alpha_{j}" for j in range(1, QN + 1)])
ax.set_ylabel("alpha_j  (sum = 1)"); ax.set_title("(a) LTHF alpha_j by COVID treatment"); ax.legend(fontsize=8)

ax = axes[1]                                                     # (b) log level
ax.plot(np.log(act_m.loc[lz]), "k-o", ms=4, lw=1.8, label="Actual")
for n in fit_m:
    ax.plot(lz, np.log(fit_m[n].loc[lz]), color=col[n], ls="--", marker="o", ms=3, label=f"fitted | {n}")
ax.set_ylabel("log(US nonfarm employment)"); ax.set_title("(b) Level: actual vs fitted"); ax.legend(fontsize=8)

ax = axes[2]                                                     # (c) fit error
for n in Z:
    ax.plot(Z.index, Z[n], color=col[n], marker="o", ms=3, label=f"{n} (RMSE {np.sqrt((Z[n]**2).mean()):.3f})")
ax.axhline(0, color="gray", lw=0.8)
ax.set_ylabel("log % (fitted − actual)"); ax.set_title("(c) Fit error"); ax.legend(fontsize=8)

for a in axes[1:]: plt.setp(a.get_xticklabels(), rotation=45, ha="right")

fig.tight_layout()
fig.savefig("Figure/LTHF_modified.png", dpi=200, bbox_inches="tight")
plt.show()

# ===== ORIGINAL NOTEBOOK CELL 4 (UNCHANGED) =====
US_EXT = "target-only"      # US path used in the Indiana forecast: "all" | "excl (EXCLUDE)" | "target-only"

lthf = {}
for name, mod in mods.items():
    lthf[name] = {"model":  mod,
                  "fitted": lthf_fitted(mod, P_est[name]),
                  "path":   lthf_forecast(mod, us, targets_q)}

p = lthf[US_EXT]["path"]
print(f"US_EXT = {US_EXT!r}: alpha = {np.round(mods[US_EXT]['alpha'], 4)}, "
      f"path {p.index[0]:%Y-%m} ~ {p.index[-1]:%Y-%m} ({len(p)} months)")

# ===== ORIGINAL NOTEBOOK CELL 5 (UNCHANGED) =====
# ── 3.1 kernel TVC cointegrating regression (Epanechnikov, LMCV bandwidth) ─────────────
def epanechnikov(u):
    return np.where(np.abs(u) <= 1.0, 0.75 * (1.0 - u ** 2), 0.0)


def _local_ls(W, X, y, cond_max=1e12):
    """row-wise weighted LS: W (m, n), X (n, k), y (n,) -> beta (m, k). NaN if singular."""
    n, k = X.shape
    XX = (X[:, :, None] * X[:, None, :]).reshape(n, k * k)
    S = (W @ XX).reshape(-1, k, k)
    b = W @ (X * y[:, None])
    beta = np.full(b.shape, np.nan)
    ok = (W.sum(axis=1) > 0) & (np.linalg.cond(S) < cond_max)
    if ok.any():
        beta[ok] = np.linalg.solve(S[ok], b[ok][..., None])[..., 0]
    return beta


def _design(df, y_col, x_cols):
    """X = (1, x - mean(x)): centering improves the condition number. Slopes unchanged; intercept mapped back to the original scale."""
    y = df[y_col].astype(float).values
    Xraw = df[x_cols].astype(float).values
    xbar = Xraw.mean(axis=0)
    X = np.column_stack([np.ones(len(y)), Xraw - xbar])
    return y, X, xbar


def lmcv_score(y, X, bw, tau=3, trim=0.05):
    """CV(h) = (1/n) sum_t (y_t - beta°_t(t/n)'x_t)^2 w(t/n),  beta°_t: excludes t-tau..t+tau"""
    n = len(y)
    r = np.arange(1, n + 1) / n
    idx = np.arange(n)
    W = epanechnikov((r[:, None] - r[None, :]) / bw)
    W[np.abs(idx[:, None] - idx[None, :]) <= tau] = 0.0      # leave-(2tau+1)-out
    w = (r >= trim) & (r <= 1 - trim)
    beta = _local_ls(W[w], X, y)
    e = y[w] - np.sum(beta * X[w], axis=1)
    if not np.all(np.isfinite(e)):
        return np.inf
    return np.sum(e ** 2) / n


def default_bw_grid(n, tau=3, n_grid=60):
    lo = max(3.0 * (tau + 2) / n, 0.02)        # too small an h leaves an empty window after leave-out -> singular matrix
    return np.geomspace(lo, 1.0, n_grid)


def select_bw(y, X, grid=None, tau=3, trim=0.05):
    grid = default_bw_grid(len(y), tau) if grid is None else np.asarray(grid)
    cv = np.array([lmcv_score(y, X, b, tau, trim) for b in grid])
    return grid[np.argmin(cv)], pd.Series(cv, index=grid, name="CV")


def fit_kernel_cr(df, y_col, x_cols, bw=None, tau=18, trim=0.05, grid=None):
    """Step 1-2: kernel(Epanechnikov) TVC cointegrating regression.
    if bw=None, select by LMCV. Returns: dict(bw, cv, alpha, beta{x}, fitted, u_hat)"""
    y, X, xbar = _design(df, y_col, x_cols)
    cv = None
    if bw is None:
        bw, cv = select_bw(y, X, grid, tau, trim)
    n = len(y)
    r = np.arange(1, n + 1) / n
    B = _local_ls(epanechnikov((r[:, None] - r[None, :]) / bw), X, y)   # beta(t/n), t = 1..n
    fitted = np.sum(B * X, axis=1)
    alpha = B[:, 0] - B[:, 1:] @ xbar                                    # intercept on the original scale
    return {
        "bw": bw, "cv": cv,
        "alpha": pd.Series(alpha, index=df.index),
        "beta": {x: pd.Series(B[:, i + 1], index=df.index) for i, x in enumerate(x_cols)},
        "fitted": pd.Series(fitted, index=df.index),
        "u_hat": pd.Series(y - fitted, index=df.index),
    }

def fit_cr_split(df_k, y_col, x_cols):
    """pre uses h_pre, post uses a window with the same number of months; estimated separately and concatenated (no linking/interpolation)"""
    X = x_cols[0]; mo = df_k["Month"]
    ip, io = np.where(mo <= PRE_END)[0], np.where(mo >= POST_START)[0]
    cr_a = fit_kernel_cr(df_k.iloc[ip], y_col, x_cols, bw=h_pre)
    h_b  = h_pre * len(ip) / len(io) if H_MODE == "months" else h_pre
    cr_b = fit_kernel_cr(df_k.iloc[io], y_col, x_cols, bw=h_b)
    alpha = pd.concat([cr_a["alpha"], cr_b["alpha"]]).reindex(df_k.index)
    beta  = pd.concat([cr_a["beta"][X], cr_b["beta"][X]]).reindex(df_k.index)
    fitted = alpha + beta * df_k[X]
    return {"bw": h_pre, "alpha": alpha, "beta": {X: beta}, "fitted": fitted, "u_hat": df_k[y_col] - fitted}

# ===== ORIGINAL NOTEBOOK CELL 6 (UNCHANGED) =====
# ── 3.2 settings + data: actual Indiana + LTHF-expanded US path ─────────────────────────
# Run first: 2(us, in_emp, lthf, US_EXT)
Y_IN, X_IN   = "ln_IN", "ln_US"     # column names: log Indiana, log US
EST_START    = "1990-01-01"         # start of estimation sample
BW_GRID      = None                 # None = default_bw_grid(n, tau)
PLOT_START_M = "2024-01-01"
EXT_NAME     = f"LTHF {US_EXT}"

us_path = pd.concat([us, lthf[US_EXT]["path"]])
us_path = us_path[~us_path.index.duplicated(keep="first")]

df_sh = pd.DataFrame({Y_IN: np.log(in_emp), X_IN: np.log(us_path)}).sort_index()
df_sh = df_sh.loc[EST_START: us_path.index[-1]]
df_sh = df_sh.loc[df_sh[[Y_IN, X_IN]].dropna().index[0]:]
df_sh.index.name = "Month"
df_sh = df_sh.reset_index()
T0_sh = int(df_sh[Y_IN].notna().sum())          # number of actual Indiana observations
H_sh  = len(df_sh) - T0_sh                      # number of forecast months up to the end of the US path
print(f"US extension: {EXT_NAME}, end {df_sh.Month.iloc[-1]:%Y-%m} -> Indiana forecast H = {H_sh} months")

# ===== ORIGINAL NOTEBOOK CELL 7 (UNCHANGED) =====
# ── 4.1 Beta: estimated separately before 2020-03 / after 2020-04 (no discarded window, no spline) ──────────────
# Run first: 3.1 functions(fit_kernel_cr), 3.2(df_sh, T0_sh, Y_IN, X_IN, BW_GRID)
TAU_B, TRIM_B = 18, 0.05
PRE_END    = pd.Timestamp("2020-03-01")   # last month of the pre sample (cut here to select h)
POST_START = pd.Timestamp("2020-04-01")   # first month of the post sample
H_MODE     = "months"                     # "months": same number of months (h_post = h_pre x n_pre / n_post) | "fraction": same h
bw_lab     = lambda bw, n: f"h = {bw:.4f} (±{bw * n:.0f} months)"

act = df_sh.iloc[:T0_sh]                  # actual Indiana span
m   = act["Month"]
i_pre, i_post = np.where(m <= PRE_END)[0], np.where(m >= POST_START)[0]
pre, post = act.iloc[i_pre], act.iloc[i_post]

cr_pre = fit_kernel_cr(pre, Y_IN, [X_IN], bw=None, tau=TAU_B, trim=TRIM_B, grid=BW_GRID)   # pre: h selected by LMCV
h_pre  = cr_pre["bw"]
h_post = h_pre * len(pre) / len(post) if H_MODE == "months" else h_pre
cr_post = fit_kernel_cr(post, Y_IN, [X_IN], bw=h_post)                                      # post: window with the same number of months

def fit_cr_split(df_k, y_col, x_cols):
    """pre uses h_pre, post uses a window with the same number of months; estimated separately and concatenated (no linking/interpolation)"""
    X = x_cols[0]; mo = df_k["Month"]
    ip, io = np.where(mo <= PRE_END)[0], np.where(mo >= POST_START)[0]
    cr_a = fit_kernel_cr(df_k.iloc[ip], y_col, x_cols, bw=h_pre)
    h_b  = h_pre * len(ip) / len(io) if H_MODE == "months" else h_pre
    cr_b = fit_kernel_cr(df_k.iloc[io], y_col, x_cols, bw=h_b)
    alpha = pd.concat([cr_a["alpha"], cr_b["alpha"]]).reindex(df_k.index)
    beta  = pd.concat([cr_a["beta"][X], cr_b["beta"][X]]).reindex(df_k.index)
    fitted = alpha + beta * df_k[X]
    return {"bw": h_pre, "alpha": alpha, "beta": {X: beta}, "fitted": fitted, "u_hat": df_k[y_col] - fitted}

cr4 = fit_cr_split(act, Y_IN, [X_IN])     # fit over the actual span (same as the separately estimated pre/post fits)
g = cr_pre["cv"].index
print(f"pre : {m.iloc[i_pre[0]]:%Y-%m} ~ {m.iloc[i_pre[-1]]:%Y-%m}, n = {len(pre)}, "
      f"{bw_lab(h_pre, len(pre))}{' [corner]' if h_pre in (g[0], g[-1]) else ''}")
print(f"post: {m.iloc[i_post[0]]:%Y-%m} ~ {m.iloc[i_post[-1]]:%Y-%m}, n = {len(post)}, "
      f"{bw_lab(h_post, len(post))}  (H_MODE = {H_MODE})")

# ===== ORIGINAL NOTEBOOK CELL 8 (UNCHANGED) =====
# ── 4.2 ECM lag selection (LassoLarsIC, BIC/AIC) + recursive forecast: LTHF-expanded US path -> β fit -> ECM ──────
# Run first: 4.1 (fit_cr_split, h_pre, df_sh, T0_sh, H_sh)
MAXLAG_L      = 12          # candidate LASSO lags (P = Q = 12)
CRITS         = ["bic", "aic"]
RESELECT_LAGS = False       # False: select lags once on the current actual sample (T0) and keep them fixed (only coefficients re-estimated) | True: reselect at every step
USE_D2005     = True        # include the 2020-05 dummy in the ECM (partialled out before selection)

def fit_ecm_lasso_ic(df_k, y_col, x_cols, u_hat, crit, max_lag, fixed=None):
    dy = df_k[y_col].diff()
    ecm = pd.DataFrame({"dy": dy, "u_lag1": u_hat.shift(1)}, index=df_k.index)
    lag_cols = []
    for i in range(1, max_lag + 1):
        c = f"dy_lag{i}"; ecm[c] = dy.shift(i); lag_cols.append(c)
    for x in x_cols:
        dx = df_k[x].diff()
        for j in range(1, max_lag + 1):
            c = f"d{x}_lag{j}"; ecm[c] = dx.shift(j); lag_cols.append(c)
    ctrl = ["u_lag1"]
    if USE_D2005:
        ecm["D2005"] = (df_k["Month"] == pd.Timestamp("2020-05-01")).astype(float); ctrl.append("D2005")
    ecm = ecm.dropna()
    if fixed is None:                          # lag selection (Frisch-Waugh: standardize after removing constant, u_lag1, D2005)
        F = sm.add_constant(ecm[ctrl], has_constant="add").values
        res = lambda a: np.asarray(a, float) - F @ np.linalg.lstsq(F, np.asarray(a, float), rcond=None)[0]
        y_r = res(ecm["dy"])
        Z = StandardScaler().fit_transform(ecm[lag_cols])
        Z_r = np.column_stack([res(Z[:, k]) for k in range(Z.shape[1])])
        coef = LassoLarsIC(criterion=crit, fit_intercept=False).fit(Z_r, y_r).coef_
        sel = [c for c, b in zip(lag_cols, coef) if abs(b) > 1e-6]
    else:
        sel = list(fixed)
    mod = sm.OLS(ecm["dy"], sm.add_constant(ecm[ctrl + sel], has_constant="add")).fit()   # re-estimate by OLS with the selected lags
    mod.selected_lags = sel
    return mod

def recursive_forecast_lasso(df_actual, y_col, x_cols, H, crit=None, max_lag=MAXLAG_L,
                             reselect=True, fixed_sel=None, date_col="Month"):
    df_work = df_actual.reset_index(drop=True).copy()
    T0 = int(df_work[y_col].notna().sum())
    dx_full = {x: df_work[x].astype(float).diff() for x in x_cols}
    sel_fixed = fixed_sel
    if sel_fixed is None and not reselect:     # select only once on the T0 sample
        k0 = df_work.iloc[:T0]
        sel_fixed = fit_ecm_lasso_ic(k0, y_col, x_cols, fit_cr_split(k0, y_col, x_cols)["u_hat"], crit, max_lag).selected_lags
    diag = []
    for step in range(1, H + 1):
        T = T0 + step - 1
        df_known = df_work.iloc[:T]
        cr  = fit_cr_split(df_known, y_col, x_cols)
        mod = fit_ecm_lasso_ic(df_known, y_col, x_cols, cr["u_hat"], crit, max_lag, fixed=sel_fixed)
        dy  = df_known[y_col].diff()
        row = {"const": 1.0, "u_lag1": cr["u_hat"].iloc[-1], "D2005": 0.0}
        for i in range(1, max_lag + 1): row[f"dy_lag{i}"] = dy.iloc[-i]
        for x in x_cols:
            for j in range(1, max_lag + 1): row[f"d{x}_lag{j}"] = dx_full[x].iloc[T - j]
        d_y = float(mod.predict(pd.DataFrame([row]).reindex(columns=mod.params.index)).iloc[0])
        df_work.loc[T, y_col] = df_known[y_col].iloc[-1] + d_y
        cr_new = fit_cr_split(df_work.iloc[:T + 1], y_col, x_cols)
        diag.append({"date": df_work[date_col].iloc[T], "ecm_model": mod, "selected": mod.selected_lags,
                     "u_hat_T": float(cr["u_hat"].iloc[-1]), "d_y_forecast": d_y,
                     "beta_path": {x: float(b.iloc[-1]) for x, b in cr_new["beta"].items()}})
    return df_work, diag

# ===== NEW ADAPTER CODE; DOES NOT MODIFY THE ORIGINAL FORECASTING FUNCTIONS =====
# Forecast specifications and calls follow the notebook's original execution cell.
FORECAST_SPECS = ("bic", "aic", "ols33")
FORECAST_LABELS = {"bic": "LASSO BIC", "aic": "LASSO AIC", "ols33": "OLS(3,3)"}
OLS33 = [f"dy_lag{i}" for i in range(1, 4)] + [f"d{X_IN}_lag{i}" for i in range(1, 4)]


def _run_specification(frame, horizon, spec):
    if spec == "ols33":
        # Exact original notebook OLS(3,3) invocation, with the scenario frame/horizon.
        result, _ = recursive_forecast_lasso(
            frame, Y_IN, [X_IN], H=horizon, fixed_sel=OLS33
        )
    elif spec in ("bic", "aic"):
        # Exact original notebook LASSO invocation, with the scenario frame/horizon.
        result, _ = recursive_forecast_lasso(
            frame, Y_IN, [X_IN], H=horizon, crit=spec, reselect=RESELECT_LAGS
        )
    else:
        raise ValueError(f"Unknown forecast specification: {spec}")
    return pd.Series(
        np.exp(result[Y_IN].iloc[T0_sh:].to_numpy()),
        index=pd.DatetimeIndex(result["Month"].iloc[T0_sh:]),
        name=FORECAST_LABELS[spec],
    )


@lru_cache(maxsize=1)
def get_spf_baselines():
    return {spec: _run_specification(df_sh, H_sh, spec) for spec in FORECAST_SPECS}


def available_months():
    return pd.DatetimeIndex(lthf[US_EXT]["path"].index).sort_values()


def scenario_from_values(values, fmt):
    """Convert consecutive monthly inputs; construct a copy of the original model input."""
    vals = np.asarray(values, dtype=float)
    months = available_months()[:len(vals)]
    if not 1 <= len(vals) <= len(available_months()):
        raise ValueError("Choose between 1 and the available SPF forecast months.")
    if not np.isfinite(vals).all():
        raise ValueError("Every month requires a finite value.")
    last_level = float(us.iloc[-1])
    if fmt == "levels":
        if np.any(vals <= 0):
            raise ValueError("Employment levels must be positive (thousands of employees).")
        levels = vals
        growth = (levels / np.r_[last_level, levels[:-1]] - 1) * 100
    elif fmt == "mom":
        if np.any(vals <= -100):
            raise ValueError("MoM growth rates must exceed -100%.")
        growth = vals
        levels = last_level * np.cumprod(1 + growth / 100)
    else:
        raise ValueError("Unknown input format.")

    converted = pd.DataFrame({"month": months, "employment_level": levels, "mom_growth": growth})
    df_user = df_sh.copy()
    user_levels = converted.set_index("month")["employment_level"]
    mask = df_user["Month"].isin(user_levels.index)
    df_user.loc[mask, X_IN] = np.log(df_user.loc[mask, "Month"].map(user_levels))
    df_user = df_user.loc[df_user["Month"] <= months[-1]].reset_index(drop=True)
    H_user = len(df_user) - T0_sh
    return converted, df_user, H_user


def run_comparison(values, fmt, specifications=FORECAST_SPECS):
    """Compute paired SPF/user Indiana paths for each selected original specification."""
    selected = tuple(dict.fromkeys(specifications))
    if not selected or any(spec not in FORECAST_SPECS for spec in selected):
        raise ValueError("Select at least one valid forecasting specification.")
    converted, df_user, H_user = scenario_from_values(values, fmt)
    baseline = get_spf_baselines()
    pairs = {}
    for spec in selected:
        user_path = _run_specification(df_user, H_user, spec)
        pairs[spec] = (baseline[spec].loc[user_path.index], user_path)
    return converted, pairs
