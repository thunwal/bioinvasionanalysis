"""
Helps the scientist choose the accumulated cost threshold: stable ranges of the sensitivity test, the suggested range
for its high-resolution run, and plain-language checks of a delineation. Every suggestion comes with the rule that
produced it, so it can be reported and questioned. Messages are (level, Markdown text) with level one of
"ok", "info", "warn" or "tip"; the CLI prints them, the web app shows them as coloured notes.
"""
from collections import deque

import numpy as np


def fmt(x):
    """Compact number format for thresholds, which range from ~0.001 to ~100 depending on the cost surface."""
    return f"{x:.3g}"


def nice_step(x):
    """Rounds a step width up to 1, 2 or 5 times a power of ten."""
    exp = np.floor(np.log10(x))
    return float(min((m * 10 ** exp for m in (1, 2, 5, 10) if m * 10 ** exp >= x), default=x))


def nearest_definition(sens, definition):
    """The robust definition of the sensitivity test that is closest to 'definition'."""
    definitions = np.array(sorted(sens["definition_robust"].unique()))
    return definitions[np.argmin(np.abs(definitions - definition))]


def stable_ranges(sens, definition, tolerance=0.25, max_quantile=0.995, n=3):
    """
    Finds threshold ranges in which the average expansion rate of robust populations stays within +/- tolerance
    around the middle of its range. Ranges are ranked by their width in threshold units (i.e. in dispersal capacity).
    Thresholds above 'max_quantile' are ignored: there, a handful of extreme paths merges distant populations, and
    the few remaining steps would otherwise form long, meaningless "stable" ranges.
    """
    ratio = (1 + tolerance) / (1 - tolerance)
    s = sens[(sens["definition_robust"] == definition) & (sens["avg_rate"] > 0)
              & (sens["quantile"] <= max_quantile)].sort_values("threshold")
    r, t, q = s["avg_rate"].to_numpy(), s["threshold"].to_numpy(), s["quantile"].to_numpy()
    found, left = [], 0
    hi, lo = deque(), deque()  # indices of window maximum / minimum (monotonic queues)
    for right in range(len(r)):
        while hi and r[hi[-1]] <= r[right]:
            hi.pop()
        hi.append(right)
        while lo and r[lo[-1]] >= r[right]:
            lo.pop()
        lo.append(right)
        while r[hi[0]] > r[lo[0]] * ratio:
            left += 1
            if hi[0] < left:
                hi.popleft()
            if lo[0] < left:
                lo.popleft()
        found.append((t[right] - t[left], left, right))
    ranges = []
    for width, a, b in sorted(found, reverse=True):
        if b - a < 3 or any(not (b < a2 or a > b2) for _, a2, b2 in ranges):
            continue  # too short, or overlapping a better range
        ranges.append((width, a, b))
        if len(ranges) == n:
            break
    return [{"from": float(t[a]), "to": float(t[b]), "q_from": float(q[a]), "q_to": float(q[b]),
             "rate_min": float(r[a:b + 1].min() / 1000), "rate_max": float(r[a:b + 1].max() / 1000)} for _, a, b in ranges]


def coarse_thresholds(costs, steps):
    """Thresholds of the sensitivity test overview: 0 to the highest accumulated cost, in about 'steps' round steps."""
    step = nice_step(np.max(costs) / steps)
    return np.arange(0, np.max(costs) + step, step).round(12), step


