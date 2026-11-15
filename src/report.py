"""
Results report for a completed run: recreates the result figures and tables of the paper
(Rohrbach et al. 2025) for any dataset, using only the outputs written by main.py.

- Figure "sensitivity" (Fig. 5 of the paper): (a) sensitivity analysis, (b) populations of an optional
  comparison run, (c) populations of this run, (d) histogram of median observations per year.
- Figure "populations" (Fig. 6 of the paper): (a) map of robust populations, (b) cumulative distance
  to the first observation over time, optionally with linear models fitted to expansion phases.
- Table "populations" (Tab. 1), table "phases" (Tab. 2, only with breakpoints) and a short summary.

Unlike the manuscript code, nothing is specific to the Sculptured Resin Bee: population names, labels,
thresholds, axis ranges and colours are derived from the data.
"""
import os
import string
from datetime import datetime as dt

import geopandas as gpd
import matplotlib
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyogrio
import rasterio as rio
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from rasterio.warp import transform_bounds
from shapely.geometry import LineString

from src.naturalearth import natural_earth

matplotlib.use("Agg")

GREY = "#8b9a9a"  # close to R's "azure4" used in the paper
GROUP_PALETTE = ["#4daf4a", "#984ea3", "#ff7f00"]  # alternating colours for all populations (Fig. 5 maps)
MARKERS = ["o", "^", "s", "D", "v", "P", "X", "*", "<", ">"]

# Similar to ggplot2's theme_bw(base_size = 8) used in the manuscript
STYLE = {
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.titlelocation": "left",
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "legend.frameon": False,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.6,
    "axes.grid": True,
    "grid.color": "#ebebeb",
    "grid.linewidth": 0.6,
    "axes.axisbelow": True,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "savefig.bbox": "tight",
}


def _log(msg):
    print(f"[{dt.now().strftime('%H:%M:%S')}] {msg}")


# ============================================ DATA ====================================================================

def group_names(rates):
    """
    Population names as used in the paper: '{first_observed_in} {min_year}', with suffixes a, b, ...
    for duplicates (ordered by point count and last year, descending).
    """
    rates = rates.copy()
    rates["base_name"] = rates["first_observed_in"] + " " + rates["min_year"].astype(str)
    rates = rates.sort_values(["base_name", "point_count", "max_year"], ascending=[True, False, False])
    n = rates.groupby("base_name")["base_name"].transform("size")
    rank = rates.groupby("base_name").cumcount()
    rates["suffix"] = [string.ascii_lowercase[r] if c > 1 else "" for r, c in zip(rank, n)]
    rates["group_name"] = rates["base_name"] + rates["suffix"]
    return rates.drop(columns=["base_name", "suffix"])


def robust_palette(n):
    """Set1 as in the paper, without yellow and grey, extended by Dark2 (without grey)."""
    set1, dark2 = plt.get_cmap("Set1").colors, plt.get_cmap("Dark2").colors
    palette = [c for i, c in enumerate(set1) if i not in (5, 8)] + list(dark2[:7])
    return [palette[i % len(palette)] for i in range(n)]


def load_run(workdir, run, year_field, robust_definition):
    """Reads all outputs of a run. The sensitivity test CSV is optional."""
    gpkg = os.path.join(workdir, f"{run}.gpkg")
    if not os.path.exists(gpkg):
        raise FileNotFoundError(f"'{gpkg}' not found. Run main.py in 'analysis' or 'all' mode first.")
    layers = [name for name, _ in pyogrio.list_layers(gpkg)]

    def layer(name):
        if f"{run}_{name}" not in layers:
            raise ValueError(f"Layer '{run}_{name}' missing in '{gpkg}'. Run main.py in 'analysis' or 'all' mode.")
        return gpd.read_file(gpkg, layer=f"{run}_{name}")

    paths = layer("paths")
    paths_grouped = layer("paths_grouped")
    points = layer("points_grouped").rename(columns={year_field: "year"})
    paths_grouped["group_id"] = pd.to_numeric(paths_grouped["group_id"]).astype(int)
    points["group_id"] = pd.to_numeric(points["group_id"], errors="coerce").astype("Int64")

    rates = group_names(pd.read_csv(os.path.join(workdir, f"{run}_expansion_rates.csv")))
    rates["group_id"] = rates["group_id"].astype(int)
    rates["robust"] = rates["median_points_per_year"] > robust_definition
    rates["expansion_rate_km"] = rates["expansion_rate"] / 1000

    cumdist = pd.read_csv(os.path.join(workdir, f"{run}_cumulative_distances.csv"))
    cumdist["group_id"] = cumdist["group_id"].astype(int)
    cumdist = cumdist.merge(rates[["group_id", "group_name", "robust"]], on="group_id", how="left")

    sens_csv = os.path.join(workdir, f"{run}_sensitivity_test.csv")
    sensitivity = pd.read_csv(sens_csv) if os.path.exists(sens_csv) else None

    return {"run": run, "paths": paths, "paths_grouped": paths_grouped, "points": points, "rates": rates,
            "cumdist": cumdist, "sensitivity": sensitivity}


