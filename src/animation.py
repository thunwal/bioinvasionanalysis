"""
Animated map of the reconstructed spread.

Least-cost paths grow year by year towards their destination observation; an observation appears
as soon as its path has reached it. Observations without an incoming path (first records, isolated
observations, or observations whose path was removed by the accumulated cost threshold) appear at the
beginning of their year.

The styling follows the population map of the paper: robust populations are coloured, sparse
populations and isolated observations are grey, and first observations of robust populations are ringed.
"""
import colorsys
import math
import string
from datetime import datetime as dt

import contextily as cx
import geopandas as gpd
import matplotlib
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xyzservices.providers as xyz
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from shapely.ops import linemerge

from src.naturalearth import CACHE_DIR, natural_earth

matplotlib.use("Agg")

GREY = "#8b9a9a"  # close to R's "azure4" used in the paper


def _log(msg):
    print(f"[{dt.now().strftime('%H:%M:%S')}] {msg}")


# ============================================ DATA PREPARATION ========================================================

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


def _as_linestring_coords(geom):
    merged = linemerge(geom) if geom.geom_type == "MultiLineString" else geom
    if merged.geom_type == "LineString":
        return np.asarray(merged.coords)[:, :2]
    # Parts could not be merged into one line: concatenate them in stored order
    return np.vstack([np.asarray(part.coords)[:, :2] for part in merged.geoms])


def prepare_data(in_gpkg, in_paths, in_points, in_rates_csv, year_field, robust_definition,
                 map_crs=None, max_path_length_km=None):
    paths = gpd.read_file(in_gpkg, layer=in_paths)
    points = gpd.read_file(in_gpkg, layer=in_points)
    rates = group_names(pd.read_csv(in_rates_csv))

    if map_crs is not None:
        paths = paths.to_crs(map_crs)
        points = points.to_crs(map_crs)

    # Population attributes
    rates["group_id"] = rates["group_id"].astype(int)
    rates["robust"] = rates["median_points_per_year"] > robust_definition
    robust = rates[rates["robust"]].sort_values("group_name")  # alphabetical order as in ggplot
    # Set1 as in the paper, without its yellow (poorly visible on light maps) and grey (reserved for sparse
    # populations), extended by Dark2 (without grey) for more than seven robust populations
    set1, dark2 = plt.get_cmap("Set1").colors, plt.get_cmap("Dark2").colors
    palette = [c for i, c in enumerate(set1) if i not in (5, 8)] + list(dark2[:7])
    colours = {gid: palette[i % len(palette)] for i, gid in enumerate(robust["group_id"])}
    legend = [(row.group_name, colours[row.group_id]) for row in robust.itertuples()]

    def colour_of(gid):
        return colours.get(gid, GREY)

    # Paths
    paths["group_id"] = pd.to_numeric(paths["group_id"]).astype(int)
    paths["length"] = paths.length
    if max_path_length_km is not None:
        n_before = len(paths)
        paths = paths[paths["length"] <= max_path_length_km * 1000]
        _log(f"Display filter: {n_before - len(paths)} paths longer than {max_path_length_km} km hidden.")
    paths = paths.reset_index(drop=True)
    paths["coords"] = [_as_linestring_coords(g) for g in paths.geometry]
    paths["colour"] = paths["group_id"].map(colour_of)
    paths["robust"] = paths["group_id"].isin(colours)

    # Points
    points = points.rename(columns={year_field: "year"}).reset_index(drop=True)
    points["group_id"] = pd.to_numeric(points["group_id"], errors="coerce").astype("Int64")
    points["colour"] = [colour_of(g) if pd.notna(g) else GREY for g in points["group_id"]]
    points["robust"] = points["group_id"].isin(list(colours)).fillna(False).astype(bool)
    first_years = robust.set_index("group_id")["min_year"]
    points["first"] = [bool(r) and y == first_years.get(int(g), -1)
                       for r, y, g in zip(points["robust"], points["year"], points["group_id"].fillna(-1))]

    return paths, points, legend


