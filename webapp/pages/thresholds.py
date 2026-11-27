"""
Page 3: the scientist chooses the accumulated cost threshold. Shows the overview sweep with the suggested
high-resolution range (and the rule behind it), the high-resolution sweep with stable ranges, and the populations
for the chosen threshold with plain-language checks.
"""
import os

import dash
import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html

from bioinvasion import pipeline
from bioinvasion.report import insights
from bioinvasion.report.figures import population_table
from webapp import figures, jobs, ui

dash.register_page(__name__, path="/thresholds", order=2, name="3 Thresholds", title="Thresholds")

layout = html.Div(id="thr-page", children=[
    html.H2("3 Thresholds"),
    dcc.Markdown("Paths with an accumulated cost at or above the **threshold** are removed; the remaining paths form "
                 "the populations. Low thresholds split populations artificially, very high thresholds merge separate "
                 "introductions. A good threshold lies where the result hardly depends on the exact value "
                 "(**stable range**, green), typically at its beginning. You decide; the suggestions only help."),
    html.Div(id="thr-missing"),
    html.H3("Overview: all thresholds"),
    html.Div(id="thr-rule"),
    dcc.Graph(id="thr-coarse"),
    html.H3("High resolution"),
    html.Div(className="row", children=[
        html.Label("From"), dcc.Input(id="thr-from", type="number"),
        html.Label("to"), dcc.Input(id="thr-to", type="number"),
        html.Label("step"), dcc.Input(id="thr-step", type="number"),
        html.Button("Run high-resolution sweep", id="thr-rerun")]),
    html.Div(id="thr-rerun-progress"),
    dcc.Graph(id="thr-fine"),
    html.Div(id="thr-ranges"),
    html.H3("Populations"),
    dcc.Markdown("Click on a sweep curve to take over its threshold, or type it in."),
    html.Div(className="row", children=[
        html.Label("Threshold"), dcc.Input(id="thr-threshold", type="number", debounce=True),
        html.Label("Robust population: median observations per year above"),
        dcc.Input(id="thr-robust", type="number", value=10, min=0, debounce=True),
        html.Button("Show populations", id="thr-apply")]),
    dcc.Loading(html.Div(id="thr-result")),
    dcc.Store(id="thr-refresh"),
])


def load(job):
    cfg = jobs.config(job)
    folder = pipeline.current_paths_folder(cfg)
    coarse_csv = os.path.join(folder, "sweep_coarse.csv")
    if not os.path.exists(coarse_csv):
        raise FileNotFoundError("No sensitivity sweep yet: import observations and click 'Compute' on page 2.")
    fine, chosen = pipeline.latest_fine_sweep(folder)
    return cfg, folder, pd.read_csv(coarse_csv), fine, chosen


def range_list(fine, definition, cfg):
    d = insights.nearest_definition(fine, definition)
    ranges = insights.stable_ranges(fine, d, cfg.sweep.stable_tolerance, cfg.sweep.max_quantile, cfg.sweep.n_ranges)
    text = (f"Stable ranges in the high-resolution sweep (robust definition {d:g}; average rate within "
            f"±{cfg.sweep.stable_tolerance:.0%}; widest first):  \n" +
            "  \n".join(f"- {insights.fmt(r['from'])}–{insights.fmt(r['to'])} (Q{r['q_from']:.3f}–Q{r['q_to']:.3f}): "
                        f"{r['rate_min']:.1f}–{r['rate_max']:.1f} km/year" for r in ranges)) if ranges else \
        "No stable range found in the high-resolution sweep."
    return ranges, ui.messages([("tip", text)])


@callback(Output("thr-missing", "children"), Output("thr-rule", "children"), Output("thr-coarse", "figure"),
          Output("thr-fine", "figure"), Output("thr-ranges", "children"), Output("thr-from", "value"),
          Output("thr-to", "value"), Output("thr-step", "value"), Output("thr-threshold", "value"),
          Output("thr-robust", "value"),
          Input("thr-page", "id"), Input("thr-refresh", "data"), State("job", "data"))