def applied_threshold(data, threshold=None, threshold_is_absolute=False):
    """
    Returns the accumulated cost threshold and its quantile. The value is calculated from the parameters as in
    main.py and checked against the run's output; if they do not match (e.g. params.py was changed after the run),
    the threshold is approximated from the output.
    """
    cost = data["paths"]["accumulated_cost"].to_numpy()
    if threshold is None:  # default of main.py: upper outlier fence
        q1, q3 = np.quantile(cost, [0.25, 0.75])
        value = q3 + 1.5 * (q3 - q1)
    elif threshold_is_absolute:
        value = threshold
    else:
        value = np.quantile(cost, threshold)

    n_retained = len(data["paths_grouped"])
    if (cost < value).sum() != n_retained:
        value = data["paths_grouped"]["accumulated_cost"].max()
        _log(f"WARNING: The threshold in the parameters does not match run '{data['run']}' "
             f"({n_retained} of {len(cost)} paths retained). Using the highest retained accumulated cost "
             f"({value:.3f}) instead.")
    return value, (cost <= value).mean()


# ============================================ TABLES ==================================================================

def population_table(rates):
    """Tab. 1: all populations, robust ones first (marked with *), sorted by first and last observation year."""
    t = rates.copy()
    t["type"] = np.where(t["robust"], "robust", "sparse")
    t["population"] = t["group_name"] + np.where(t["robust"], " *", "")
    t = t.sort_values(["type", "min_year", "max_year", "group_name"], ascending=[True, True, False, True])
    t["expansion_rate_km_per_year"] = t["expansion_rate_km"].round(1)
    t["r2"] = t["r2"].round(2)
    return t[["population", "group_id", "type", "min_year", "max_year", "point_count", "median_points_per_year",
              "expansion_rate_km_per_year", "r2"]]


def fit_phases(cumdist, breakpoints):
    """
    Tab. 2: expansion rates per phase. 'breakpoints' maps population names to two years (start and end of the
    expansion phase), splitting the observation period into lag, expansion and final phase.
    """
    phases = ["Lag phase", "Expansion phase", "Final phase"]
    rows = []
    for name, (b1, b2) in breakpoints.items():
        g = cumdist[cumdist["group_name"] == name]
        if g.empty:
            _log(f"WARNING: Breakpoints given for population '{name}', which does not exist in this run. "
                 f"Available populations: {', '.join(sorted(cumdist['group_name'].dropna().unique())[:20])} ...")
            continue
        bounds = [g["year"].min(), b1, b2, g["year"].max()]
        for i in range(3):
            seg = g[(g["year"] >= bounds[i]) & (g["year"] <= bounds[i + 1])]
            rate, r2 = np.nan, np.nan
            if seg["year"].nunique() > 1:
                slope, intercept = np.polyfit(seg["year"], seg["max_distance"], 1)
                pred = slope * seg["year"] + intercept
                ss_tot = ((seg["max_distance"] - seg["max_distance"].mean()) ** 2).sum()
                rate = slope / 1000
                r2 = 1 - ((seg["max_distance"] - pred) ** 2).sum() / ss_tot if ss_tot > 0 else np.nan
            rows.append({"population": name, "segment_id": i + 1, "phase": phases[i], "year_from": bounds[i],
                         "year_to": bounds[i + 1], "expansion_rate_km_per_year": round(rate, 1),
                         "r2": round(r2, 2), "n_years": seg["year"].nunique()})
    return pd.DataFrame(rows)


