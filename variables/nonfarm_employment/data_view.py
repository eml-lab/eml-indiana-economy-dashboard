"""Read-only reference values from the unchanged forecasting backend."""
import numpy as np
from variables.nonfarm_employment.forecasting import available_months, lthf, US_EXT, us
months = available_months()
spf_levels = lthf[US_EXT]["path"].reindex(months).astype(float)
spf_previous = np.r_[float(us.iloc[-1]), spf_levels.to_numpy()[:-1]]
spf_mom = (spf_levels.to_numpy() / spf_previous - 1.0) * 100.0
