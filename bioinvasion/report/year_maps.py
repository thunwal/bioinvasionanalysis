"""
One map per year: the state of the spread at the end of each year, in the style of the population map of the paper
(Fig. 6a). Robust populations are coloured, sparse populations and isolated observations are grey, first observations
of robust populations are ringed. The maps have no title and no source credits, so they can be used in any layout;
the year is in the file name (<year>.png).
"""
import os

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D

from bioinvasion.report.figures import GREY, STYLE, _draw_lines, robust_palette


def year_maps(data, basemap, out_dir, dpi=150, width_cm=16, log=print):
    """Writes <out_dir>/<year>.png for every year from the first to the last observation. Returns the file paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths, points, rates = data["paths_grouped"], data["points"], data["rates"]
    robust = rates[rates["robust"]].sort_values("group_name")
    colours = dict(zip(robust["group_id"], robust_palette(len(robust))))  # the same colour in every year
    in_robust = points["group_id"].isin(list(colours)).fillna(False).astype(bool)
    first_year = rates.set_index("group_id")["min_year"]
    firsts = points[in_robust]
    firsts = firsts[firsts["year"] == firsts["group_id"].astype(int).map(first_year)]

    handles = [Line2D([], [], color=colours[g], lw=1.5, label=n) for g, n in zip(robust["group_id"],
                                                                               robust["group_name"])]
    handles += [Line2D([], [], color=GREY, lw=1.2, label="Sparse population"),
                Line2D([], [], color=GREY, lw=0, marker="o", markersize=3, label="Isolated observation"),
                Line2D([], [], color="black", lw=0, marker="o", markerfacecolor="none", markersize=6,
                       label="First observation")]

    files = []
    width = width_cm / 2.54
    x0, x1, y0, y1 = basemap.extent
    for year in range(int(points["year"].min()), int(points["year"].max()) + 1):
        with plt.rc_context(STYLE):
            fig, ax = plt.subplots(figsize=(width, width * (y1 - y0) / (x1 - x0) * 0.8 + 0.3))
            basemap.draw(ax)
            p = paths[paths["destination_year"] <= year]
            o = points[points["year"] <= year]
            sparse = p[~p["group_id"].isin(colours)]
            rob = p[p["group_id"].isin(colours)]
            _draw_lines(ax, sparse, [GREY] * len(sparse), 0.8)
            iso_or_sparse = o[~o["group_id"].isin(list(colours)).fillna(False).astype(bool)]
            ax.scatter(iso_or_sparse.geometry.x, iso_or_sparse.geometry.y, s=4, color=GREY, linewidths=0, zorder=3)
            _draw_lines(ax, rob, rob["group_id"].map(colours), 1.2, zorder=4)
            pop = o[o["group_id"].isin(list(colours)).fillna(False).astype(bool)]
            ax.scatter(pop.geometry.x, pop.geometry.y, s=5, linewidths=0, zorder=5,
                       color=[colours[g] for g in pop["group_id"]])
            f = firsts[firsts["year"] <= year]
            ax.scatter(f.geometry.x, f.geometry.y, s=40, facecolors="none", edgecolors="black", linewidths=0.9,
                       zorder=6, path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
            ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0)
            path = os.path.join(out_dir, f"{year}.png")
            fig.savefig(path, dpi=dpi)
            plt.close(fig)
        files.append(path)
    log(f"Year maps: {len(files)} maps saved to '{out_dir}'.")
    return files