def show_sweeps(_, __, job):
    try:
        cfg, folder, coarse, fine, chosen = load(job)
    except Exception as e:
        return (ui.error(e),) + (dash.no_update,) * 9
    robust = cfg.delineation.robust_definition
    ranges, ranges_box = range_list(fine, robust, cfg)
    threshold = cfg.delineation.threshold
    if threshold is None and ranges:
        threshold = ranges[0]["from"]
    return (None, ui.messages([("info", chosen["rule"])]),
            figures.sweep_figure(coarse, threshold, shade=(chosen["from"], chosen["to"])),
            figures.sweep_figure(fine, threshold, ranges=ranges), ranges_box,
            chosen["from"], chosen["to"], chosen["step"], threshold, robust)


@callback(Output("thr-refresh", "data"), Input("thr-rerun", "n_clicks"), State("thr-from", "value"),
          State("thr-to", "value"), State("thr-step", "value"), State("job", "data"), background=True,
          progress=[Output("thr-rerun-progress", "children")],
          running=[(Output("thr-rerun", "disabled"), True, False)], prevent_initial_call=True)
def rerun(set_progress, n, start, end, step, job):
    if None in (start, end, step) or step <= 0 or end <= start:
        set_progress(ui.error("Please give from < to and a positive step."))
        return dash.no_update
    if (end - start) / step > 5000:
        set_progress(ui.error("More than 5000 steps: please choose a larger step."))
        return dash.no_update
    try:
        with jobs.running(job):
            pipeline.sweep(jobs.config(job), start, end, step, log=ui.Log(), progress=lambda i, total: set_progress(
                [html.Span(f"{i} of {total} thresholds "), html.Progress(value=str(i), max=str(total))]))
    except Exception as e:
        set_progress(ui.error(e))
        return dash.no_update
    set_progress(None)
    return n


@callback(Output("thr-threshold", "value", allow_duplicate=True), Input("thr-fine", "clickData"),
          Input("thr-coarse", "clickData"), prevent_initial_call=True)
def take_threshold(fine_click, coarse_click):
    click = fine_click if dash.ctx.triggered_id == "thr-fine" else coarse_click
    return round(click["points"][0]["x"], 10) if click else dash.no_update


@callback(Output("thr-result", "children"), Output("thr-fine", "figure", allow_duplicate=True),
          Output("thr-coarse", "figure", allow_duplicate=True),
          Input("thr-apply", "n_clicks"), State("thr-threshold", "value"), State("thr-robust", "value"),
          State("job", "data"), prevent_initial_call=True)
def apply(_, threshold, robust, job):
    if threshold is None or robust is None:
        return ui.error("Please set a threshold and a robust population definition."), dash.no_update, dash.no_update
    try:
        cfg, folder, coarse, fine, chosen = load(job)
        log = ui.Log()
        delin = pipeline.delineate(cfg, float(threshold), float(robust), log=log)
        data = pipeline.load_delineation(delin)
    except Exception as e:
        return ui.error(e), dash.no_update, dash.no_update
    jobs.write_config(job, {"delineation": {"threshold": float(threshold), "robust_definition": float(robust)}})
    checks = insights.delineation_checks(data) + insights.sweep_checks(fine, float(threshold), float(robust))
    table = population_table(data["rates"])
    ranges, _ = range_list(fine, float(robust), cfg)
    return (ui.flat(html.P(f"Threshold {threshold:g} (Q{data['threshold_quantile']:.3f}): "
                    f"{len(data['paths_grouped'])} of {len(data['paths'])} paths kept."),
             *ui.messages(checks),
             dcc.Graph(figure=figures.populations_map(data)),
             dash_table.DataTable(data=table.to_dict("records"), columns=[{"name": c, "id": c} for c in table.columns],
                                  sort_action="native", page_size=15, style_table={"overflowX": "auto"},
                                  style_cell={"fontSize": 13, "padding": "3px 8px"}),
             dcc.Link("Next: 4 Export →", href="/export", className="next")),
            figures.sweep_figure(fine, float(threshold), ranges=ranges),
            figures.sweep_figure(coarse, float(threshold), shade=(chosen["from"], chosen["to"])))
