"""
Web app of bioinvasionanalysis (Dash, multi-page). Start locally with: python -m webapp
Each page is one module in webapp/pages with its layout and callbacks; all computations go through
bioinvasion.pipeline, the same code as cli.py.
"""
import os

import dash
import diskcache
from dash import Dash, DiskcacheManager, Input, Output, State, dcc, html

from webapp import jobs

os.makedirs(jobs.JOBS_DIR, exist_ok=True)
cache = diskcache.Cache(os.path.join(jobs.JOBS_DIR, "_callback_cache"))

app = Dash(__name__, use_pages=True, background_callback_manager=DiskcacheManager(cache),
           suppress_callback_exceptions=True, title="Bioinvasion analysis")
server = app.server  # for gunicorn: gunicorn webapp.app:server

app.layout = html.Div([
    dcc.Location(id="url"),
    dcc.Store(id="job", storage_type="session"),
    html.Header([
        html.H1("Bioinvasion analysis"),
        html.P(["Expansion dynamics of non-native species with sequential least-cost modelling, following ",
                html.A("Rohrbach et al. (2025)", href="https://doi.org/10.1007/s10980-025-02188-9", target="_blank"),
                ". Results of a session are kept for 24 hours."]),
        html.Nav([dcc.Link(page["name"], href=page["relative_path"], className="nav-link")
                  for page in dash.page_registry.values()]),
    ]),
    html.Main(dash.page_container),
])


@dash.callback(Output("job", "data"), Input("url", "pathname"), State("job", "data"))
def ensure_job(_, job):
    """Every browser session (tab) gets its own job folder."""
    if job and jobs.exists(job):
        return dash.no_update
    return jobs.new_job()
