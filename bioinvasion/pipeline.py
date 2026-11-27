"""
The analysis in stages, on a project folder. This is the only module that reads and writes files; the computations
are in bioinvasion/core and work on GeoDataFrames in memory.

    stage        function            output (in the project folder)
    1 import     import_presence()   presence/presence.gpkg, presence/import_report.txt
    2 paths      compute_paths()     paths__<cost>__<years>/paths.gpkg
    3 sweep      sweep()             paths__.../sweep_coarse.csv, paths__.../sweep__<from>-<to>x<step>.csv
    4 delineate  delineate()         paths__.../delin__t<threshold>__r<robust>/populations.gpkg + CSVs
    5 report     report()            paths__.../delin__.../report/

Every stage writes a manifest (settings, input file hashes, code version, results) next to its output. A stage whose
manifest matches the current settings and inputs is skipped (the log says so), and every stage first brings the
stages it depends on up to date. So changing the threshold reuses the least-cost paths.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime as dt

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio as rio

from bioinvasion.core.expansionrate import expansion_rate
from bioinvasion.core.leastcostpaths import least_cost_paths
from bioinvasion.core.populations import delineate as delineate_core
from bioinvasion.core.sensitivity import sweep as sweep_core
from bioinvasion.core.thinning import filter_points, thin
from bioinvasion.report import insights
from bioinvasion.report.figures import Basemap, build_run_data, write_outputs
from bioinvasion.sources.files import read_csv, read_gpkg

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log(msg):
    print(f"[{dt.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ============================================ MANIFESTS ===============================================================

def code_version():
    """BIOINVASION_VERSION, else the git commit (with '+changes' if there are uncommitted changes), else the package
    version."""
    if os.environ.get("BIOINVASION_VERSION"):
        return os.environ["BIOINVASION_VERSION"]
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True,
                             check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "bioinvasion"], cwd=REPO, capture_output=True,
                               text=True).stdout.strip()
        return sha + ("+changes" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        pass
    try:  # no git, e.g. in the Docker image: version of the installed package (pyproject.toml)
        from importlib.metadata import version
        return f"bioinvasion {version('bioinvasion')}"
    except Exception:
        return "unknown"


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_default(o):
    if isinstance(o, np.generic):
        return o.item()
    raise TypeError(f"not JSON serialisable: {type(o)}")


def write_manifest(path, stage, settings, inputs, results=None):
    manifest = {"stage": stage, "settings": settings, "inputs": inputs, "results": results or {},
                "code_version": code_version(), "created": dt.now().astimezone().isoformat(timespec="seconds")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=_json_default)
    return manifest


def read_manifest(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _same(a, b):
    return json.loads(json.dumps(a, default=_json_default)) == json.loads(json.dumps(b, default=_json_default))


def up_to_date(manifest_path, settings, inputs, outputs):
    """True if all outputs exist and the manifest has the same settings and input hashes."""
    m = read_manifest(manifest_path)
    return (m is not None and all(os.path.exists(o) for o in outputs)
            and _same(m["settings"], settings) and _same(m["inputs"], inputs))


# ============================================ 1 IMPORT ================================================================

def presence_path(cfg):
    return cfg.path(os.path.join("presence", "presence.gpkg"))


def import_presence(cfg, log=log, progress=None, force=False):
    """Stage 1: reads the observations into the standard schema (see bioinvasion/sources/files.py)."""
    out = presence_path(cfg)
    folder = os.path.dirname(out)
    manifest = os.path.join(folder, "manifest.json")
    d = cfg.data
    if d.source == "inaturalist":
        settings = {k: getattr(d, k) for k in ("source", "taxon", "research_grade_only", "include_obscured",
                                               "max_positional_accuracy_m")}
        settings["bbox_of"] = cfg.cost.file
        inputs = {"cost": file_hash(cfg.path(cfg.cost.file))}
    else:
        settings = {k: getattr(d, k) for k in ("source", "file", "layer")}
        inputs = {"file": file_hash(cfg.path(d.file))}
    if not force and up_to_date(manifest, settings, inputs, [out]):
        log(f"Import: up to date ('{out}').")
        return out

    if d.source == "csv":
        gdf, report = read_csv(cfg.path(d.file))
    elif d.source == "gpkg":
        gdf, report = read_gpkg(cfg.path(d.file), d.layer or None)
    else:
        from bioinvasion.sources.inaturalist import fetch_inaturalist, raster_bbox_4326
        with rio.open(cfg.path(cfg.cost.file)) as cost:
            bbox = raster_bbox_4326(cost)
        gdf, report = fetch_inaturalist(d.taxon, bbox, d.research_grade_only, d.include_obscured,
                                        d.max_positional_accuracy_m, log=log, progress=progress)
    os.makedirs(folder, exist_ok=True)
    gdf.to_file(out, layer="presence")
    with open(os.path.join(folder, "import_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    write_manifest(manifest, "import", settings, inputs, {"report": report, "observations": len(gdf)})
    for line in report:
        log(f"Import: {line}")
    return out


# ============================================ 2 PATHS =================================================================

def check_cost_surface(cost):
    """Requirements of the least-cost analysis. Raises ValueError with an explanation."""
    if cost.crs is None or not cost.crs.is_projected:
        raise ValueError("The cost surface must be in a projected coordinate reference system (distances in metres), "
                         f"but has {cost.crs}.")
    if cost.res[0] != cost.res[1]:
        raise ValueError(f"The cost surface must have square cells, but has {cost.res[0]} x {cost.res[1]}.")


def year_range(cfg, presence, log=log):
    start, end = cfg.data.start_year, cfg.data.end_year
    if start is None:
        start = int(presence["year"].min())
        log(f"start_year not set: using the earliest year in the data, {start}.")
    if end is None:
        end = int(presence["year"].max())
        log(f"end_year not set: using the latest year in the data, {end}.")
    return start, end


def paths_folder(cfg, start, end):
    return cfg.path(f"paths__{cfg.cost_label}__{start}-{end}")


def current_paths_folder(cfg):
    """The paths folder for the current settings (it may not exist yet). Requires imported observations."""
    years = gpd.read_file(presence_path(cfg), layer="presence", columns=["year"], ignore_geometry=True)
    start, end = year_range(cfg, years, log=lambda msg: None)
    return paths_folder(cfg, start, end)


def compute_paths(cfg, log=log, progress=None, force=False):
    """Stage 2: filters and thins the observations and calculates the least-cost paths. Returns the folder."""
    presence_file = import_presence(cfg, log)
    presence = gpd.read_file(presence_file, layer="presence")
    start, end = year_range(cfg, presence, log)
    folder = paths_folder(cfg, start, end)
    out, manifest = os.path.join(folder, "paths.gpkg"), os.path.join(folder, "manifest.json")
    settings = {"start_year": start, "end_year": end, "cost_file": cfg.cost.file}
    inputs = {"presence": file_hash(presence_file), "cost": file_hash(cfg.path(cfg.cost.file))}
    if not force and up_to_date(manifest, settings, inputs, [out]):
        log(f"Paths: up to date ('{folder}').")
        return folder
    if os.path.exists(folder):
        log(f"Paths: inputs or settings changed, removing the outdated results in '{folder}'.")
        shutil.rmtree(folder)

    with rio.open(cfg.path(cfg.cost.file)) as cost:
        check_cost_surface(cost)
        points, removed = filter_points(presence, cost, start, end)
        for reason, n in removed:
            log(f"Paths: removed {n} observations ({reason}).")
        points_thinned = thin(points, cost)
        log(f"Paths: {len(points)} observations, {len(points_thinned)} after keeping the earliest per cell.")
        paths = least_cost_paths(points_thinned, cost, start, end, progress=progress, log=log)
        cell_size = cost.res[0]
    os.makedirs(folder)
    points.to_file(out, layer="points")
    points_thinned.to_file(out, layer="points_thinned")
    paths.to_file(out, layer="paths")
    write_manifest(manifest, "paths", settings, inputs, {
        "observations_in_presence": len(presence), "removed": removed, "observations": len(points),
        "observations_thinned": len(points_thinned), "paths": len(paths), "cell_size": cell_size,
        "max_accumulated_cost": float(paths["accumulated_cost"].max())})
    log(f"Paths: {len(paths)} least-cost paths saved to '{out}'.")
    return folder


def load_paths(folder):
    out = os.path.join(folder, "paths.gpkg")
    manifest = read_manifest(os.path.join(folder, "manifest.json"))
    return {"points": gpd.read_file(out, layer="points"), "points_thinned": gpd.read_file(out, layer="points_thinned"),
            "paths": gpd.read_file(out, layer="paths"), "cell_size": manifest["results"]["cell_size"],
            "manifest": manifest}


# ============================================ 3 SWEEP =================================================================

def _run_sweep(folder, name, thresholds, robust_definitions, extra, log, progress):
    out, manifest = os.path.join(folder, f"{name}.csv"), os.path.join(folder, f"{name}.manifest.json")
    settings = {"thresholds_from": float(thresholds[0]), "thresholds_to": float(thresholds[-1]),
                "steps": len(thresholds), "robust_definitions": list(robust_definitions), **extra}
    inputs = {"paths": file_hash(os.path.join(folder, "paths.gpkg"))}
    if up_to_date(manifest, settings, inputs, [out]):
        log(f"Sweep: up to date ('{out}').")
        return pd.read_csv(out)
    run = load_paths(folder)
    log(f"Sweep: {len(thresholds)} thresholds from {thresholds[0]:g} to {thresholds[-1]:g}, robust definitions "
        f"{robust_definitions[0]:g} to {robust_definitions[-1]:g}...")
    result = sweep_core(run["paths"], run["points"], run["cell_size"], thresholds, robust_definitions, progress)
    result.to_csv(out, index=False)
    write_manifest(manifest, "sweep", settings, inputs)
    log(f"Sweep: saved to '{out}'.")
    return result


def sweep(cfg, fine_from=None, fine_to=None, fine_step=None, log=log, progress=None):
    """
    Stage 3: overview sweep over the whole range of accumulated costs, then a high-resolution sweep over the
    suggested range (or the range given here or in [sweep]). Returns (coarse, fine, range) with range a dict that
    includes the rule by which it was chosen.
    """
    folder = compute_paths(cfg, log)
    costs = load_paths(folder)["paths"]["accumulated_cost"].to_numpy()
    definitions = cfg.robust_definitions()
    thresholds, step = insights.coarse_thresholds(costs, cfg.sweep.coarse_steps)
    coarse = _run_sweep(folder, "sweep_coarse", thresholds, definitions, {"step": step}, log, progress)

    s = cfg.sweep
    if fine_from is None and s.fine_from is not None:
        fine_from, fine_to, fine_step = s.fine_from, s.fine_to, s.fine_step
    if fine_from is not None:
        chosen = {"from": float(fine_from), "to": float(fine_to), "step": float(fine_step),
                  "rule": "Range set by the user."}
    else:
        chosen = insights.suggest_fine_range(coarse, costs, cfg.delineation.robust_definition, s)
    log(f"Sweep: high-resolution range {chosen['from']:g} to {chosen['to']:g} by {chosen['step']:g}. "
        f"{chosen['rule']}")
    n = int(round((chosen["to"] - chosen["from"]) / chosen["step"])) + 1
    fine_thresholds = (chosen["from"] + np.arange(n) * chosen["step"]).round(12)
    name = f"sweep__{chosen['from']:g}-{chosen['to']:g}x{chosen['step']:g}"
    fine = _run_sweep(folder, name, fine_thresholds, definitions, {"range": chosen}, log, progress)
    return coarse, fine, chosen


def latest_fine_sweep(folder):
    """The most recent high-resolution sweep of a paths folder: (DataFrame, range dict) or (None, None)."""
    files = sorted(glob.glob(os.path.join(folder, "sweep__*.csv")), key=os.path.getmtime)
    if not files:
        return None, None
    manifest = read_manifest(files[-1].replace(".csv", ".manifest.json"))
    return pd.read_csv(files[-1]), manifest["settings"]["range"]


def load_sweeps(folder):
    """All sweeps of a paths folder combined (high resolution where available), or None."""
    files = sorted(glob.glob(os.path.join(folder, "sweep*.csv")))
    if not files:
        return None
    combined = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    combined["threshold"] = combined["threshold"].round(10)
    return combined.drop_duplicates(["threshold", "definition_robust"]).sort_values(
        ["definition_robust", "threshold"]).reset_index(drop=True)


# ============================================ 4 DELINEATE =============================================================

def _threshold(cfg, threshold):
    threshold = cfg.delineation.threshold if threshold is None else threshold
    if threshold is None:
        raise ValueError("No accumulated cost threshold set. Look at the sensitivity sweep (python cli.py sweep "
                         "<project>), then set [delineation] threshold in project.toml or use --threshold.")
    return float(threshold)


def delineation_folder(paths_dir, threshold, robust_definition):
    return os.path.join(paths_dir, f"delin__t{threshold:g}__r{robust_definition:g}")


def delineate(cfg, threshold=None, robust_definition=None, log=log):
    """Stage 4: populations and expansion rates for one threshold. Returns the folder."""
    threshold = _threshold(cfg, threshold)
    robust_definition = cfg.delineation.robust_definition if robust_definition is None else robust_definition
    paths_dir = compute_paths(cfg, log)
    run = load_paths(paths_dir)
    paths_grouped, points_grouped, quantile = delineate_core(run["paths"], run["points"], threshold, run["cell_size"])
    cumulative_distances, rates = expansion_rate(points_grouped)
    folder = delineation_folder(paths_dir, threshold, robust_definition)
    os.makedirs(folder, exist_ok=True)
    out = os.path.join(folder, "populations.gpkg")
    if os.path.exists(out):
        os.remove(out)
    paths_grouped.to_file(out, layer="paths_grouped")
    points_grouped.to_file(out, layer="points_grouped")
    rates.to_csv(os.path.join(folder, "expansion_rates.csv"), index=False)
    cumulative_distances.to_csv(os.path.join(folder, "cumulative_distances.csv"), index=False)
    write_manifest(os.path.join(folder, "manifest.json"), "delineate",
                   {"threshold": threshold, "robust_definition": robust_definition},
                   {"paths": file_hash(os.path.join(paths_dir, "paths.gpkg"))},
                   {"threshold_quantile": quantile, "paths_kept": len(paths_grouped), "populations": len(rates),
                    "isolated_observations": int(points_grouped["group_id"].isna().sum())})
    log(f"Delineation: threshold {threshold:g} (Q{quantile:.3f}) keeps {len(paths_grouped)} of {len(run['paths'])} "
        f"paths; {len(rates)} populations. Saved to '{folder}'.")
    return folder


def load_delineation(folder, robust_definition=None):
    """Data structure of report.figures.build_run_data for a delineation folder (with all sweeps of its paths)."""
    paths_dir = os.path.dirname(folder)
    manifest = read_manifest(os.path.join(folder, "manifest.json"))
    robust_definition = manifest["settings"]["robust_definition"] if robust_definition is None else robust_definition
    gpkg = os.path.join(folder, "populations.gpkg")
    data = build_run_data(
        run=os.path.basename(folder),
        paths=gpd.read_file(os.path.join(paths_dir, "paths.gpkg"), layer="paths"),
        paths_grouped=gpd.read_file(gpkg, layer="paths_grouped"),
        points_grouped=gpd.read_file(gpkg, layer="points_grouped"),
        rates=pd.read_csv(os.path.join(folder, "expansion_rates.csv")),
        cumdist=pd.read_csv(os.path.join(folder, "cumulative_distances.csv")),
        sensitivity=load_sweeps(paths_dir),
        year_field="year",
        robust_definition=robust_definition)
    data["threshold"] = manifest["settings"]["threshold"]
    data["threshold_quantile"] = manifest["results"]["threshold_quantile"]
    return data


# ============================================ 5 REPORT ================================================================

def report(cfg, threshold=None, robust_definition=None, compare_threshold=None, log=log):
    """Stage 5: figures and tables of the paper for one delineation. Returns (folder, summary, checks)."""
    import matplotlib
    matplotlib.use("Agg")
    folder = delineate(cfg, threshold, robust_definition, log)
    data = load_delineation(folder)
    compare, compare_label = None, None
    if compare_threshold is not None:
        compare = load_delineation(delineate(cfg, compare_threshold, robust_definition, log))
        compare_label = f"accumulated cost threshold = {compare_threshold:g}"
    if data["sensitivity"] is None:
        log("Report: no sweep found (python cli.py sweep <project>); the sensitivity panel is left out.")
    basemap = Basemap(cfg.path(cfg.cost.file), data["paths"].crs)
    r = cfg.report
    breakpoints = {name: tuple(years) for name, years in r.breakpoints.items()}
    out_dir = os.path.join(folder, "report")
    text = write_outputs(data, basemap, data["threshold"], data["threshold_quantile"], data["robust_definition"],
                         out_dir, compare, compare_label, r.split_at, breakpoints, r.formats, r.dpi)
    checks = insights.delineation_checks(data)
    if data["sensitivity"] is not None:
        checks += insights.sweep_checks(data["sensitivity"], data["threshold"], data["robust_definition"])
    log(f"Report: saved to '{out_dir}'.")
    return out_dir, text, checks


# ============================================ 6 YEAR MAPS AND EXPORT ==================================================

def year_maps(cfg, threshold=None, robust_definition=None, log=log):
    """One PNG per year end (no title, no source credits). Returns the folder."""
    import matplotlib
    matplotlib.use("Agg")
    from bioinvasion.report.year_maps import year_maps as draw_year_maps
    folder = delineate(cfg, threshold, robust_definition, log)
    data = load_delineation(folder)
    basemap = Basemap(cfg.path(cfg.cost.file), data["paths"].crs)
    out_dir = os.path.join(folder, "years")
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    draw_year_maps(data, basemap, out_dir, cfg.year_maps.dpi, cfg.year_maps.width_cm, log=log)
    return out_dir


def settings_text(folder):
    """The settings and numbers of a delineation in words, for the methods section."""
    paths_dir = os.path.dirname(folder)
    project_dir = os.path.dirname(paths_dir)
    imp = read_manifest(os.path.join(project_dir, "presence", "manifest.json"))
    pth = read_manifest(os.path.join(paths_dir, "manifest.json"))
    dln = read_manifest(os.path.join(folder, "manifest.json"))
    p, d = pth["results"], dln["results"]
    lines = ["Settings and numbers of this analysis (bioinvasionanalysis, Rohrbach et al. 2025)", "",
             "Observations:"]
    lines += [f"  {line}" for line in imp["results"]["report"]]
    lines += [f"  Years analysed: {pth['settings']['start_year']}-{pth['settings']['end_year']}"]
    lines += [f"  Removed: {n} ({reason})" for reason, n in p["removed"] if n]
    lines += [f"  Observations analysed: {p['observations']}; after keeping the earliest per cost surface cell: "
              f"{p['observations_thinned']}",
              "", "Least-cost paths:",
              f"  Cost surface: {pth['settings']['cost_file']} (cell size {p['cell_size']:g})",
              f"  Paths: {p['paths']}; highest accumulated cost {p['max_accumulated_cost']:.4g}",
              "", "Population delineation:",
              f"  Accumulated cost threshold: {dln['settings']['threshold']:g} (Q{d['threshold_quantile']:.3f}); "
              f"paths kept: {d['paths_kept']}",
              f"  Robust population: median observations per year > {dln['settings']['robust_definition']:g}",
              f"  Populations: {d['populations']}; isolated observations: {d['isolated_observations']}"]
    sweeps = sorted(glob.glob(os.path.join(paths_dir, "sweep*.manifest.json")))
    if sweeps:
        lines += ["", "Sensitivity sweep:"]
        for path in sweeps:
            s = read_manifest(path)["settings"]
            lines.append(f"  {os.path.basename(path).replace('.manifest.json', '.csv')}: {s['steps']} thresholds "
                         f"from {s['thresholds_from']:g} to {s['thresholds_to']:g}, robust definitions "
                         f"{min(s['robust_definitions']):g}-{max(s['robust_definitions']):g}")
            if "range" in s:
                lines.append(f"    {s['range']['rule']}")
    lines += ["", f"Code version: {dln['code_version']}; created {dln['created']}"]
    return "\n".join(lines)


def export(cfg, threshold=None, robust_definition=None, log=log):
    """Report, year maps and all results of a delineation in one zip file. Returns the path of the zip."""
    import zipfile
    out_dir, _, _ = report(cfg, threshold, robust_definition, log=log)
    folder = os.path.dirname(out_dir)
    year_maps(cfg, threshold, robust_definition, log)
    paths_dir = os.path.dirname(folder)
    zip_path = os.path.join(folder, "export.zip")
    files = {"settings.txt": None}
    for name in ("populations.gpkg", "expansion_rates.csv", "cumulative_distances.csv", "manifest.json"):
        files[name] = os.path.join(folder, name)
    for path in glob.glob(os.path.join(out_dir, "*")) + glob.glob(os.path.join(folder, "years", "*.png")):
        files[os.path.relpath(path, folder)] = path
    for path in glob.glob(os.path.join(paths_dir, "sweep*.csv")):
        files[f"sweep/{os.path.basename(path)}"] = path
    files["paths/manifest.json"] = os.path.join(paths_dir, "manifest.json")
    files["presence/import_report.txt"] = cfg.path(os.path.join("presence", "import_report.txt"))
    files["project.toml"] = cfg.path("project.toml")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("settings.txt", settings_text(folder) + "\n")
        for arcname, path in files.items():
            if path:
                z.write(path, arcname)
    log(f"Export: {len(files)} files saved to '{zip_path}'.")
    return zip_path