def suggest_fine_range(coarse, costs, definition, s):
    """
    Suggests the high-resolution range of the sensitivity test from its overview ('s' = SensitivityConfig). Returns a dict with
    from, to, step, the stable ranges found, and 'rule': the rule in words, as shown to the user and stored.
    """
    cap = float(np.quantile(costs, s.max_quantile))
    definition = nearest_definition(coarse, definition)
    ranges = stable_ranges(coarse, definition, s.stable_tolerance, s.max_quantile, s.n_ranges)
    if ranges:
        lo, hi = min(r["from"] for r in ranges), max(r["to"] for r in ranges)
        margin = s.margin * (hi - lo)
        lo, hi = max(lo - margin, 0.0), min(hi + margin, cap)
        rule = (f"Sensitivity test overview: stable ranges for robust definition {definition:g}, where the average expansion "
                f"rate stays within ±{s.stable_tolerance:.0%} (top {1 - s.max_quantile:.1%} of paths ignored). "
                f"Suggested range: from the lowest start to the highest end of the {len(ranges)} widest stable "
                f"range(s), widened by {s.margin:.0%} on each side and capped at Q{s.max_quantile:g} ({fmt(cap)}).")
    else:
        lo, hi = 0.0, cap
        rule = (f"Sensitivity test overview: no stable range found for robust definition {definition:g} (average rate within "
                f"±{s.stable_tolerance:.0%}). Suggested range: 0 to Q{s.max_quantile:g} ({fmt(cap)}).")
    step = nice_step((hi - lo) / s.fine_steps) if hi > lo else nice_step(cap / s.fine_steps)
    lo, hi = np.floor(lo / step) * step, np.ceil(hi / step) * step
    rule += f" Step: {step:g} (about {s.fine_steps} steps, rounded)."
    return {"from": float(lo), "to": float(hi), "step": step, "ranges": ranges, "definition": float(definition),
            "rule": rule}


def suggest_breakpoints(years, distances):
    """
    Splits a cumulative distance curve into three linear phases (lag, expansion, final) by minimising the total
    squared error, with the expansion phase being the steepest. Each phase spans at least two years (the expansion
    phase three); neighbouring phases share their boundary year. Returns None if no such split exists.
    """
    years, distances = np.asarray(years), np.asarray(distances)
    best, best_sse = None, np.inf
    for i in range(1, len(years) - 1):
        for j in range(i + 2, len(years) - 1):  # expansion phase: at least three years
            sse, slopes = 0, []
            for a, b in ((0, i), (i, j), (j, len(years) - 1)):
                x, y = years[a:b + 1], distances[a:b + 1]
                coef = np.polyfit(x, y, 1)
                slopes.append(coef[0])
                sse += ((y - np.polyval(coef, x)) ** 2).sum()
            if slopes[1] <= max(slopes[0], slopes[2]):
                continue  # the expansion phase must be the steepest
            if sse < best_sse:
                best, best_sse = (int(years[i]), int(years[j])), sse
    return best


def sensitivity_checks(sens, threshold, definition):
    """Notes on the chosen threshold in the light of the sensitivity test."""
    msgs = []
    tmin, tmax = sens["threshold"].min(), sens["threshold"].max()
    if not tmin <= threshold <= tmax:
        msgs.append(("warn", f"The threshold {fmt(threshold)} lies **outside the tested range** {fmt(tmin)}–"
                             f"{fmt(tmax)}, so the sensitivity test cannot tell whether it lies in a stable range."))
        return msgs
    at = sens.iloc[(sens["threshold"] - threshold).abs().argsort()]
    at = at[at["threshold"] == at["threshold"].iloc[0]].dropna(subset=["avg_rate"])
    if len(at) > 1 and at["avg_rate"].max() > 0:
        spread = (at["avg_rate"].max() - at["avg_rate"].min()) / at["avg_rate"].mean()
        msgs.append(("ok" if spread < 0.1 else "info",
                     f"At this threshold, the average expansion rate is {at['avg_rate'].min() / 1000:.1f}–"
                     f"{at['avg_rate'].max() / 1000:.1f} km/year across the tested robust population definitions"
                     f"{' (insensitive to the definition)' if spread < 0.1 else ''}."))
    ranges = stable_ranges(sens, nearest_definition(sens, definition))
    inside = [r for r in ranges if r["from"] <= threshold <= r["to"]]
    if inside:
        r = inside[0]
        msgs.append(("ok", f"The threshold lies in a stable range ({fmt(r['from'])}–{fmt(r['to'])}, average rate "
                           f"{r['rate_min']:.1f}–{r['rate_max']:.1f} km/year)."))
    elif ranges:
        msgs.append(("info", "The threshold lies outside the stable ranges found: " + "; ".join(
            f"{fmt(r['from'])}–{fmt(r['to'])}" for r in ranges) + "."))
    return msgs


