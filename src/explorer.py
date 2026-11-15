"""
Interactive results explorer for Jupyter (see notebooks/results_explorer.ipynb).

Loads a completed run and lets the user re-delineate populations with a different accumulated cost threshold
and robust population definition, without recalculating the least-cost paths (the expensive step). Every change
is explained in plain sentences, checked for typical problems, and shown in the figures of the paper.
Finally, the chosen settings, figures and tables can be exported.
"""
import contextlib
import io
import os
from collections import deque

import geopandas as gpd
import ipywidgets as W
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio as rio
from IPython.display import display

from src import report as R
from src.expansionrate import expansion_rate
from src.populations import group_paths, group_points

NOTEBOOK_STYLE = {**R.STYLE, "figure.dpi": 110}
LEVELS = {  # icon, colour of the left border
    "ok": ("✔", "#2e7d32"),
    "info": ("ℹ", "#1565c0"),
    "warn": ("⚠", "#c77700"),
    "tip": ("➜", "#7b1fa2"),
    "error": ("✖", "#c62828"),
}
WIDE = W.Layout(width="auto")
LABEL = {"description_width": "initial"}


def settings_from_params(params):
    """Default settings of the explorer, taken from params.py."""
    inat = getattr(params, "presence_source", "file") == "inaturalist"
    return {
        "workdir": params.workdir_path,
        "run": params.run,
        "cost_name": params.cost_name,
        "year_field": "year" if inat else params.year_field,
        "location_field": "country" if inat else params.location_field,
        "threshold": getattr(params, "threshold", None),
        "threshold_is_absolute": getattr(params, "threshold_is_absolute", False),
        "robust_definition": getattr(params, "robust_definition", 10),
    }


# ============================================ TEXT ====================================================================

def messages_html(messages):
    rows = []
    for level, text in messages:
        icon, colour = LEVELS[level]
        rows.append(f'<div style="border-left:4px solid {colour};padding:3px 10px;margin:5px 0;line-height:1.45">'
                    f'<span style="color:{colour}">{icon}</span>&nbsp; {text}</div>')
    return "".join(rows)


def show_messages(messages):
    display(W.HTML(messages_html(messages)))


def fmt(x):
    """Compact number format for thresholds, which range from ~0.001 to ~100 depending on the cost surface."""
    return f"{x:.3g}"


def nice_step(x):
    """Rounds a step width to 1, 2 or 5 times a power of ten."""
    exp = np.floor(np.log10(x))
    return min((m * 10 ** exp for m in (1, 2, 5, 10) if m * 10 ** exp >= x), default=x)


# ============================================ ANALYSIS ================================================================

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
    return [{"from": t[a], "to": t[b], "q_from": q[a], "q_to": q[b], "rate_min": r[a:b + 1].min() / 1000,
             "rate_max": r[a:b + 1].max() / 1000} for _, a, b in ranges]


