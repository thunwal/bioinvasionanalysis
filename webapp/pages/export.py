"""Page 4: download the results of the chosen threshold as one zip file."""
import dash
from dash import Input, Output, State, callback, dcc, html

from bioinvasion import pipeline
from webapp import jobs, ui

dash.register_page(__name__, path="/export", order=3, name="4 Export", title="Export")

layout = html.Div(id="exp-page", children=[
    html.H2("4 Export"),
    html.Div(id="exp-current"),
    dcc.Markdown("The zip file contains: populations and paths (GeoPackage), expansion rates and cumulative distances "
                 "(CSV), the sensitivity sweeps (CSV), the figures and tables of the paper, one map per year end "
                 "(PNG, without title or source credits), `settings.txt` with all settings and numbers in words "
                 "(for the methods section), the import report, the manifests, and `project.toml`, with which the "
                 "analysis can be repeated on your computer (`python cli.py export <folder>`)."),
    html.Button("Create zip file", id="exp-build"),
    html.Div(id="exp-progress"),
    html.Div(id="exp-result"),
    dcc.Download(id="exp-download"),
])


@callback(Output("exp-current", "children"), Input("exp-page", "id"), State("job", "data"))
def current(_, job):
    try:
        d = jobs.read_settings(job).get("delineation", {})
    except ValueError as e:
        return ui.error(e)
    if "threshold" not in d:
        return ui.error("Please choose a threshold first (page 3, 'Show populations').")
    return ui.messages([("info", f"Threshold **{d['threshold']:g}**, robust population: median observations per "
                                 f"year above **{d.get('robust_definition', 10):g}**.")])


@callback(Output("exp-download", "data"), Output("exp-result", "children"), Input("exp-build", "n_clicks"),
          State("job", "data"), background=True, progress=[Output("exp-progress", "children")],
          running=[(Output("exp-build", "disabled"), True, False)], prevent_initial_call=True)
def build(set_progress, _, job):
    set_progress("Creating figures, tables and year maps...")
    log = ui.Log()
    try:
        zip_path = pipeline.export(jobs.config(job), log=log)
    except Exception as e:
        set_progress(None)
        return dash.no_update, ui.flat(ui.error(e), ui.log_box(log))
    set_progress(None)
    return dcc.send_file(zip_path, filename="bioinvasion_results.zip"), ui.log_box(log)