def delineation_checks(data, previous=None):
    """
    Plain-language checks of a delineation ('data' as built by report.figures.build_run_data). 'previous' is an
    optional dict {"data": ..., "label": ...} of the previous setting, to describe what changed.
    """
    rates, pts, paths = data["rates"], data["points"], data["paths_grouped"]
    robust = rates[rates["robust"]]
    n_iso = int(pts["group_id"].isna().sum())
    msgs = [("ok", f"**{len(rates)}** populations, **{len(robust)}** of them robust "
                   f"({', '.join(robust.sort_values('group_name')['group_name']) or 'none'}). "
                   f"{n_iso} observations ({n_iso / len(pts):.1%}) are isolated.")]
    if previous is not None:
        p_rates = previous["data"]["rates"]
        p_names, names = set(p_rates.loc[p_rates["robust"], "group_name"]), set(robust["group_name"])
        change = (f"Compared to the previous setting ({previous['label']}): populations {len(p_rates)} → "
                  f"{len(rates)}, robust {len(p_names)} → {len(names)}.")
        if names - p_names:
            change += f" Newly robust: {', '.join(sorted(names - p_names))}."
        if p_names - names:
            change += f" No longer robust: {', '.join(sorted(p_names - names))}."
        moved = []
        for name in sorted(names & p_names):
            a = p_rates.loc[p_rates["group_name"] == name, "expansion_rate_km"].iloc[0]
            b = robust.loc[robust["group_name"] == name, "expansion_rate_km"].iloc[0]
            if a > 0 and abs(b - a) / a > 0.2:
                moved.append(f"{name} {a:.1f} → {b:.1f}")
        if moved:
            change += f" Expansion rates changed by more than 20%: {'; '.join(moved)} km/year."
        msgs.append(("info", change))
    if len(robust) == 0:
        msgs.append(("warn", "There are no robust populations, so no reliable expansion rate can be given. "
                             "Lower the robust population definition or raise the threshold."))
    if n_iso / len(pts) > 0.25:
        msgs.append(("warn", f"{n_iso / len(pts):.0%} of the observations are isolated. The threshold may be too "
                             "strict and fragment populations artificially."))
    counts = pts["group_id"].value_counts()
    if len(counts) and counts.iloc[0] / len(pts) > 0.6 and len(robust) <= 2:
        big = rates.loc[rates["group_id"] == counts.index[0], "group_name"].iloc[0]
        minx, miny, maxx, maxy = pts[pts["group_id"] == counts.index[0]].total_bounds
        msgs.append(("warn", f"Population {big} holds {counts.iloc[0] / len(pts):.0%} of all observations and "
                             f"spans about {np.hypot(maxx - minx, maxy - miny) / 1000:,.0f} km. Check whether it "
                             "merges independent introductions (threshold too high)."))
    if len(paths):
        lengths = paths.length / 1000
        longest = paths.assign(km=lengths).nlargest(3, "km")
        if longest["km"].iloc[0] > 10 * lengths.median():
            items = ", ".join(f"{r.km:,.0f} km ({r.destination_year})" for r in longest.itertuples())
            msgs.append(("warn", f"The longest kept paths are much longer than typical paths (median "
                                 f"{lengths.median():,.0f} km): {items}. Check whether such annual dispersal is "
                                 "plausible for the species, or whether they connect separate introductions."))
    poor = robust[robust["r2"] < 0.5]
    if len(poor):
        msgs.append(("warn", "The linear model fits poorly for " + ", ".join(
            f"{r.group_name} (R² {r.r2:.2f})" for r in poor.itertuples()) + ". The expansion may not be linear; "
            "consider splitting it into phases."))
    short = robust[robust["max_year"] - robust["min_year"] < 5]
    if len(short):
        msgs.append(("info", "Short observation period (< 5 years) for " + ", ".join(short["group_name"]) +
                             "; their expansion rates are less certain."))
    return msgs
