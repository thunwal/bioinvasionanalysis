"""Interactive Plotly figures of the web app (the static figures of the paper are in bioinvasion/report/figures.py)."""
import numpy as np
import plotly.graph_objects as go
from matplotlib.colors import to_hex

from bioinvasion.report.figures import GREY, robust_palette

MAP_STYLE = "carto-positron"


def _zoom(bounds):
    """Rough map zoom level for lon/lat bounds (xmin, ymin, xmax, ymax)."""
    span = max(bounds[2] - bounds[0], (bounds[3] - bounds[1]) * 1.6, 0.01)
    return float(np.clip(np.log2(360 / span) - 0.3, 0, 14))


def _map_layout(fig, gdf_4326, height=520):
    b = gdf_4326.total_bounds
    fig.update_layout(map=dict(style=MAP_STYLE, center=dict(lon=(b[0] + b[2]) / 2, lat=(b[1] + b[3]) / 2),
                               zoom=_zoom(b)),
                      margin=dict(l=0, r=0, t=0, b=0), height=height,
                      legend=dict(bgcolor="rgba(255,255,255,0.8)", x=0.01, y=0.99))
    return fig


def observations_map(points):
    """Observations coloured by year."""
    p = points.to_crs(4326)
    fig = go.Figure(go.Scattermap(lon=p.geometry.x, lat=p.geometry.y, mode="markers",
                                  marker=dict(size=5, color=p["year"], colorscale="Viridis",
                                              colorbar=dict(title="Year")),
                                  text=p["year"].astype(str) + " " + p["location"].astype(str),
                                  hoverinfo="text"))
    return _map_layout(fig, p)


def observations_per_year(points):
    counts = points["year"].value_counts().sort_index()
    fig = go.Figure(go.Bar(x=counts.index, y=counts.values, marker_color="#555"))
    fig.update_layout(height=220, margin=dict(l=40, r=10, t=10, b=30), xaxis_title=None,
                      yaxis_title="Observations", template="simple_white")
    return fig


def sweep_figure(sweep, threshold=None, shade=None, ranges=(), title=""):
    """
    Average expansion rate of robust populations against the threshold, one line per robust definition.
    'shade' = (from, to) of the suggested high-resolution range; 'ranges' = stable ranges (dicts with from/to).
    """
    fig = go.Figure()
    definitions = sorted(sweep["definition_robust"].unique())
    for i, d in enumerate(definitions):
        s = sweep[sweep["definition_robust"] == d].sort_values("threshold")
        colour = f"hsl({int(250 * i / max(len(definitions) - 1, 1))},70%,45%)"
        fig.add_trace(go.Scatter(x=s["threshold"], y=s["avg_rate"] / 1000, mode="lines", name=f"> {d:g}",
                                 line=dict(width=1.2, color=colour, shape="hv"),
                                 customdata=np.column_stack([s["quantile"], s["num_groups"], s["num_groups_robust"]]),
                                 hovertemplate="threshold %{x:.4g} (Q%{customdata[0]:.3f})<br>%{y:.1f} km/year<br>"
                                               "%{customdata[2]} robust of %{customdata[1]} populations"))
    if shade:
        fig.add_vrect(x0=shade[0], x1=shade[1], fillcolor="#1565c0", opacity=0.08, line_width=0,
                      annotation_text="high-resolution range", annotation_position="top left")
    for r in ranges:
        fig.add_vrect(x0=r["from"], x1=r["to"], fillcolor="#2e7d32", opacity=0.12, line_width=0)
    if threshold is not None:
        fig.add_vline(x=threshold, line_dash="dash", line_color="black", line_width=1)
    fig.update_layout(height=360, margin=dict(l=50, r=10, t=30 if title else 10, b=40), template="simple_white",
                      title=title, xaxis_title="Accumulated cost threshold",
                      yaxis_title="Average expansion rate of robust populations (km/year)",
                      legend=dict(title="Robust: median obs./year"), hovermode="closest")
    return fig


def _lines(gdf):
    lon, lat = [], []
    for geom in gdf.geometry:
        for part in getattr(geom, "geoms", [geom]):
            x, y = part.xy
            lon += list(x) + [None]
            lat += list(y) + [None]
    return lon, lat


def populations_map(data):
    """Robust populations coloured, sparse populations and isolated observations grey."""
    paths = data["paths_grouped"].to_crs(4326)
    points = data["points"].to_crs(4326)
    rates = data["rates"]
    robust = rates[rates["robust"]].sort_values("group_name")
    colours = dict(zip(robust["group_id"], [to_hex(c) for c in robust_palette(len(robust))]))
    fig = go.Figure()
    sparse = paths[~paths["group_id"].isin(colours)]
    lon, lat = _lines(sparse)
    fig.add_trace(go.Scattermap(lon=lon, lat=lat, mode="lines", line=dict(color=GREY, width=1.5),
                                name="Sparse populations", hoverinfo="skip"))
    iso = points[points["group_id"].isna()]
    fig.add_trace(go.Scattermap(lon=iso.geometry.x, lat=iso.geometry.y, mode="markers", name="Isolated observations",
                                marker=dict(size=5, color=GREY), text=iso["year"].astype(str), hoverinfo="text"))
    for gid, name in zip(robust["group_id"], robust["group_name"]):
        r = rates[rates["group_id"] == gid].iloc[0]
        lon, lat = _lines(paths[paths["group_id"] == gid])
        fig.add_trace(go.Scattermap(lon=lon, lat=lat, mode="lines", line=dict(color=colours[gid], width=2.5),
                                    name=f"{name}: {r['expansion_rate_km']:.1f} km/year",
                                    hovertext=name, hoverinfo="text"))
    return _map_layout(fig, points, height=560)
