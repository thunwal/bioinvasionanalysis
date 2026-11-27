"""
Project settings. A project is a folder with a 'project.toml' file; all outputs are written into that folder.
'python cli.py init <folder>' writes a commented template (PROJECT_TEMPLATE below).

Settings are read strictly: unknown sections or keys are an error, so that a typo cannot silently fall back to a
default. Optional values that are not set are decided automatically; the decision is logged and stored in the
manifest of the stage that made it.
"""
import os
import tomllib
from dataclasses import dataclass, field, fields, asdict


@dataclass
class DataConfig:
    source: str = "csv"                     # "csv", "gpkg" or "inaturalist"
    file: str = ""                          # csv/gpkg: path, relative to the project folder
    layer: str = ""                         # gpkg: layer name, required if the file has several layers
    taxon: str = ""                         # inaturalist: scientific name or taxon ID
    research_grade_only: bool = True        # inaturalist
    include_obscured: bool = False          # inaturalist
    max_positional_accuracy_m: float | None = None  # inaturalist; not set = no limit
    start_year: int | None = None           # not set = earliest year in the data
    end_year: int | None = None             # not set = latest year in the data


@dataclass
class CostConfig:
    file: str = ""                          # GeoTIFF, relative to the project folder
    label: str = ""                         # short name used in output folder names; not set = file name


@dataclass
class SensitivityConfig:
    robust_from: float = 5                  # robust population definitions tested (paper: 5 to 15 by 1)
    robust_to: float = 15
    robust_step: float = 1
    coarse_steps: int = 200                 # overview: 0 to the highest accumulated cost in about this many steps
    fine_steps: int = 1000                  # high resolution: about this many steps in the suggested range
    stable_tolerance: float = 0.25          # stable range: average rate stays within +/- this share
    max_quantile: float = 0.995             # thresholds above this quantile of path costs are ignored as extremes
    n_ranges: int = 3                       # number of widest stable ranges the suggested range covers
    margin: float = 0.1                     # the suggested range is widened by this share of its width on each side
    fine_from: float | None = None          # set all three to override the suggested high-resolution range
    fine_to: float | None = None
    fine_step: float | None = None


@dataclass
class DelineationConfig:
    threshold: float | None = None          # accumulated cost threshold (absolute value); paths at or above it are removed
    robust_definition: float = 10           # robust population: median observations per year above this value


@dataclass
class ReportConfig:
    formats: list = field(default_factory=lambda: ["png"])
    dpi: int = 300
    split_at: float | None = None           # split the x axis of the sensitivity plot at this threshold (paper: 10)
    breakpoints: dict = field(default_factory=dict)  # population name -> [start, end] of the expansion phase


@dataclass
class YearMapsConfig:
    dpi: int = 150
    width_cm: float = 16


@dataclass
class Config:
    project_dir: str
    data: DataConfig
    cost: CostConfig
    sensitivity: SensitivityConfig
    delineation: DelineationConfig
    report: ReportConfig
    year_maps: YearMapsConfig

    def path(self, relative):
        """Path relative to the project folder (absolute paths are kept)."""
        return relative if os.path.isabs(relative) else os.path.join(self.project_dir, relative)

    @property
    def cost_label(self):
        return self.cost.label or os.path.splitext(os.path.basename(self.cost.file))[0]

    def robust_definitions(self):
        s = self.sensitivity
        n = int(round((s.robust_to - s.robust_from) / s.robust_step)) + 1
        return [round(s.robust_from + i * s.robust_step, 10) for i in range(n)]

    def as_dict(self):
        d = asdict(self)
        d.pop("project_dir")
        return d


SECTIONS = {"data": DataConfig, "cost": CostConfig, "sensitivity": SensitivityConfig, "delineation": DelineationConfig,
            "report": ReportConfig, "year_maps": YearMapsConfig}


