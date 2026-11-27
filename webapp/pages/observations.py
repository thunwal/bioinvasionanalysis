"""Page 2: import the observations (CSV, GeoPackage or iNaturalist), then compute paths and the sensitivity sweep."""
import os

import dash
import geopandas as gpd
from dash import Input, Output, State, callback, dcc, html

from bioinvasion import pipeline
from bioinvasion.sources.files import InvalidPresenceData, gpkg_layers
from webapp import figures, jobs, ui

dash.register_page(__name__, path="/observations", order=1, name="2 Observations", title="Observations")

CSV_SPEC = ("**CSV**: UTF-8 (\"CSV UTF-8\" in Excel), comma or semicolon separated. Required columns: `longitude`, "
            "`latitude` (WGS84 decimal degrees; with semicolons, decimal commas are accepted) and `year` (whole "
            "number). Optional: `location` (e.g. country; names the populations, e.g. \"France 2008\"), `source`, "
            "`source_id`. Other columns are ignored.  \n**GeoPackage**: one point layer with a defined coordinate "
            "reference system and a `year` column; optional `location`, `source`, `source_id`.  \n"
            "Files that do not meet these rules are rejected with the reason; nothing is guessed or repaired.")

layout = html.Div(id="obs-page", children=[
    html.H2("2 Observations"),
    dcc.Tabs(id="obs-tabs", value="file", children=[
        dcc.Tab(label="Upload a file", value="file", children=[
            dcc.Markdown(CSV_SPEC),
            dcc.Upload(id="obs-upload", children=html.Div(["Drop a CSV or GeoPackage here or ", html.A("choose a file")]),
                       className="upload", accept=".csv,.gpkg", max_size=jobs.MAX_UPLOAD_MB * 1_000_000),
            html.Div(id="obs-layer-box", hidden=True, children=[
                html.Label("The GeoPackage has several layers. Layer:"),
                dcc.Dropdown(id="obs-layer"),
                html.Button("Import this layer", id="obs-layer-import")]),
        ]),
        dcc.Tab(label="Download from iNaturalist", value="inat", children=[
            dcc.Markdown("Downloads all observations of a taxon within the extent of the cost surface (page 1). "
                         "iNaturalist allows about one request per second, so this can take a few minutes. "
                         f"At most {jobs.MAX_OBSERVATIONS:,} observations."),
            html.Label("Taxon (scientific name or iNaturalist taxon ID)"),
            dcc.Input(id="inat-taxon", type="text", placeholder="e.g. Megachile sculpturalis", debounce=True),
            dcc.Checklist(id="inat-options", value=["research"], options=[
                {"label": "Research grade only (identification confirmed by the community)", "value": "research"},
                {"label": "Include observations with obscured coordinates (randomised by up to ~20 km)",
                 "value": "obscured"}]),
            html.Label("Exclude observations with a positional accuracy worse than (m; empty = no limit)"),
            dcc.Input(id="inat-accuracy", type="number", min=1, placeholder="no limit"),
            html.Button("Download", id="inat-download"),
            html.Div(id="inat-progress"),
        ]),
    ]),
    html.Div(id="obs-result"),
    html.H3("Years to analyse"),
    dcc.Markdown("Empty = from the first to the last year in the data."),
    html.Div(className="row", children=[
        html.Label("From"), dcc.Input(id="obs-start", type="number", step=1, debounce=True),
        html.Label("to"), dcc.Input(id="obs-end", type="number", step=1, debounce=True),
        html.Span(id="obs-years-saved")]),
    html.H3("Compute"),
    dcc.Markdown("Removes observations outside the cost surface or on NoData cells, keeps the earliest observation "
                 "per cell, connects each observation to the nearest earlier one by a least-cost path, and runs the "
                 "sensitivity sweep (overview over all thresholds, then a high-resolution sweep over a suggested "
                 "range). This can take several minutes."),
    html.Button("Compute paths and sweep", id="obs-compute"),
    html.Div(id="obs-compute-progress"),
    html.Div(id="obs-compute-result"),
])


def show_presence(job, report=None):
    folder = jobs.job_dir(job)
    gdf = gpd.read_file(pipeline.presence_path(jobs.config(job)), layer="presence")
    if report is None:
        path = os.path.join(folder, "presence", "import_report.txt")
        report = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    return ui.flat(ui.messages([("ok", "  \n".join(report))]),
                   dcc.Graph(figure=figures.observations_map(gdf)), dcc.Graph(figure=figures.observations_per_year(gdf)))


def import_now(job, changes, log=None, progress=None):
    """Writes the data settings and imports. Returns the page content."""
    jobs.write_config(job, {"data": changes})
    try:
        cfg = jobs.config(job)
    except ValueError as e:
        return ui.error(e)
    try:
        pipeline.import_presence(cfg, log=log or ui.Log(), progress=progress, force=True)
    except (InvalidPresenceData, ValueError) as e:
        return ui.error(f"Import stopped: {e}")
    n = len(gpd.read_file(pipeline.presence_path(cfg), layer="presence", columns=["year"], ignore_geometry=True))
    if n > jobs.MAX_OBSERVATIONS:
        os.remove(pipeline.presence_path(cfg))
        return ui.error(f"{n:,} observations are more than the limit of {jobs.MAX_OBSERVATIONS:,} of this server. "
                        "Please reduce the data or run the analysis on your computer with cli.py.")
    return show_presence(job)