def summary(data, threshold_value, threshold_quantile, robust_definition):
    """Numbers used inline in the results section of the paper."""
    rates = data["rates"]
    robust = rates[rates["robust"]]
    lines = [
        f"Run: {data['run']}",
        f"Years: {int(data['points']['year'].min())}-{int(data['points']['year'].max())}",
        f"Least-cost paths: {len(data['paths'])}, retained after threshold: {len(data['paths_grouped'])}",
        f"Accumulated cost threshold: {threshold_value:.3f} (Q{threshold_quantile:.3f})",
        f"Populations: {len(rates)}, robust (median observations per year > {robust_definition}): {len(robust)}, "
        f"sparse: {len(rates) - len(robust)}",
        f"Isolated observations (no population): {int(data['points']['group_id'].isna().sum())}",
    ]
    if len(robust):
        hi, lo = robust.loc[robust["expansion_rate_km"].idxmax()], robust.loc[robust["expansion_rate_km"].idxmin()]
        lines += [
            f"Median observations per year of robust populations: {robust['median_points_per_year'].min()}"
            f"-{robust['median_points_per_year'].max()}",
            f"Expansion rate of robust populations: {lo['expansion_rate_km']:.1f} ({lo['group_name']}) to "
            f"{hi['expansion_rate_km']:.1f} km/year ({hi['group_name']}), "
            f"mean {robust['expansion_rate_km'].mean():.1f} km/year",
        ]
    return "\n".join(lines)


# ============================================ MAPS ====================================================================

class Basemap:
    """Countries (Natural Earth) and graticule for the extent of the cost surface, in the CRS of the analysis."""

    def __init__(self, cost_path, crs, graticule_step=10):
        with rio.open(cost_path) as src:
            b = src.bounds
            self.extent = (b.left, b.right, b.bottom, b.top)
            bbox = transform_bounds(src.crs, "EPSG:4326", *b, densify_pts=50)
        pad = graticule_step
        self.countries = natural_earth("countries", bbox_4326=(max(bbox[0] - pad, -180), max(bbox[1] - pad, -90),
                                                               min(bbox[2] + pad, 180), min(bbox[3] + pad, 90)),
                                       crs=crs, columns=["NAME"])
        self.graticule = self._graticule(bbox, crs, graticule_step)

    @staticmethod
    def _graticule(bbox, crs, step):
        x0, y0 = np.floor(bbox[0] / step) * step - step, max(np.floor(bbox[1] / step) * step - step, -90)
        x1, y1 = np.ceil(bbox[2] / step) * step + step, min(np.ceil(bbox[3] / step) * step + step, 90)
        lat_s, lon_s = np.linspace(y0, y1, 200), np.linspace(x0, x1, 400)
        lines = [LineString(np.column_stack([np.full_like(lat_s, lon), lat_s])) for lon in np.arange(x0, x1 + 1, step)]
        lines += [LineString(np.column_stack([lon_s, np.full_like(lon_s, lat)])) for lat in np.arange(y0, y1 + 1, step)
                  if -90 < lat < 90]
        return gpd.GeoSeries(lines, crs="EPSG:4326").to_crs(crs)

    def draw(self, ax):
        self.countries.plot(ax=ax, facecolor="#f7f7f7", edgecolor="#bebebe", linewidth=0.5, zorder=0)
        self.graticule.plot(ax=ax, color="#bebebe", linestyle=(0, (4, 3)), linewidth=0.4, zorder=0.5)
        ax.set_xlim(self.extent[0], self.extent[1])
        ax.set_ylim(self.extent[2], self.extent[3])
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.grid(False)


def _coords(geoms):
    out = []
    for g in geoms:
        if g is None or g.is_empty:
            continue
        parts = g.geoms if g.geom_type == "MultiLineString" else [g]
        out += [np.asarray(p.coords)[:, :2] for p in parts]
    return out


def _draw_lines(ax, gdf, colours, linewidth, zorder=2):
    """Draws lines with one colour per feature (much faster than GeoDataFrame.plot for many lines)."""
    segs, cols = [], []
    for geom, c in zip(gdf.geometry, colours):
        parts = _coords([geom])
        segs += parts
        cols += [c] * len(parts)
    ax.add_collection(LineCollection(segs, colors=cols, linewidths=linewidth, capstyle="round", zorder=zorder))


def _draw_isolated(ax, points, label=None):
    iso = points[points["group_id"].isna()]
    ax.scatter(iso.geometry.x, iso.geometry.y, s=4, color=GREY, linewidths=0, zorder=3, label=label)