def build_timeline(paths, points, grow_window, duration_exponent):
    """
    Assigns each path its growth duration (as fraction of its year) and each point its appearance time
    (in fractional years).

    Within a year, the longest path takes 'grow_window' of the year; shorter paths take
    grow_window * (length / longest) ** duration_exponent.
    """
    longest = paths.groupby("destination_year")["length"].transform("max")
    paths["duration"] = grow_window * (paths["length"] / longest) ** duration_exponent

    # Match each point to the path that ends at it (same year, endpoint in the same cost surface cell).
    # The 'dist' column of the grouped points holds the distance to the nearest path endpoint;
    # its maximum therefore approximates half the cell diagonal.
    tolerance = points["dist"].max() * 1.01 if "dist" in points and points["dist"].notna().any() else 10000
    endpoints = gpd.GeoDataFrame(
        {"year": paths["destination_year"], "duration": paths["duration"]},
        geometry=gpd.points_from_xy([c[-1, 0] for c in paths["coords"]], [c[-1, 1] for c in paths["coords"]]),
        crs=paths.crs,
    )
    points["appear"] = points["year"].astype(float)
    for year, pts in points.groupby("year"):
        ends = endpoints[endpoints["year"] == year]
        if ends.empty:
            continue
        joined = gpd.sjoin_nearest(pts[["geometry"]], ends, how="left", max_distance=tolerance)
        joined = joined[~joined.index.duplicated(keep="first")]
        matched = joined["duration"].notna()
        points.loc[joined.index[matched], "appear"] = year + joined.loc[matched, "duration"]
    n_matched = (points["appear"] % 1 > 0).sum()
    _log(f"{n_matched} of {len(points)} observations are reached by a path; the others appear at the start of their year.")
    return paths, points


# ================================================ RENDERING ===========================================================

def _partial_line(coords, cumlen, fraction):
    """Returns the first 'fraction' (0..1) of a polyline."""
    if fraction >= 1:
        return coords
    target = cumlen[-1] * fraction
    i = int(np.searchsorted(cumlen, target, side="right"))
    if i <= 0:
        return coords[:1]
    if i >= len(coords):
        return coords
    seg = cumlen[i] - cumlen[i - 1]
    t = 0 if seg == 0 else (target - cumlen[i - 1]) / seg
    tip = coords[i - 1] + t * (coords[i] - coords[i - 1])
    return np.vstack([coords[:i], tip])


def _ease(x):
    """Smoothstep easing so paths accelerate and decelerate gently."""
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def _map_extent(points, aspect, padding):
    xmin, ymin, xmax, ymax = points.total_bounds
    w, h = xmax - xmin, ymax - ymin
    xmin, xmax = xmin - w * padding, xmax + w * padding
    ymin, ymax = ymin - h * padding, ymax + h * padding
    w, h = xmax - xmin, ymax - ymin
    cx_, cy_ = (xmin + xmax) / 2, (ymin + ymax) / 2
    if w / h < aspect:
        w = h * aspect
    else:
        h = w / aspect
    return cx_ - w / 2, cx_ + w / 2, cy_ - h / 2, cy_ + h / 2


def _resolve_provider(name):
    provider = xyz
    for part in name.split("."):
        provider = provider[part]
    return provider


def _outline_colour(water_colour, border_colour):
    """Water outlines: hue and saturation of the water colour, lightness of the border colour."""
    h, _, sat = colorsys.rgb_to_hls(*matplotlib.colors.to_rgb(water_colour))
    _, lightness, _ = colorsys.rgb_to_hls(*matplotlib.colors.to_rgb(border_colour))
    return matplotlib.colors.to_hex(colorsys.hls_to_rgb(h, lightness, min(sat, 0.35)))


def _relief_basemap(ax, crs, zoom, extent, relief_strength, water_colour, border_colour, cache_dir, scale):
    """
    Light grey relief (Esri World Shaded Relief) with water bodies and country borders from Natural Earth.
    """
    x0, x1, y0, y1 = extent
    corners = gpd.GeoSeries(gpd.points_from_xy([x0, x1, x0, x1], [y0, y0, y1, y1]), crs=crs)
    # Generous margin, since a rectangle in a conic projection is not a rectangle in lon/lat
    lon, lat = corners.to_crs(4326).x, corners.to_crs(4326).y
    bbox_4326 = (lon.min() - 5, max(lat.min() - 5, -85), lon.max() + 5, min(lat.max() + 5, 85))

    w, s, e, n = bbox_4326
    img, img_ext = cx.bounds2img(w, s, e, n, zoom=zoom, ll=True, source=xyz.Esri.WorldShadedRelief)
    img, img_ext = cx.warp_tiles(img, img_ext, t_crs=crs)
    rgb = img[..., :3].astype(float) / 255
    alpha = img[..., 3] if img.shape[-1] == 4 else np.full(img.shape[:2], 255)
    grey = rgb @ np.array([0.299, 0.587, 0.114])
    # Flat terrain has a grey value of about 0.83 in these tiles. It is mapped to a near-white land colour;
    # sunlit and shaded slopes deviate from it, scaled by 'relief_strength'.
    light = np.clip(0.95 + (grey - 0.83) * relief_strength, 0, 1)
    light[alpha == 0] = 0.95
    ax.imshow(light, cmap="gray", vmin=0, vmax=1, extent=img_ext, interpolation="bilinear", zorder=0)

    outline = _outline_colour(water_colour, border_colour)
    for layer in ("ocean", "lakes"):
        natural_earth(layer, bbox_4326, crs, cache_dir).plot(ax=ax, facecolor=water_colour, edgecolor=outline,
                                                             linewidth=0.6 * scale, zorder=1)
    natural_earth("borders", bbox_4326, crs, cache_dir).plot(ax=ax, color=border_colour, linewidth=0.7 * scale,
                                                             zorder=2)
    ax.text(0.995, 0.005, "Relief: Esri | Water, borders: Natural Earth", transform=ax.transAxes, ha="right",
            va="bottom", fontsize=6 * scale, color="#666", zorder=10)


