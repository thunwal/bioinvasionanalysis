"""
Creates figures and tables of a completed run, as in the results section of the paper.
Defaults are taken from params.py; all settings can be overridden on the command line (see --help).

Example:
    python report.py
    python report.py --run myrun_q95 --compare-run myrun_q90 --breakpoints "France 2008=2011-2021"
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")  # no display needed

import params  # noqa: E402
from src.report import report  # noqa: E402


def parse_breakpoints(values):
    """'Population name=2011-2021' -> {'Population name': (2011, 2021)}"""
    result = {}
    for v in values or []:
        name, _, years = v.rpartition("=")
        start, _, end = years.partition("-")
        if not name or not start or not end:
            raise argparse.ArgumentTypeError(f"Invalid breakpoints '{v}', expected e.g. 'France 2008=2011-2021'.")
        result[name.strip()] = (int(start), int(end))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workdir", default=params.workdir_path, help="directory with the run outputs (default: params.workdir_path)")
    p.add_argument("--run", default=params.run, help="run name (default: params.run)")
    p.add_argument("--cost-name", default=params.cost_name, help="cost surface file, defines the map extent (default: params.cost_name)")
    p.add_argument("--year-field", default=None, help="year field of the observations (default: params.year_field)")
    p.add_argument("--robust-definition", type=float, default=getattr(params, "robust_definition", 10),
                   help="populations with median observations per year above this value are robust (default: 10)")
    p.add_argument("--threshold", type=float, default=getattr(params, "threshold", None),
                   help="accumulated cost threshold used for the run (default: params.threshold)")
    p.add_argument("--threshold-is-absolute", action=argparse.BooleanOptionalAction,
                   default=getattr(params, "threshold_is_absolute", False),
                   help="threshold is an accumulated cost value instead of a quantile (default: params.threshold_is_absolute)")
    p.add_argument("--compare-run", default=None,
                   help="second run with a different threshold, shown as additional population map (Fig. 5b of the paper)")
    p.add_argument("--compare-label", default=None, help="title of the comparison map, e.g. 'accumulated cost threshold = 3.3'")
    p.add_argument("--split-at", type=float, default=None,
                   help="split the x axis of the sensitivity plot at this threshold, to compress a long tail (paper: 10)")
    p.add_argument("--breakpoints", action="append", metavar="'NAME=FROM-TO'",
                   help="expansion phase of a population, e.g. 'France 2008=2011-2021'; repeat for several populations")
    p.add_argument("--formats", nargs="+", default=["png"], help="output formats, e.g. png pdf svg tiff (default: png)")
    p.add_argument("--dpi", type=int, default=300)
    p.add_argument("--out-dir", default=None, help="output directory (default: <workdir>/<run>_report)")
    a = p.parse_args()

    year_field = a.year_field
    if year_field is None:
        year_field = "year" if getattr(params, "presence_source", "file") == "inaturalist" else params.year_field

    report(
        workdir=a.workdir,
        run=a.run,
        cost_name=a.cost_name,
        out_dir=a.out_dir or os.path.join(a.workdir, f"{a.run}_report"),
        year_field=year_field,
        robust_definition=a.robust_definition,
        threshold=a.threshold,
        threshold_is_absolute=a.threshold_is_absolute,
        compare_run=a.compare_run,
        compare_label=a.compare_label,
        split_at=a.split_at,
        breakpoints=parse_breakpoints(a.breakpoints),
        formats=a.formats,
        dpi=a.dpi,
    )


if __name__ == "__main__":
    main()