def map_all_populations(ax, basemap, data, title):
    """Fig. 5b/c: all populations in alternating colours, isolated observations in grey."""
    basemap.draw(ax)
    paths = data["paths_grouped"]
    ids = sorted(paths["group_id"].unique(), key=str)  # factor level order as in R
    colour = {gid: GROUP_PALETTE[i % len(GROUP_PALETTE)] for i, gid in enumerate(ids)}
    _draw_isolated(ax, data["points"])
    _draw_lines(ax, paths, paths["group_id"].map(colour), 1.0)
    ax.set_title(title)


def map_robust_populations(ax, basemap, data, colours):
    """Fig. 6a: robust populations in colour, sparse populations and isolated observations in grey."""
    basemap.draw(ax)
    paths, points, rates = data["paths_grouped"], data["points"], data["rates"]
    robust_ids = set(colours)
    sparse = paths[~paths["group_id"].isin(robust_ids)]
    robust = paths[paths["group_id"].isin(robust_ids)]
    _draw_lines(ax, sparse, [GREY] * len(sparse), 0.8)
    _draw_isolated(ax, points)
    _draw_lines(ax, robust, robust["group_id"].map(colours), 1.2, zorder=4)

    # First observations of robust populations (ringed, with white halo)
    first_year = rates.set_index("group_id")["min_year"]
    in_robust = points["group_id"].isin(list(robust_ids)).fillna(False).astype(bool)
    firsts = points[in_robust]
    firsts = firsts[firsts["year"] == firsts["group_id"].astype(int).map(first_year)]
    ax.scatter(firsts.geometry.x, firsts.geometry.y, s=40, facecolors="none", edgecolors="black", linewidths=0.9,
               zorder=6, path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])

    robust_rates = rates[rates["robust"]].sort_values("group_name")
    handles = [Line2D([], [], color=colours[g], lw=1.5, label=n)
               for g, n in zip(robust_rates["group_id"], robust_rates["group_name"])]
    handles += [Line2D([], [], color=GREY, lw=1.2, label="Sparse population"),
                Line2D([], [], color=GREY, lw=0, marker="o", markersize=3, label="Isolated observation"),
                Line2D([], [], color="black", lw=0, marker="o", markerfacecolor="none", markersize=6,
                       label="First observation")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0)
    ax.set_title("a")


# ============================================ CHARTS ==================================================================

def plot_sensitivity(axes, data, threshold_value, split_at=None):
    """
    Fig. 5a: average expansion rate of robust populations against the accumulated cost threshold, one line per
    robust population definition. 'axes' is one axis, or two if the x axis is split at 'split_at'.
    """
    sens = data["sensitivity"].sort_values("threshold")
    definitions = sorted(sens["definition_robust"].unique())
    cmap = plt.get_cmap("turbo")
    colours = {d: cmap(1 - i / max(len(definitions) - 1, 1)) for i, d in enumerate(definitions)}
    ymax = np.nanmax(sens["avg_rate"]) / 1000 * 1.05 if sens["avg_rate"].notna().any() else 1

    for ax in axes:
        for d in definitions:
            s = sens[sens["definition_robust"] == d]
            ax.plot(s["threshold"], s["avg_rate"] / 1000, color=colours[d], lw=0.9, label=str(d))
        ax.set_ylim(0, ymax)

    xmin, xmax = sens["threshold"].min(), sens["threshold"].max()
    if len(axes) == 2:
        axes[0].set_xlim(xmin, split_at)
        axes[1].set_xlim(split_at, xmax)
        axes[1].tick_params(labelleft=False, left=False)
        axes[0].spines["right"].set_visible(False)
        axes[1].spines["left"].set_visible(False)
    else:
        axes[0].set_xlim(xmin, xmax)

    # Applied threshold
    for ax in axes:
        lo, hi = ax.get_xlim()
        if lo <= threshold_value <= hi:
            ax.axvline(threshold_value, color="black", ls="--", lw=0.8)
            ax.annotate(f"applied threshold: {threshold_value:.3g} —", xy=(threshold_value, ymax * 0.65),
                        xytext=(-2, 0), textcoords="offset points", ha="right", va="center", fontsize=6.5)

    # Quantiles of the accumulated cost distribution on the top axis (only those within the tested range)
    q_ticks, q_labels = [], []
    for q in (0.25, 0.50, 0.75, 0.90, 0.95):
        idx = np.flatnonzero(sens["quantile"].to_numpy() >= q)
        if len(idx) and not (idx[0] == 0 and sens["quantile"].iloc[0] - q > 0.01):
            q_ticks.append(sens["threshold"].iloc[idx[0]])
            q_labels.append(f"Q{q:.2f}")
    ax_q = axes[0]
    top = ax_q.secondary_xaxis("top")
    lo, hi = ax_q.get_xlim()
    sel = [(t, lab) for t, lab in zip(q_ticks, q_labels) if lo <= t <= hi]
    top.set_xticks([t for t, _ in sel], [lab for _, lab in sel], rotation=90, fontsize=6.5)

    axes[0].set_ylabel("Average expansion rate (km/year)")
    axes[0].set_xlabel("Accumulated cost threshold")
    axes[0].set_title("a", pad=24 if sel else None)
    axes[-1].legend(title="Robust population definition\n(median observations per year)", title_fontsize=6.5,
                    loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0, ncol=2 if len(definitions) > 6 else 1)