def animate(in_gpkg, in_paths, in_points, in_rates_csv, out_file, year_field="year", robust_definition=10,
            basemap="relief", basemap_zoom="auto", relief_strength=1.0, water_colour="#dce9f2",
            border_colour="#9a9a9a", cache_dir=None, map_crs=None, max_path_length_km=None,
            title="", fps=30, seconds_per_year=3.0, hold_start=1.0, hold_end=3.0,
            grow_window=0.75, duration_exponent=0.5, width_px=1920, height_px=1080, dpi=150, padding=0.05,
            preview_year=None):
    """
    Renders the spread animation to 'out_file' (.mp4 via ffmpeg, or .gif).
    If 'preview_year' is set (e.g. 2019.5), only a single still frame at that time is written as PNG instead.
    """
    if cache_dir is None:
        cache_dir = CACHE_DIR
    paths, points, legend = prepare_data(in_gpkg, in_paths, in_points, in_rates_csv, year_field,
                                         robust_definition, map_crs, max_path_length_km)
    paths, points = build_timeline(paths, points, grow_window, duration_exponent)
    paths["cumlen"] = [np.concatenate([[0], np.cumsum(np.hypot(*np.diff(c, axis=0).T))]) for c in paths["coords"]]

    start_year, end_year = int(points["year"].min()), int(points["year"].max())
    _log(f"Animating {len(paths)} paths and {len(points)} observations from {start_year} to {end_year}.")

    # Figure: one axes filling the whole canvas
    scale = width_px / 1920  # keeps text and line sizes proportional to the output resolution
    fig = plt.figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_axis_off()
    x0, x1, y0, y1 = _map_extent(points, width_px / height_px, padding)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)

    # Basemap: tiles are downloaded for the current extent and warped to the map CRS
    if basemap_zoom == "auto":
        # Choose the tile zoom level whose resolution matches the output width (tiles are 256 px wide)
        lon = gpd.GeoSeries(gpd.points_from_xy([x0, x1, x0, x1], [y0, y0, y1, y1]), crs=points.crs).to_crs(4326).x
        basemap_zoom = int(np.clip(math.ceil(math.log2(width_px / 256 * 360 / (lon.max() - lon.min()))), 0, 18))
    _log(f"Loading basemap '{basemap}' at zoom level {basemap_zoom}...")
    if basemap == "relief":
        _relief_basemap(ax, points.crs, basemap_zoom, (x0, x1, y0, y1), relief_strength, water_colour,
                        border_colour, cache_dir, scale)
    else:
        cx.add_basemap(ax, crs=points.crs, source=_resolve_provider(basemap), zoom=basemap_zoom,
                       attribution_size=6 * scale, reset_extent=True)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)

    # Artists
    lw = 1.6 * scale
    done_lines = LineCollection([], linewidths=lw, capstyle="round", joinstyle="round", zorder=3)
    grow_lines = LineCollection([], linewidths=lw * 1.4, capstyle="round", joinstyle="round", zorder=4)
    ax.add_collection(done_lines)
    ax.add_collection(grow_lines)
    tips = ax.scatter([], [], s=(14 * scale) ** 1, c="white", edgecolors="none", zorder=5)

    pts_xy = np.column_stack([points.geometry.x, points.geometry.y])
    pts_rgba = np.array([matplotlib.colors.to_rgba(c) for c in points["colour"]])
    base_size = np.where(points["robust"], 16, 9) * scale ** 2
    dots = ax.scatter(pts_xy[:, 0], pts_xy[:, 1], s=np.zeros(len(points)), c=pts_rgba,
                      edgecolors="white", linewidths=0.4 * scale, zorder=6)
    firsts = points[points["first"]]
    rings = ax.scatter(firsts.geometry.x, firsts.geometry.y, s=np.zeros(len(firsts)), facecolors="none",
                       edgecolors="black", linewidths=1.4 * scale, zorder=7)

    halo = [pe.withStroke(linewidth=4 * scale, foreground="white")]
    year_text = ax.text(0.025, 0.04, "", transform=ax.transAxes, fontsize=44 * scale, fontweight="bold",
                        color="#222", path_effects=halo, zorder=10)
    count_text = ax.text(0.025, 0.135, "", transform=ax.transAxes, fontsize=11 * scale, color="#333",
                         path_effects=[pe.withStroke(linewidth=3 * scale, foreground="white")], zorder=10)
    if title:
        ax.text(0.025, 0.955, title, transform=ax.transAxes, fontsize=18 * scale, fontweight="bold",
                color="#222", va="top", path_effects=halo, zorder=10)

    handles = [Line2D([], [], color=c, lw=3 * scale, label=n) for n, c in legend]
    handles += [Line2D([], [], color=GREY, lw=3 * scale, label="Sparse population"),
                Line2D([], [], color=GREY, marker="o", lw=0, markersize=4 * scale, label="Isolated observation"),
                Line2D([], [], color="black", marker="o", markerfacecolor="none", lw=0, markersize=8 * scale,
                       markeredgewidth=1.4 * scale, label="First observation")]
    ax.legend(handles=handles, loc="upper right", fontsize=10 * scale, frameon=True, framealpha=0.85,
              edgecolor="none", borderpad=0.8 * scale)

    years = paths["destination_year"].to_numpy()
    dur = paths["duration"].to_numpy()
    path_rgba = np.array([matplotlib.colors.to_rgba(c) for c in paths["colour"]])
    path_rgba[~paths["robust"].to_numpy(), 3] = 0.7
    done_rgba = path_rgba.copy()
    done_rgba[:, 3] *= 0.75
    pop_duration = 0.08  # in years

    def draw(t):
        year = min(int(math.floor(t)), end_year)
        frac = t - year

        # Paths of earlier years and finished paths of the current year
        finished = (years < year) | ((years == year) & (dur <= frac))
        idx = np.flatnonzero(finished)
        done_lines.set_segments([paths.at[i, "coords"] for i in idx])
        done_lines.set_color(done_rgba[idx])

        # Paths growing in the current year
        idx = np.flatnonzero((years == year) & (dur > frac))
        segs, tip_xy = [], []
        for i in idx:
            seg = _partial_line(paths.at[i, "coords"], paths.at[i, "cumlen"], _ease(frac / dur[i]))
            segs.append(seg)
            tip_xy.append(seg[-1])
        grow_lines.set_segments(segs)
        grow_lines.set_color(path_rgba[idx])
        tips.set_offsets(np.array(tip_xy) if tip_xy else np.empty((0, 2)))

        # Observations pop up when reached: overshoot, then settle to base size
        age = t - points["appear"].to_numpy()
        pop = np.clip(age / pop_duration, 0, 1)
        size = np.where(age < 0, 0, base_size * (1 + 1.5 * np.sin(np.pi * pop) * (pop < 1)))
        dots.set_sizes(size)
        first_age = age[points["first"].to_numpy()]
        rings.set_sizes(np.where(first_age < 0, 0, 90 * scale ** 2))

        year_text.set_text(str(year))
        n = int((age >= 0).sum())
        count_text.set_text(f"{n} observation{'s' if n != 1 else ''}")
        return done_lines, grow_lines, tips, dots, rings, year_text, count_text

    if preview_year is not None:
        draw(float(preview_year))
        out_png = out_file.rsplit(".", 1)[0] + f"_preview_{preview_year}.png"
        fig.savefig(out_png, dpi=dpi)
        plt.close(fig)
        _log(f"Preview saved to '{out_png}'.")
        return out_png

    # Timeline: hold first frame, animate each year, hold final state
    t_anim = np.linspace(start_year, end_year + 1, int((end_year + 1 - start_year) * seconds_per_year * fps),
                         endpoint=False)
    times = np.concatenate([np.full(int(hold_start * fps), float(start_year)), t_anim,
                            np.full(int(hold_end * fps), end_year + 0.999)])

    anim = FuncAnimation(fig, draw, frames=times, blit=False)
    if out_file.lower().endswith(".gif"):
        writer = PillowWriter(fps=fps)
    else:
        writer = FFMpegWriter(fps=fps, codec="libx264", extra_args=["-pix_fmt", "yuv420p", "-crf", "18"])
    _log(f"Rendering {len(times)} frames to '{out_file}'...")
    anim.save(out_file, writer=writer, dpi=dpi,
              progress_callback=lambda i, n: _log(f"Frame {i}/{n}") if i % (fps * 5) == 0 else None)
    plt.close(fig)
    _log(f"Animation saved to '{out_file}'.")
    return out_file
