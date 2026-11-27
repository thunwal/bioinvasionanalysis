"""Page 1: choose a demo cost surface or upload a GeoTIFF."""
import os

import dash
import numpy as np
import rasterio as rio
from dash import Input, Output, State, callback, dcc, html

from bioinvasion.pipeline import check_cost_surface
from bioinvasion.sources.inaturalist import raster_bbox_4326
from webapp import jobs, ui

dash.register_page(__name__, path="/", order=0, name="1 Cost surface", title="Cost surface")

layout = html.Div(id="cost-page", children=[
    html.H2("1 Cost surface"),
    dcc.Markdown("The cost surface describes how difficult it is for the species to move through the landscape: "
                 "the value of a cell is the cost of crossing it. **NoData cells** (e.g. sea) cannot be crossed. "
                 "Requirements: GeoTIFF, projected coordinate reference system (metres), square cells, "
                 f"at most {jobs.MAX_CELLS:,} cells."),
    dcc.RadioItems(id="cost-choice", options=[{"label": label, "value": key}
                                              for key, (label, _) in jobs.DEMO_SURFACES.items()]
                   + [{"label": "Upload my own GeoTIFF", "value": "upload"}]),
    html.Div(id="cost-upload-box", hidden=True, children=dcc.Upload(
        id="cost-upload", children=html.Div(["Drop a GeoTIFF here or ", html.A("choose a file")]),
        className="upload", accept=".tif,.tiff", max_size=jobs.MAX_UPLOAD_MB * 1_000_000)),
    html.Div(id="cost-result"),
    dcc.Link("Next: 2 Observations →", href="/observations", className="next"),
])


def describe(path):
    with rio.open(path) as r:
        check_cost_surface(r)
        cells = r.width * r.height
        if cells > jobs.MAX_CELLS:
            raise ValueError(f"The cost surface has {cells:,} cells, more than the limit of {jobs.MAX_CELLS:,} of "
                             f"this server. Please use a coarser resolution or a smaller extent, or run the analysis "
                             f"on your computer with cli.py.")
        values = r.read(1, masked=True)
        bbox = raster_bbox_4326(r)
        items = [("ok", f"**{os.path.basename(path)}**: {r.width} × {r.height} cells of {r.res[0]:g} m, "
                        f"{r.crs.to_string()}"),
                 ("info", f"Extent (lon/lat): {bbox[0]:.2f}, {bbox[1]:.2f} to {bbox[2]:.2f}, {bbox[3]:.2f}. "
                          f"Values: {float(values.min()):.4g} to {float(values.max()):.4g}; "
                          f"NoData cells: {int(np.ma.count_masked(values)):,}")]
        if r.nodata is None:
            items.append(("warn", "The raster has no NoData value, so every cell can be crossed."))
    return items


@callback(Output("cost-choice", "value"), Output("cost-result", "children", allow_duplicate=True),
          Input("cost-page", "id"), State("job", "data"), prevent_initial_call="initial_duplicate")
def show_current(_, job):
    try:
        cost = jobs.read_settings(job).get("cost", {})
    except ValueError:
        return dash.no_update, None
    if not cost.get("file"):
        return None, None
    choice = cost.get("label") if cost.get("label") in jobs.DEMO_SURFACES else "upload"
    try:
        return choice, ui.messages(describe(os.path.join(jobs.job_dir(job), cost["file"])))
    except Exception as e:
        return choice, ui.error(e)


@callback(Output("cost-upload-box", "hidden"), Output("cost-result", "children", allow_duplicate=True),
          Input("cost-choice", "value"), State("job", "data"), prevent_initial_call=True)
def choose(choice, job):
    if choice != "upload" and choice in jobs.DEMO_SURFACES:
        path = jobs.DEMO_SURFACES[choice][1]
        jobs.write_config(job, {"cost": {"file": path, "label": choice}})
        return True, ui.messages(describe(path))
    return False, dash.no_update


@callback(Output("cost-result", "children", allow_duplicate=True), Input("cost-upload", "contents"),
          State("cost-upload", "filename"), State("job", "data"), prevent_initial_call=True)
def upload(contents, filename, job):
    if not contents:
        return dash.no_update
    try:
        rel = ui.save_upload(job, contents, filename, "cost")
        items = describe(os.path.join(jobs.job_dir(job), rel))
    except Exception as e:
        return ui.error(f"The cost surface cannot be used: {e}")
    jobs.write_config(job, {"cost": {"file": rel, "label": os.path.splitext(jobs.safe_name(filename))[0][:30]}})
    return ui.messages(items)