@callback(Output("obs-result", "children", allow_duplicate=True), Output("obs-start", "value"),
          Output("obs-end", "value"), Input("obs-page", "id"), State("job", "data"),
          prevent_initial_call="initial_duplicate")
def show_current(_, job):
    try:
        data = jobs.read_settings(job).get("data", {})
        content = show_presence(job) if os.path.exists(os.path.join(jobs.job_dir(job), "presence", "presence.gpkg")) \
            else None
    except Exception:
        return None, None, None
    return content, data.get("start_year"), data.get("end_year")


@callback(Output("obs-result", "children", allow_duplicate=True), Output("obs-layer-box", "hidden"),
          Output("obs-layer", "options"), Input("obs-upload", "contents"), State("obs-upload", "filename"),
          State("job", "data"), prevent_initial_call=True)
def upload(contents, filename, job):
    if not contents:
        return dash.no_update, dash.no_update, dash.no_update
    try:
        rel = ui.save_upload(job, contents, filename, "upload")
    except ValueError as e:
        return ui.error(e), True, []
    if rel.lower().endswith(".gpkg"):
        layers = gpkg_layers(os.path.join(jobs.job_dir(job), rel))
        if len(layers) > 1:
            jobs.write_config(job, {"data": {"source": "gpkg", "file": rel, "layer": None}})
            return None, False, layers
        return import_now(job, {"source": "gpkg", "file": rel, "layer": None, "taxon": None}), True, []
    return import_now(job, {"source": "csv", "file": rel, "layer": None, "taxon": None}), True, []


@callback(Output("obs-result", "children", allow_duplicate=True), Input("obs-layer-import", "n_clicks"),
          State("obs-layer", "value"), State("job", "data"), prevent_initial_call=True)
def import_layer(_, layer, job):
    if not layer:
        return ui.error("Please choose a layer.")
    return import_now(job, {"layer": layer})


@callback(Output("obs-result", "children", allow_duplicate=True), Input("inat-download", "n_clicks"),
          State("inat-taxon", "value"), State("inat-options", "value"), State("inat-accuracy", "value"),
          State("job", "data"), background=True, progress=[Output("inat-progress", "children")],
          running=[(Output("inat-download", "disabled"), True, False)], prevent_initial_call=True)
def download(set_progress, _, taxon, options, accuracy, job):
    if not taxon:
        return ui.error("Please enter a taxon.")
    if not jobs.read_settings(job).get("cost", {}).get("file"):
        return ui.error("Please choose the cost surface first (page 1): it defines the area to download.")
    set_progress("Connecting to iNaturalist...")
    return import_now(job, {"source": "inaturalist", "taxon": str(taxon).strip(), "file": None, "layer": None,
                            "research_grade_only": "research" in options, "include_obscured": "obscured" in options,
                            "max_positional_accuracy_m": float(accuracy) if accuracy else None},
                      progress=lambda done, total: set_progress(f"{done:,} of {total:,} observations downloaded..."))


@callback(Output("obs-years-saved", "children"), Input("obs-start", "value"), Input("obs-end", "value"),
          State("job", "data"), prevent_initial_call=True)
def years(start, end, job):
    jobs.write_config(job, {"data": {"start_year": int(start) if start else None,
                                     "end_year": int(end) if end else None}})
    return "Saved." if start or end else ""


@callback(Output("obs-compute-result", "children"), Input("obs-compute", "n_clicks"), State("job", "data"),
          background=True, progress=[Output("obs-compute-progress", "children")],
          running=[(Output("obs-compute", "disabled"), True, False)], prevent_initial_call=True)
def compute(set_progress, _, job):
    log = ui.Log()
    try:
        cfg = jobs.config(job)
        if not os.path.exists(pipeline.presence_path(cfg)):
            return ui.error("Please import observations first.")
        with jobs.running(job):
            set_progress("Least-cost paths: starting...")
            pipeline.compute_paths(cfg, log=log, progress=lambda i, n: set_progress(
                html.Progress(value=str(i), max=str(n), title=f"Least-cost paths: year {i} of {n}")))
            def sweep_progress(i, n):
                if i % 5 == 0 or i == n:
                    set_progress([html.Span(f"Sensitivity sweep: {i} of {n} thresholds "),
                                  html.Progress(value=str(i), max=str(n))])

            coarse, fine, chosen = pipeline.sweep(cfg, log=log, progress=sweep_progress)
    except jobs.Busy as e:
        return ui.error(e)
    except Exception as e:
        return ui.flat(ui.error(f"Computation stopped: {e}"), ui.log_box(log))
    set_progress(None)
    return ui.flat(ui.messages([("ok", "Least-cost paths and sensitivity sweep are ready."), ("info", chosen["rule"])]),
                   ui.log_box(log), dcc.Link("Next: 3 Thresholds →", href="/thresholds", className="next"))
