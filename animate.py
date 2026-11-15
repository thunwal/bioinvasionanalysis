import os
import params
from src.animation import animate

run = params.run
workdir_path = params.workdir_path

if __name__ == "__main__":
    animate(
        in_gpkg=os.path.join(workdir_path, f"{run}.gpkg"),
        in_paths=f"{run}_paths_grouped",
        in_points=f"{run}_points_grouped",
        in_rates_csv=os.path.join(workdir_path, f"{run}_expansion_rates.csv"),
        out_file=os.path.join(workdir_path, params.animation_file),
        year_field="year" if getattr(params, "presence_source", "file") == "inaturalist" else params.year_field,
        robust_definition=params.robust_definition,
        basemap=params.basemap,
        basemap_zoom=params.basemap_zoom,
        relief_strength=params.relief_strength,
        water_colour=params.water_colour,
        border_colour=params.border_colour,
        map_crs=params.map_crs,
        max_path_length_km=params.max_path_length_km,
        title=params.animation_title,
        fps=params.fps,
        seconds_per_year=params.seconds_per_year,
        hold_start=params.hold_start,
        hold_end=params.hold_end,
        grow_window=params.grow_window,
        duration_exponent=params.duration_exponent,
        width_px=params.width_px,
        height_px=params.height_px,
        preview_year=params.preview_year,
    )
