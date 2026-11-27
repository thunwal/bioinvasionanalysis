"""
Job folders of the web app. Each browser session gets one job: a normal project folder (project.toml + results, see
bioinvasion/pipeline.py) under JOBS_DIR, so a job can also be inspected or continued with cli.py. Jobs are deleted
after JOB_TTL_HOURS. The limits below protect the public server.
"""
import os
import re
import shutil
import time
import tomllib
import uuid

from bioinvasion.config import load_config

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.environ.get("BIOINVASION_JOBS_DIR", os.path.join(REPO, "webapp_jobs"))
RUNNING_DIR = os.path.join(JOBS_DIR, "_running")

JOB_TTL_HOURS = 24
MAX_UPLOAD_MB = 50
MAX_CELLS = 2_000_000          # raster cells of an uploaded cost surface
MAX_OBSERVATIONS = 20_000      # observations after import (also the iNaturalist download limit)
MAX_RUNNING = 2                # concurrent path and sensitivity test computations on the server

DEMO_SURFACES = {
    "terrain5km": ("Europe, 5 km cells, based on terrain only (GTOPO30 elevation, costs 1 to 10; demo)",
                   os.path.join(REPO, "data", "cost_surface_gtopo30_esri102031_5km_exp_base1_k9.tif")),
}


def new_job():
    cleanup()
    job = uuid.uuid4().hex
    os.makedirs(os.path.join(JOBS_DIR, job))
    write_config(job, {})
    return job


def job_dir(job):
    """Folder of a job. The id comes from the browser, so it is checked strictly."""
    if not job or not re.fullmatch(r"[0-9a-f]{32}", job):
        raise ValueError("Invalid session. Please reload the page.")
    path = os.path.join(JOBS_DIR, job)
    if not os.path.isdir(path):
        raise ValueError("This session has expired (results are kept for 24 hours). Please reload the page.")
    return path


def exists(job):
    try:
        job_dir(job)
        return True
    except ValueError:
        return False


def cleanup():
    if not os.path.isdir(JOBS_DIR):
        return
    limit = time.time() - JOB_TTL_HOURS * 3600
    for name in os.listdir(JOBS_DIR):
        path = os.path.join(JOBS_DIR, name)
        if re.fullmatch(r"[0-9a-f]{32}", name) and os.path.getmtime(path) < limit:
            shutil.rmtree(path, ignore_errors=True)


def safe_name(filename):
    name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(filename or "upload"))
    return name.lstrip(".") or "upload"


# ------------------------------------------------------------------ project.toml of a job ---------------------------

def read_settings(job):
    path = os.path.join(job_dir(job), "project.toml")
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_config(job, changes):
    """Merges {section: {key: value}} into the job's project.toml; a value None removes the key."""
    settings = read_settings(job) if os.path.exists(os.path.join(job_dir(job), "project.toml")) else {}
    for section, values in changes.items():
        current = settings.setdefault(section, {})
        for key, value in values.items():
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value
    lines = ["# Settings of a web app session. The same file works with the command line: python cli.py report <folder>"]
    for section, values in settings.items():
        lines.append(f"\n[{section}]")
        lines += [f"{k} = {_toml_value(v)}" for k, v in values.items() if not isinstance(v, dict)]
    with open(os.path.join(job_dir(job), "project.toml"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def config(job):
    return load_config(job_dir(job))


# ------------------------------------------------------------------ limit concurrent computations -------------------

class Busy(Exception):
    pass


class running:
    """Context manager that allows at most MAX_RUNNING computations at the same time."""

    def __init__(self, job):
        self.marker = os.path.join(RUNNING_DIR, job)

    def __enter__(self):
        os.makedirs(RUNNING_DIR, exist_ok=True)
        limit = time.time() - 3 * 3600  # markers of crashed computations expire
        active = [m for m in os.listdir(RUNNING_DIR) if os.path.getmtime(os.path.join(RUNNING_DIR, m)) > limit]
        if len(active) >= MAX_RUNNING and os.path.basename(self.marker) not in active:
            raise Busy("The server is busy with other computations. Please try again in a few minutes.")
        open(self.marker, "w").close()
        return self

    def __exit__(self, *exc):
        if os.path.exists(self.marker):
            os.remove(self.marker)