def suggest_breakpoints(years, distances):
    """
    Splits a cumulative distance curve into three linear phases (lag, expansion, final) by minimising the total
    squared error, with the expansion phase being the steepest. Each phase spans at least two years (the expansion phase three); neighbouring
    phases share their boundary year. Returns None if no such split exists.
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


# ============================================ EXPLORER ================================================================

class Explorer:
    """
    Usage in Jupyter:
        ex = Explorer(settings)
        display(ex.load_section())        # loads the run
        display(ex.sensitivity_section())
        display(ex.delineation_section())
        display(ex.phases_section())
        display(ex.export_section())
    """

    def __init__(self, settings):
        self.settings = dict(settings)
        self.loaded = False
        self.breakpoints = {}
        self.split_at = None
        self.previous = None
        self.current = None
        self._syncing = False
        self._threshold_mode = "absolute" if settings.get("threshold_is_absolute") else "quantile"
        self._outputs = {name: W.Output() for name in ("load", "sensitivity", "delineation", "phases", "export")}
        self._build_widgets()

    # ------------------------------------------------------------------------------------------------ data ---------

    def load(self):
        s = self.settings
        gpkg = os.path.join(s["workdir"], f"{s['run']}.gpkg")
        self.saved = R.load_run(s["workdir"], s["run"], s["year_field"], s["robust_definition"])
        self.all_paths = self.saved["paths"]
        self.cost = np.sort(self.all_paths["accumulated_cost"].to_numpy())
        self.points_raw = gpd.read_file(gpkg, layer=f"{s['run']}_points")
        with rio.open(os.path.join(s["workdir"], s["cost_name"])) as src:
            self.cell_size = src.res[0]
        self.basemap = R.Basemap(os.path.join(s["workdir"], s["cost_name"]), self.all_paths.crs)
        with contextlib.redirect_stdout(io.StringIO()):
            value, quantile = R.applied_threshold(self.saved, s["threshold"], s["threshold_is_absolute"])
        self.current = {"data": self.saved, "threshold": value, "quantile": quantile, "raw": None,
                        "label": "saved run"}
        self.previous = None
        self.breakpoints = {}
        self.loaded = True

    def quantile_of(self, value):
        return (self.cost < value).mean()

    def cost_at(self, quantile):
        return float(np.quantile(self.cost, quantile))

    def delineate(self, threshold, robust_definition):
        """Population delineation and expansion rates for a threshold, in memory (same functions as main.py)."""
        s = self.settings
        retained = self.all_paths[self.all_paths["accumulated_cost"] < threshold].copy()
        if retained.empty:
            raise ValueError(f"No least-cost path has an accumulated cost below {fmt(threshold)}.")
        with contextlib.redirect_stdout(io.StringIO()):
            paths_grouped = group_paths(retained)
            points_grouped = group_points(self.points_raw.copy(), paths_grouped, self.cell_size)
            cumdist, rates = expansion_rate(points_grouped, s["year_field"], s["location_field"])
        data = R.build_run_data(s["run"], self.all_paths, paths_grouped, points_grouped, rates, cumdist,
                                self.saved["sensitivity"], s["year_field"], robust_definition)
        raw = {"paths_grouped": paths_grouped, "points_grouped": points_grouped, "rates": rates, "cumdist": cumdist}
        return data, raw

    # ------------------------------------------------------------------------------------------------ widgets ------

    def _build_widgets(self):
        s = self.settings
        self.w_workdir = W.Text(value=str(s["workdir"]), description="Data directory:", layout=WIDE, style=LABEL)
        self.w_run = W.Text(value=s["run"], description="Run name:", layout=WIDE, style=LABEL)
        self.w_cost = W.Text(value=s["cost_name"], description="Cost surface file:", layout=WIDE, style=LABEL)
        self.w_year = W.Text(value=s["year_field"], description="Year field:", style=LABEL)
        self.w_location = W.Text(value=s["location_field"], description="Location field:", style=LABEL)
        self.w_load = W.Button(description="Load run", button_style="primary", icon="folder-open")
        self.w_load.on_click(lambda _: self._on_load())

        self.w_split = W.FloatText(value=0, description="Split x axis at (0 = off):", style=LABEL,
                                   layout=W.Layout(width="260px"))
        self.w_split.observe(lambda _: self._render("sensitivity"), names="value")

        self.w_quantile = W.FloatSlider(min=0.5, max=1.0, step=0.001, readout_format=".3f", continuous_update=False,
                                        description="Threshold as quantile:", style=LABEL,
                                        layout=W.Layout(width="520px"))
        self.w_absolute = W.FloatText(description="as accumulated cost:", style=LABEL, layout=W.Layout(width="260px"))
        self.w_robust = W.FloatSlider(min=1, max=30, step=0.5, value=s["robust_definition"], continuous_update=False,
                                      description="Robust population definition (median observations per year >):",
                                      style=LABEL, layout=W.Layout(width="520px"))
        self.w_threshold_info = W.HTML()
        self.w_apply = W.Button(description="Apply", button_style="primary", icon="refresh")
        self.w_apply.on_click(lambda _: self._on_apply())
        self.w_quantile.observe(self._on_quantile, names="value")
        self.w_absolute.observe(self._on_absolute, names="value")

        self.w_population = W.Dropdown(description="Population:", style=LABEL)
        self.w_years = W.IntRangeSlider(description="Expansion phase:", style=LABEL, continuous_update=False,
                                        layout=W.Layout(width="520px"))
        self.w_suggest = W.Button(description="Suggest phases", icon="magic")
        self.w_keep = W.Button(description="Use these phases", icon="check", button_style="success")
        self.w_drop = W.Button(description="Remove phases", icon="times")
        self.w_population.observe(lambda _: self._on_population(), names="value")
        self.w_years.observe(lambda _: None if self._syncing else self._render("phases"), names="value")
        self.w_suggest.on_click(lambda _: self._on_suggest())
        self.w_keep.on_click(lambda _: self._on_keep())
        self.w_drop.on_click(lambda _: self._on_drop())

        self.w_out_dir = W.Text(description="Output directory:", layout=WIDE, style=LABEL)
        self.w_formats = W.SelectMultiple(options=["png", "pdf", "svg", "tiff"], value=["png"], rows=4,
                                          description="Formats:", style=LABEL)
        self.w_overwrite = W.Checkbox(value=False, indent=False,
                                      description="Also overwrite the run's population layers and CSV files with "
                                                  "this delineation")
        self.w_export = W.Button(description="Export", button_style="primary", icon="download")
        self.w_export.on_click(lambda _: self._on_export())

    def _set_threshold_widgets(self, value):
        self._syncing = True
        self.w_absolute.value = round(value, 6)
        self.w_quantile.value = float(np.clip(self.quantile_of(value), 0.5, 1.0))
        self._syncing = False
        self._update_threshold_info()

    def _on_quantile(self, change):
        if self._syncing:
            return
        self._threshold_mode = "quantile"
        self._syncing = True
        self.w_absolute.value = round(self.cost_at(change["new"]), 6)
        self._syncing = False
        self._update_threshold_info()

    def _on_absolute(self, change):
        if self._syncing:
            return
        self._threshold_mode = "absolute"
        self._syncing = True
        self.w_quantile.value = float(np.clip(self.quantile_of(change["new"]), 0.5, 1.0))
        self._syncing = False
        self._update_threshold_info()

    def _pending_threshold(self):
        if self._threshold_mode == "quantile":
            return self.cost_at(self.w_quantile.value)
        return self.w_absolute.value

    def _update_threshold_info(self):
        if not self.loaded:
            return
        value = self._pending_threshold()
        kept = int((self.cost < value).sum())
        changed = (not np.isclose(value, self.current["threshold"])
                   or self.w_robust.value != self.current["data"]["robust_definition"])
        hint = " — <b>click Apply to update the results</b>" if changed else ""
        self.w_threshold_info.value = (f"Accumulated cost {fmt(value)} (Q{self.quantile_of(value):.3f}): "
                                       f"{kept} of {len(self.cost)} least-cost paths are kept{hint}.")

    # ------------------------------------------------------------------------------------------------ sections -----

    def load_section(self):
        form = W.VBox([self.w_workdir, self.w_run, self.w_cost, W.HBox([self.w_year, self.w_location]), self.w_load])
        return W.VBox([form, self._outputs["load"]])

    def sensitivity_section(self):
        self._render("sensitivity")
        return W.VBox([self.w_split, self._outputs["sensitivity"]])

    def delineation_section(self):
        self.w_robust.observe(lambda _: self._update_threshold_info(), names="value")
        self._render("delineation")
        return W.VBox([W.HBox([self.w_quantile, self.w_absolute]), self.w_robust, self.w_threshold_info,
                       self.w_apply, self._outputs["delineation"]])

    def phases_section(self):
        self._render("phases")
        return W.VBox([self.w_population, self.w_years, W.HBox([self.w_suggest, self.w_keep, self.w_drop]),
                       self._outputs["phases"]])

    def export_section(self):
        self._render("export")
        return W.VBox([self.w_out_dir, self.w_formats, self.w_overwrite, self.w_export, self._outputs["export"]])

    # ------------------------------------------------------------------------------------------------ events -------

    def _on_load(self):
        self.settings.update({"workdir": self.w_workdir.value, "run": self.w_run.value, "cost_name": self.w_cost.value,
                              "year_field": self.w_year.value, "location_field": self.w_location.value})
        out = self._outputs["load"]
        with out:
            out.clear_output()
            show_messages([("info", "Loading run, this takes a few seconds...")])
        try:
            self.load()
        except Exception as e:  # show the reason in the notebook instead of a traceback
            with out:
                out.clear_output()
                show_messages([("error", f"Could not load the run: {e}")])
            return
        self.w_out_dir.value = os.path.join(self.settings["workdir"], f"{self.settings['run']}_report")
        self._set_threshold_widgets(self.current["threshold"])
        for name in self._outputs:
            self._render(name)

    def _on_apply(self):
        if not self.loaded:
            return
        value, robust_definition = self._pending_threshold(), self.w_robust.value
        out = self._outputs["delineation"]
        with out:
            out.clear_output()
            show_messages([("info", "Delineating populations and calculating expansion rates...")])
        try:
            if np.isclose(value, self.current["threshold"]):  # only the robust definition changed: no recalculation
                data = {**self.current["data"], "rates": self.current["data"]["rates"].copy(),
                        "cumdist": self.current["data"]["cumdist"].copy()}
                R.set_robust_definition(data, robust_definition)
                raw = self.current["raw"]
            else:
                data, raw = self.delineate(value, robust_definition)
        except Exception as e:
            with out:
                out.clear_output()
                show_messages([("error", str(e))])
            return
        self.previous = self.current
        self.current = {"data": data, "threshold": value, "quantile": self.quantile_of(value), "raw": raw,
                        "label": f"threshold {fmt(value)}, robust > {robust_definition:g}"}
        self._update_threshold_info()
        for name in ("sensitivity", "delineation", "phases", "export"):
            self._render(name)

    def _robust_rates(self):
        rates = self.current["data"]["rates"]
        return rates[rates["robust"]].sort_values("group_name")

    def _on_population(self):
        if self._syncing or not self.w_population.value:
            return
        self._prepare_years()
        self._render("phases")

    def _prepare_years(self):
        """Sets the year slider to the observation period of the selected population (or its saved phases)."""
        name = self.w_population.value
        g = self.current["data"]["cumdist"]
        years = g[g["group_name"] == name]["year"]
        lo, hi = int(years.min()), int(years.max())
        self._syncing = True
        self.w_years.min, self.w_years.max = min(lo, self.w_years.min), max(hi, self.w_years.max)
        self.w_years.value = self.breakpoints.get(name, (lo, hi))
        self.w_years.min, self.w_years.max = lo, hi
        self._syncing = False

    def _on_suggest(self):
        name = self.w_population.value
        g = self.current["data"]["cumdist"]
        g = g[g["group_name"] == name].sort_values("year")
        best = suggest_breakpoints(g["year"], g["max_distance"]) if len(g) >= 4 else None
        if best:
            self.w_years.value = best

    def _on_keep(self):
        if self.w_population.value:
            self.breakpoints[self.w_population.value] = tuple(self.w_years.value)
            self._render("phases")
            self._render("export")

    def _on_drop(self):
        self.breakpoints.pop(self.w_population.value, None)
        self._render("phases")
        self._render("export")

    def _on_export(self):
        out = self._outputs["export"]
        cur, s = self.current, self.settings
        out_dir = self.w_out_dir.value
        try:
            R.write_outputs(cur["data"], self.basemap, cur["threshold"], cur["quantile"],
                            cur["data"]["robust_definition"], out_dir, split_at=self.split_at,
                            breakpoints=self._valid_breakpoints(), formats=list(self.w_formats.value))
            written = sorted(f for f in os.listdir(out_dir) if f.startswith(s["run"] + "_"))
            messages = [("ok", f"Saved to <code>{out_dir}</code>: " + ", ".join(f"<code>{f}</code>" for f in written))]
            if self.w_overwrite.value:
                messages.append(self._overwrite_run())
        except Exception as e:
            messages = [("error", f"Export failed: {e}")]
        with out:
            out.clear_output()
            show_messages(messages)
            self._show_settings()

    def _overwrite_run(self):
        raw, s = self.current["raw"], self.settings
        if raw is None:
            return ("info", "The run's files already contain this delineation; nothing to overwrite.")
        gpkg = os.path.join(s["workdir"], f"{s['run']}.gpkg")
        raw["paths_grouped"].to_file(gpkg, layer=f"{s['run']}_paths_grouped")
        raw["points_grouped"].to_file(gpkg, layer=f"{s['run']}_points_grouped")
        raw["rates"].to_csv(os.path.join(s["workdir"], f"{s['run']}_expansion_rates.csv"), index=False)
        raw["cumdist"].to_csv(os.path.join(s["workdir"], f"{s['run']}_cumulative_distances.csv"), index=False)
        return ("ok", f"Population layers in <code>{gpkg}</code> and the expansion rate CSV files were overwritten. "
                      f"animate.py and report.py now use this delineation.")

    def _valid_breakpoints(self):
        names = set(self.current["data"]["rates"]["group_name"])
        return {k: v for k, v in self.breakpoints.items() if k in names}

    # ------------------------------------------------------------------------------------------------ rendering ----

    def _render(self, name):
        out = self._outputs[name]
        with out:
            out.clear_output(wait=True)
            if not self.loaded:
                show_messages([("info", "Load a run first (section 1).")])
                return
            with plt.rc_context(NOTEBOOK_STYLE):
                getattr(self, f"_render_{name}")()

    def _show(self, fig):
        display(fig)
        plt.close(fig)

    def _render_load(self):
        data, cur = self.saved, self.current
        pts, rates = data["points"], data["rates"]
        robust = rates[rates["robust"]]
        sens = data["sensitivity"]
        text = (f"Run <b>{data['run']}</b> contains <b>{len(pts)}</b> observations from {int(pts['year'].min())} to "
                f"{int(pts['year'].max())}. Sequential least-cost modelling connected each year's new observations to "
                f"earlier ones with <b>{len(data['paths'])}</b> least-cost paths. With the accumulated cost threshold "
                f"of the run, <b>{fmt(cur['threshold'])}</b> (Q{cur['quantile']:.3f}), "
                f"{len(data['paths_grouped'])} paths were kept. They form <b>{len(rates)}</b> populations, of which "
                f"<b>{len(robust)}</b> are robust (more than {data['robust_definition']:g} median observations per "
                f"year).")
        messages = [("ok", text)]
        if sens is None:
            messages.append(("warn", "This run has no sensitivity test. Section 2 can only show the distribution of "
                                     "accumulated costs. See the suggested test range there."))
        show_messages(messages)

    def _render_sensitivity(self):
        sens, cur = self.saved["sensitivity"], self.current
        definition = cur["data"]["robust_definition"]
        q99 = self.cost_at(0.99)
        step = nice_step(q99 / 200)
        suggestion = (f"<code>acc_cost_test_steps = np.arange(0, {nice_step(q99)}, {step:g})</code> and "
                      f"<code>acc_cost_steps_are_absolute = True</code> (covers Q0 to Q0.99 in about 200 steps), or "
                      f"<code>np.arange(0.80, 1.0, 0.002)</code> with <code>acc_cost_steps_are_absolute = False</code>")
        messages = [("info", "The sensitivity test shows how the average expansion rate of robust populations changes "
                             "with the accumulated cost threshold. Low thresholds split populations artificially "
                             "(too few paths kept), very high thresholds merge separate introductions into "
                             "implausible super-populations. A good threshold lies at the <b>beginning of a stable "
                             "range</b>, where the result hardly depends on the exact value.")]
        if sens is None:
            messages.append(("tip", f"Run <code>main.py</code> with <code>mode = \"test\"</code> and {suggestion}."))
            show_messages(messages)
            self._show(self._cost_histogram())
            return

        tmin, tmax = sens["threshold"].min(), sens["threshold"].max()
        qmin, qmax = sens["quantile"].min(), sens["quantile"].max()
        if not tmin <= cur["threshold"] <= tmax:
            messages.append(("warn", f"The current threshold {fmt(cur['threshold'])} (Q{cur['quantile']:.3f}) lies "
                                     f"<b>outside the tested range</b> {fmt(tmin)}–{fmt(tmax)} (Q{qmin:.3f}–"
                                     f"Q{qmax:.3f}). The test cannot tell whether it lies in a stable range."))
        if qmin >= 0.99:
            messages.append(("warn", "The whole tested range lies above Q0.99: practically all paths are kept at "
                                     "every tested value, so the curves are flat and uninformative."))
        elif qmax <= 0.5:
            messages.append(("warn", "The tested range only covers the lower half of the accumulated costs (up to "
                                     f"Q{qmax:.2f}). Test higher values."))
        if qmin >= 0.99 or qmax <= 0.5 or not tmin <= cur["threshold"] <= tmax:
            messages.append(("tip", f"Rerun the test (<code>mode = \"test\"</code>) with {suggestion}."))

        definitions = np.array(sorted(sens["definition_robust"].unique()))
        nearest = definitions[np.argmin(np.abs(definitions - definition))]
        ranges = stable_ranges(sens, nearest)
        if ranges and qmin < 0.99:
            items = "".join(f"<li>{fmt(r['from'])}–{fmt(r['to'])} (Q{r['q_from']:.3f}–Q{r['q_to']:.3f}): "
                            f"{r['rate_min']:.1f}–{r['rate_max']:.1f} km/year</li>" for r in ranges)
            messages.append(("tip", f"Most stable threshold ranges for robust definition {nearest:g} (average rate "
                                    f"stays within ±25%; widest first; top 0.5% of paths ignored):<ul "
                                    f"style='margin:2px 0'>{items}</ul>Consider the beginning of the range that "
                                    f"follows the steep increase (merging of fragments), and avoid ranges at the very "
                                    f"top, where few extreme paths merge distant populations."))
        if tmin <= cur["threshold"] <= tmax:
            at = sens.iloc[(sens["threshold"] - cur["threshold"]).abs().argsort()]
            at = at[at["threshold"] == at["threshold"].iloc[0]].dropna(subset=["avg_rate"])
            if len(at) > 1 and at["avg_rate"].max() > 0:
                spread = (at["avg_rate"].max() - at["avg_rate"].min()) / at["avg_rate"].mean()
                level = "ok" if spread < 0.1 else "info"
                messages.append((level, f"At the current threshold, the average expansion rate is "
                                        f"{at['avg_rate'].min() / 1000:.1f}–{at['avg_rate'].max() / 1000:.1f} km/year "
                                        f"across the tested robust population definitions"
                                        f"{' (insensitive to the definition)' if spread < 0.1 else ''}."))
        show_messages(messages)
        self.split_at = self.w_split.value or None
        self._show(self._sensitivity_figure(sens, nearest))

    def _sensitivity_figure(self, sens, definition):
        cur = self.current
        split = self.split_at if self.split_at and sens["threshold"].min() < self.split_at < sens["threshold"].max() \
            else None
        fig = plt.figure(figsize=(7.5, 5.2))
        gs = fig.add_gridspec(2, 1, height_ratios=[3, 2], hspace=0.45)
        if split:
            sub = gs[0].subgridspec(1, 2, width_ratios=[4, 1], wspace=0.04)
            axes = [fig.add_subplot(sub[0, 0])]
            axes.append(fig.add_subplot(sub[0, 1], sharey=axes[0]))
        else:
            axes = [fig.add_subplot(gs[0])]
        R.plot_sensitivity(axes, {"sensitivity": sens}, cur["threshold"], split)
        axes[0].set_title("Average expansion rate of robust populations", pad=24)
        ax = fig.add_subplot(gs[1], sharex=axes[0])
        s = sens[sens["definition_robust"] == definition].sort_values("threshold")
        ax.step(s["threshold"], s["num_groups"], where="post", color="#555555", lw=1)
        ax.set_ylabel("All populations", color="#555555")
        ax.set_ylim(bottom=0)
        ax2 = ax.twinx()
        ax2.step(s["threshold"], s["num_groups_robust"], where="post", color="#d62728", lw=1.2)
        ax2.set_ylabel(f"Robust populations (> {definition:g})", color="#d62728")
        ax2.set_ylim(0, max(s["num_groups_robust"].max(), 1) * 1.15)
        ax2.yaxis.get_major_locator().set_params(integer=True)
        ax2.grid(False)
        ax.axvline(cur["threshold"], color="black", ls="--", lw=0.8)
        ax.set_xlabel("Accumulated cost threshold")
        ax.set_title("Number of populations (populations merge as the threshold increases)")
        return fig

    def _cost_histogram(self):
        fig, ax = plt.subplots(figsize=(7.5, 2.8))
        ax.hist(self.cost, bins=100, color="#bebebe", edgecolor="black", linewidth=0.3)
        ax.axvline(self.current["threshold"], color="black", ls="--", lw=0.8)
        ax.set_yscale("log")
        ax.set_xlabel("Accumulated cost of least-cost paths")
        ax.set_ylabel("Number of paths")
        ax.set_title("Distribution of accumulated costs (dashed: current threshold)")
        return fig

    def _delineation_messages(self):
        data, cur, prev = self.current["data"], self.current, self.previous
        rates, pts, paths = data["rates"], data["points"], data["paths_grouped"]
        robust = rates[rates["robust"]]
        n_iso = int(pts["group_id"].isna().sum())
        msgs = [("ok", f"<b>{len(rates)}</b> populations, <b>{len(robust)}</b> of them robust "
                       f"({', '.join(robust.sort_values('group_name')['group_name']) or 'none'}). "
                       f"{n_iso} observations ({n_iso / len(pts):.1%}) are isolated.")]
        if prev is not None:
            p_rates = prev["data"]["rates"]
            p_names, names = set(p_rates.loc[p_rates["robust"], "group_name"]), set(robust["group_name"])
            change = (f"Compared to the previous setting ({prev['label']}): populations {len(p_rates)} → "
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
                "consider splitting it into phases (section 4)."))
        short = robust[robust["max_year"] - robust["min_year"] < 5]
        if len(short):
            msgs.append(("info", "Short observation period (< 5 years) for " + ", ".join(short["group_name"]) +
                                 "; their expansion rates are less certain."))
        return msgs

    def _render_delineation(self):
        cur, prev = self.current, self.previous
        show_messages(self._delineation_messages())
        compare = prev["data"] if prev is not None else None
        label = f"previous: {prev['label']}" if prev is not None else None
        self._show(R.figure_sensitivity(cur["data"], self.basemap, cur["threshold"], cur["data"]["robust_definition"],
                                        compare, label, self.split_at))
        self._show(R.figure_populations(cur["data"], self.basemap, self._valid_breakpoints()))
        table = R.population_table(cur["data"]["rates"])
        display(W.HTML("<b>Robust populations</b>" + table[table["type"] == "robust"].to_html(index=False)))
        n_sparse = int((table["type"] == "sparse").sum())
        with_sparse = W.Output()
        with with_sparse:
            display(W.HTML(table[table["type"] == "sparse"].to_html(index=False)))
        acc = W.Accordion(children=[with_sparse], titles=(f"Sparse populations ({n_sparse})",))
        acc.selected_index = None
        display(acc)

    def _render_phases(self):
        robust = self._robust_rates()
        names = list(robust["group_name"])
        if self.w_population.options != tuple(names):
            self._syncing = True
            self.w_population.options = names
            self.w_population.value = names[0] if names else None
            self._syncing = False
            if names:
                self._prepare_years()
        if not names:
            show_messages([("info", "There are no robust populations at the current setting.")])
            return
        name = self.w_population.value
        g = self.current["data"]["cumdist"]
        g = g[g["group_name"] == name].sort_values("year")
        b1, b2 = self.w_years.value
        if g["year"].nunique() < 4:
            show_messages([("info", f"{name} has fewer than four years of data; phases cannot be fitted.")])
            return
        phases = R.fit_phases(g, {name: (b1, b2)})
        whole = robust[robust["group_name"] == name].iloc[0]
        exp = phases[phases["segment_id"] == 2].iloc[0]
        msgs = [("info", "Many invasions show a <b>lag phase</b>, an <b>expansion phase</b> and a <b>final "
                         "phase</b> (e.g. when the range edge reaches a barrier or the observation period ends). "
                         "A single linear model then underestimates the expansion rate. Set the expansion phase "
                         "with the slider or let <i>Suggest phases</i> find the best three-part fit."),
                ("ok", f"{name}: expansion phase {b1}–{b2}: <b>{exp['expansion_rate_km_per_year']:.1f} km/year</b> "
                       f"(R² {exp['r2']:.2f}) compared to {whole['expansion_rate_km']:.1f} km/year (R² "
                       f"{whole['r2']:.2f}) for the whole period.")]
        if name in self.breakpoints:
            msgs.append(("ok", f"Phases saved for {name}: {self.breakpoints[name][0]}–{self.breakpoints[name][1]}."))
        if self._valid_breakpoints():
            msgs.append(("info", "Saved phases: " + "; ".join(f"{k} {v[0]}–{v[1]}"
                                                              for k, v in self._valid_breakpoints().items())))
        show_messages(msgs)

        fig, ax = plt.subplots(figsize=(7.5, 3.2))
        ax.plot(g["year"], g["max_distance"] / 1000, color="#377eb8", marker="o", markersize=4, lw=1.2,
                label=name)
        colours = ["#999999", "#e41a1c", "#999999"]
        for row, c in zip(phases.itertuples(), colours):
            seg = g[(g["year"] >= row.year_from) & (g["year"] <= row.year_to)]
            if seg["year"].nunique() > 1:
                k, d = np.polyfit(seg["year"], seg["max_distance"] / 1000, 1)
                x = np.array([row.year_from, row.year_to])
                ax.plot(x, k * x + d, ls="--", color=c, lw=1.2,
                        label=f"{row.phase}: {row.expansion_rate_km_per_year:.1f} km/year")
        ax.axvspan(b1, b2, color="#e41a1c", alpha=0.07, lw=0)
        ax.xaxis.get_major_locator().set_params(integer=True)
        ax.set_xlabel("Time (year)")
        ax.set_ylabel("Cumulative distance (km)")
        ax.set_ylim(bottom=0)
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0)
        self._show(fig)
        display(W.HTML(phases.to_html(index=False)))

    def _render_export(self):
        show_messages([("info", "Export saves the figures, tables and a summary for the current setting. Below are "
                                "the settings to reproduce it with <code>main.py</code> and <code>report.py</code>.")])
        self._show_settings()

    def _show_settings(self):
        cur, s = self.current, self.settings
        if self._threshold_mode == "quantile" and cur["label"] != "saved run":
            value, absolute = f"{cur['quantile']:.3f}", False
        else:
            value, absolute = fmt(cur["threshold"]), True
        robust_definition = cur["data"]["robust_definition"]
        options = [f"--run {s['run']}", f"--threshold {value}",
                   "--threshold-is-absolute" if absolute else "--no-threshold-is-absolute",
                   f"--robust-definition {robust_definition:g}"]
        if self.split_at:
            options.append(f"--split-at {self.split_at:g}")
        options += [f'--breakpoints "{k}={v[0]}-{v[1]}"' for k, v in self._valid_breakpoints().items()]
        snippet = (f"# params.py\nthreshold = {value}\nthreshold_is_absolute = {absolute}\n"
                   f"robust_definition = {robust_definition:g}\n\n# command line\npython report.py "
                   + " \\\n    ".join(options))
        display(W.HTML(f"<pre style='padding:8px;border:1px solid #ccc'>{snippet}</pre>"))
