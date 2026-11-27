"""
Command line interface of bioinvasionanalysis. Each command works on a project folder containing a project.toml
(create one with 'init'); results are written into that folder. Every command first brings the stages it depends on
up to date and skips stages whose inputs and settings have not changed.

    python cli.py init      <project>                      write a commented project.toml template
    python cli.py import    <project>                      read the observations (CSV, GPKG or iNaturalist)
    python cli.py paths     <project>                      thin the observations, calculate least-cost paths
    python cli.py sweep     <project> [--from --to --step] sensitivity sweep: overview + high resolution
    python cli.py delineate <project> [--threshold --robust]   populations and expansion rates
    python cli.py report    <project> [--threshold --robust --compare-threshold]   figures and tables of the paper

Example:
    python cli.py sweep ~/projects/msculpturalis
    python cli.py report ~/projects/msculpturalis --threshold 4.4
"""
import argparse
import os
import sys

from bioinvasion import pipeline
from bioinvasion.config import PROJECT_TEMPLATE, load_config
from bioinvasion.report.insights import fmt
from bioinvasion.sources.files import InvalidPresenceData

ICONS = {"ok": "✔", "info": "ℹ", "warn": "⚠", "tip": "➜"}


def print_messages(messages):
    for level, text in messages:
        print(f"  {ICONS[level]} {text.replace('**', '')}")


def cmd_init(a):
    os.makedirs(a.project, exist_ok=True)
    path = os.path.join(a.project, "project.toml")
    if os.path.exists(path):
        sys.exit(f"'{path}' exists already; not overwritten.")
    with open(path, "w", encoding="utf-8") as f:
        f.write(PROJECT_TEMPLATE)
    print(f"Created '{path}'. Edit [data] and [cost], then run: python cli.py sweep {a.project}")


def cmd_import(a):
    pipeline.import_presence(load_config(a.project), force=a.force)


def cmd_paths(a):
    pipeline.compute_paths(load_config(a.project), force=a.force)


def cmd_sweep(a):
    given = [a.from_, a.to, a.step]
    if any(v is not None for v in given) and not all(v is not None for v in given):
        sys.exit("--from, --to and --step must be given together.")
    cfg = load_config(a.project)
    coarse, fine, chosen = pipeline.sweep(cfg, a.from_, a.to, a.step)
    from bioinvasion.report.insights import nearest_definition, stable_ranges
    d = nearest_definition(fine, cfg.delineation.robust_definition)
    print(f"\nStable ranges in the high-resolution sweep (robust definition {d:g}, average rate within "
          f"±{cfg.sweep.stable_tolerance:.0%}):")
    for r in stable_ranges(fine, d, cfg.sweep.stable_tolerance, cfg.sweep.max_quantile, cfg.sweep.n_ranges):
        print(f"  {fmt(r['from'])}–{fmt(r['to'])} (Q{r['q_from']:.3f}–Q{r['q_to']:.3f}): "
              f"{r['rate_min']:.1f}–{r['rate_max']:.1f} km/year")
    print("\nNext: choose a threshold, e.g. at the beginning of a stable range, and run "
          f"python cli.py report {a.project} --threshold <value>")


def cmd_delineate(a):
    pipeline.delineate(load_config(a.project), a.threshold, a.robust)


def cmd_report(a):
    out_dir, text, checks = pipeline.report(load_config(a.project), a.threshold, a.robust, a.compare_threshold)
    print("\n" + text + "\n\nChecks:")
    print_messages(checks)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    def command(name, func, help):
        c = sub.add_parser(name, help=help)
        c.add_argument("project", help="project folder containing project.toml")
        c.set_defaults(func=func)
        return c

    command("init", cmd_init, "write a project.toml template")
    command("import", cmd_import, "read the observations").add_argument(
        "--force", action="store_true", help="import again even if nothing changed (e.g. new iNaturalist data)")
    command("paths", cmd_paths, "calculate least-cost paths").add_argument(
        "--force", action="store_true", help="recalculate even if nothing changed")
    c = command("sweep", cmd_sweep, "sensitivity sweep")
    c.add_argument("--from", dest="from_", type=float, help="high-resolution range: first threshold")
    c.add_argument("--to", type=float, help="high-resolution range: last threshold")
    c.add_argument("--step", type=float, help="high-resolution range: step")
    for name, func, help in (("delineate", cmd_delineate, "populations and expansion rates"),
                             ("report", cmd_report, "figures and tables of the paper")):
        c = command(name, func, help)
        c.add_argument("--threshold", type=float, help="accumulated cost threshold (default: [delineation] threshold)")
        c.add_argument("--robust", type=float, help="robust population definition (default: [delineation])")
        if name == "report":
            c.add_argument("--compare-threshold", type=float,
                           help="second threshold, shown as an additional population map (Fig. 5b of the paper)")
    a = p.parse_args()
    try:
        a.func(a)
    except (InvalidPresenceData, ValueError, FileNotFoundError) as e:
        sys.exit(f"ERROR: {e}")


if __name__ == "__main__":
    main()