def plot_histogram(ax, rates, robust_definition, title):
    """Fig. 5d: number of populations per median observations per year, robust populations labelled."""
    values = rates["median_points_per_year"]
    bins = np.arange(0, np.ceil(values.max()) + 2, 1)
    counts, _, _ = ax.hist(values, bins=bins, color="#bebebe", edgecolor="black", linewidth=0.3)
    ytop = counts.max() * 1.1
    ax.axvline(robust_definition, color="black", ls="--", lw=0.8)
    ax.text(robust_definition, ytop * 0.97, "sparse ", ha="right", va="top", fontsize=6.5)
    ax.text(robust_definition, ytop * 0.97, " robust", ha="left", va="top", fontsize=6.5)
    # Labels of robust populations, spread horizontally where they would overlap (with leader lines)
    xmax = bins[-1]
    min_gap = xmax * 0.045
    robust = rates[rates["robust"]].sort_values("median_points_per_year")
    label_x, prev = [], -np.inf
    for x in robust["median_points_per_year"] + 0.5:
        prev = max(x, prev + min_gap)
        label_x.append(prev)
    shift = max(0, label_x[-1] - xmax * 0.98) if label_x else 0  # keep labels inside the panel
    label_x = [max(lx - shift, x + 0.5 - xmax) for lx, x in zip(label_x, robust["median_points_per_year"])]
    y_bar, y_text = counts.max() * 0.03, counts.max() * 0.12
    for lx, r in zip(label_x, robust.itertuples()):
        x = r.median_points_per_year + 0.5
        ax.plot([x, x, lx], [y_bar, y_text * 0.7, y_text * 0.95], color="black", lw=0.4)
        ax.text(lx, y_text, r.group_name, rotation=90, ha="center", va="bottom", fontsize=5.5)
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ytop)
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.yaxis.get_major_locator().set_params(integer=True)
    ax.set_xlabel("Median observations per year")
    ax.set_ylabel("Number of populations")
    ax.set_title(title)


def plot_cumulative_distance(ax, data, colours, breakpoints):
    """Fig. 6b: cumulative distance to the first observation over time for robust populations."""
    cd = data["cumdist"][data["cumdist"]["robust"].fillna(False)].sort_values(["group_name", "year"])
    handles = []
    for i, (name, g) in enumerate(cd.groupby("group_name", sort=True)):
        c = colours[g["group_id"].iloc[0]]
        m = MARKERS[i % len(MARKERS)]
        ax.plot(g["year"], g["max_distance"] / 1000, color=c, lw=1.2, marker=m, markersize=4, label=name)
        handles.append(Line2D([], [], color=c, lw=1.2, marker=m, markersize=4, label=name))
        if name in breakpoints:
            b1, b2 = breakpoints[name]
            seg = g[(g["year"] >= b1) & (g["year"] <= b2)]
            if seg["year"].nunique() > 1:
                slope, intercept = np.polyfit(seg["year"], seg["max_distance"] / 1000, 1)
                ax.plot([b1, b2], [slope * b1 + intercept, slope * b2 + intercept], color=c, lw=0.8, ls="--")
    if breakpoints:
        handles.append(Line2D([], [], color="black", lw=0.8, ls="--", label="Linear model"))
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.set_xlabel("Time (year)")
    ax.set_ylabel("Cumulative distance (km)")
    ax.set_ylim(bottom=0)
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0)
    ax.set_title("b")


# ============================================ FIGURES =================================================================

