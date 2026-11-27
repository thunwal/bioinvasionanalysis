import numpy as np
import pandas as pd

from bioinvasion.core.expansionrate import expansion_rate
from bioinvasion.core.populations import delineate
from bioinvasion.core.robust import is_robust


def sweep(paths, points, cell_size, thresholds, robust_definitions, progress=None):
    """
    Sensitivity analysis: delineates the populations for every accumulated cost threshold and reports, for every
    robust population definition, the number of (robust) populations and the min/max/average expansion rate of the
    robust populations. 'progress(done, total)' is called after each threshold.
    """
    results = []
    for i, threshold in enumerate(thresholds):
        paths_grouped, points_grouped, quantile = delineate(paths, points, threshold, cell_size)
        rates = expansion_rate(points_grouped)[1] if len(paths_grouped) else None
        for definition in robust_definitions:
            row = {"quantile": quantile, "threshold": threshold, "definition_robust": definition,
                   "num_groups": 0, "num_groups_robust": 0,
                   "min_rate": np.nan, "max_rate": np.nan, "avg_rate": np.nan}
            if rates is not None:
                robust = rates[is_robust(rates["median_points_per_year"], definition)]
                row.update(num_groups=rates["group_id"].nunique(), num_groups_robust=robust["group_id"].nunique(),
                           min_rate=robust["expansion_rate"].min(), max_rate=robust["expansion_rate"].max(),
                           avg_rate=robust["expansion_rate"].mean())
            results.append(row)
        if progress:
            progress(i + 1, len(thresholds))
    return pd.DataFrame(results)