def load_config(project_dir):
    """Reads <project_dir>/project.toml."""
    path = os.path.join(project_dir, "project.toml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"'{path}' not found. Create one with: python cli.py init {project_dir}")
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    unknown = set(raw) - set(SECTIONS)
    if unknown:
        raise ValueError(f"Unknown section(s) in '{path}': {', '.join(sorted(unknown))}. "
                         f"Valid sections: {', '.join(SECTIONS)}.")
    sections = {}
    for name, cls in SECTIONS.items():
        values = raw.get(name, {})
        valid = {f.name for f in fields(cls)}
        bad = set(values) - valid
        if bad:
            raise ValueError(f"Unknown key(s) in section [{name}] of '{path}': {', '.join(sorted(bad))}. "
                             f"Valid keys: {', '.join(sorted(valid))}.")
        sections[name] = cls(**values)
    cfg = Config(project_dir=os.path.abspath(project_dir), **sections)
    _check(cfg, path)
    return cfg


def _check(cfg, path):
    d = cfg.data
    if d.source not in ("csv", "gpkg", "inaturalist"):
        raise ValueError(f"[data] source must be \"csv\", \"gpkg\" or \"inaturalist\" in '{path}', not '{d.source}'.")
    if d.source in ("csv", "gpkg") and not d.file:
        raise ValueError(f"[data] file must be set for source \"{d.source}\" in '{path}'.")
    if d.source == "inaturalist" and not d.taxon:
        raise ValueError(f"[data] taxon must be set for source \"inaturalist\" in '{path}'.")
    if not cfg.cost.file:
        raise ValueError(f"[cost] file must be set in '{path}'.")
    s = cfg.sensitivity
    fine = [s.fine_from, s.fine_to, s.fine_step]
    if any(v is not None for v in fine) and not all(v is not None for v in fine):
        raise ValueError(f"[sensitivity] fine_from, fine_to and fine_step must be set together (or none) in '{path}'.")


PROJECT_TEMPLATE = '''# Project settings for bioinvasionanalysis. Paths are relative to this folder.
# Keys that are commented out are decided automatically; the decision is logged and stored in manifest.json.

[data]
# Where the observations come from: "csv", "gpkg" or "inaturalist".
# CSV: UTF-8, comma or semicolon separated, columns longitude, latitude (WGS84 decimal degrees) and year (integer);
#      optional columns location, source, source_id. Other columns are ignored.
# GPKG: one point layer with a defined CRS and a column year (integer); optional location, source, source_id.
source = "csv"
file = "observations.csv"
# layer = ""                         # gpkg: layer name, required if the file has several layers
# taxon = "Megachile sculpturalis"   # inaturalist: scientific name or taxon ID
# research_grade_only = true         # inaturalist
# include_obscured = false           # inaturalist: coordinates randomised by up to ~20 km
# max_positional_accuracy_m = 10000  # inaturalist: not set = no limit
# start_year = 2008                  # not set = earliest year in the data
# end_year = 2024                    # not set = latest year in the data

[cost]
file = "cost_surface.tif"   # GeoTIFF in a projected CRS with square cells; NoData cells cannot be crossed
# label = "sdm10km"         # short name for output folders; not set = file name

[sensitivity]
robust_from = 5             # robust population definitions tested, as in the paper
robust_to = 15
robust_step = 1
coarse_steps = 200          # overview: 0 to the highest accumulated cost in about this many steps
fine_steps = 1000           # high resolution: about this many steps in the suggested range
stable_tolerance = 0.25     # stable range: average expansion rate stays within +/- 25 %
max_quantile = 0.995        # ignore thresholds above this quantile of path costs (extreme paths)
n_ranges = 3                # suggested range covers the 3 widest stable ranges ...
margin = 0.1                # ... widened by 10 % of its width on each side
# fine_from = 3             # set all three to choose the high-resolution range yourself
# fine_to = 15
# fine_step = 0.01

[delineation]
# threshold = 4.4           # accumulated cost threshold; choose it after looking at the sensitivity test
robust_definition = 10      # robust population: more than 10 median observations per year

[report]
formats = ["png"]           # e.g. ["png", "pdf", "tiff"]
dpi = 300
# split_at = 10             # split the x axis of the sensitivity plot here, to compress a long tail
# breakpoints = { "France 2008" = [2011, 2021] }   # expansion phases for the phase table

[year_maps]
dpi = 150
width_cm = 16
'''