def figure_sensitivity(data, basemap, threshold_value, robust_definition, compare=None, compare_label=None,
                       split_at=None):
    """Fig. 5. Panels without data (sensitivity test not run, no comparison run) are left out."""
    has_sens = data["sensitivity"] is not None
    if split_at is not None and has_sens and not (data["sensitivity"]["threshold"].min() < split_at
                                                  < data["sensitivity"]["threshold"].max()):
        _log(f"split_at = {split_at} is outside the tested threshold range; x axis is not split.")
        split_at = None

    n_map_rows = 2 if compare is not None else 1
    rows = (1 if has_sens else 0) + 2
    fig = plt.figure(figsize=(6.85, 7 if has_sens else 4.7))
    gs = fig.add_gridspec(rows, 6, hspace=0.5, wspace=0.6)
    letters = iter(string.ascii_lowercase)
    r0 = 0
    if has_sens:
        next(letters)  # "a" is set in plot_sensitivity
        if split_at is None:
            axes = [fig.add_subplot(gs[0, 0:4])]
        else:
            sub = gs[0, 0:4].subgridspec(1, 2, width_ratios=[4, 1], wspace=0.04)
            axes = [fig.add_subplot(sub[0, 0])]
            axes.append(fig.add_subplot(sub[0, 1], sharey=axes[0]))
        plot_sensitivity(axes, data, threshold_value, split_at)
        r0 = 1

    if compare is not None:
        map_all_populations(fig.add_subplot(gs[r0, 0:4]), basemap, compare,
                            f"{next(letters)} – {compare_label or 'comparison run: ' + compare['run']}")
        map_all_populations(fig.add_subplot(gs[r0 + 1, 0:4]), basemap, data,
                            f"{next(letters)} – accumulated cost threshold = {threshold_value:.3g}")
    else:
        map_all_populations(fig.add_subplot(gs[r0:r0 + n_map_rows + 1, 0:4]), basemap, data,
                            f"{next(letters)} – accumulated cost threshold = {threshold_value:.3g}")
    plot_histogram(fig.add_subplot(gs[r0:r0 + 2, 4:6]), data["rates"], robust_definition, next(letters))
    return fig


def figure_populations(data, basemap, breakpoints):
    """Fig. 6."""
    robust = data["rates"][data["rates"]["robust"]].sort_values("group_name")
    colours = dict(zip(robust["group_id"], robust_palette(len(robust))))
    fig, (ax_map, ax_cd) = plt.subplots(2, 1, figsize=(6.85, 6.3), gridspec_kw={"hspace": 0.25})
    map_robust_populations(ax_map, basemap, data, colours)
    plot_cumulative_distance(ax_cd, data, colours, breakpoints)
    return fig


def report(workdir, run, cost_name, out_dir, year_field="year", robust_definition=10, threshold=None,
           threshold_is_absolute=False, compare_run=None, compare_label=None, split_at=None, breakpoints=None,
           formats=("png",), dpi=300):
    breakpoints = breakpoints or {}
    os.makedirs(out_dir, exist_ok=True)
    plt.rcParams.update(STYLE)

    _log(f"Loading results of run '{run}' from '{workdir}'...")
    data = load_run(workdir, run, year_field, robust_definition)
    compare = load_run(workdir, compare_run, year_field, robust_definition) if compare_run else None
    threshold_value, threshold_quantile = applied_threshold(data, threshold, threshold_is_absolute)
    if data["sensitivity"] is None:
        _log("No sensitivity test results found (run main.py in 'test' or 'all' mode); panel a is left out.")

    def out(name):
        return os.path.join(out_dir, f"{run}_{name}")

    text = summary(data, threshold_value, threshold_quantile, robust_definition)
    with open(out("summary.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)

    population_table(data["rates"]).to_csv(out("populations.csv"), index=False)
    if breakpoints:
        fit_phases(data["cumdist"], breakpoints).to_csv(out("phases.csv"), index=False)

    _log("Loading basemap...")
    basemap = Basemap(os.path.join(workdir, cost_name), data["paths"].crs)

    _log("Creating figures...")
    figures = {
        "fig_sensitivity": figure_sensitivity(data, basemap, threshold_value, robust_definition, compare,
                                              compare_label, split_at),
        "fig_populations": figure_populations(data, basemap, breakpoints),
    }
    for name, fig in figures.items():
        for fmt in formats:
            fig.savefig(out(f"{name}.{fmt}"), dpi=dpi)
        plt.close(fig)
    _log(f"Report saved to '{out_dir}'.")
