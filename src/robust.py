def is_robust(median_points_per_year, robust_definition):
    """
    A population is robust if its median number of observations per year is above the robust definition
    (Rohrbach et al. 2025: "Populations with a median above 10 were classified as robust").
    Works on single values and on pandas Series.
    """
    return median_points_per_year > robust_definition
