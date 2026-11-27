"""Smoke test: invented observations (tests/synthetic.py) run from import to export through cli.py (about 15 s)."""
import os
import subprocess
import sys
import zipfile

from tests.synthetic import REPO_DEMO_SURFACE, write_observations

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_cli_export(tmp_path):
    write_observations(os.path.join(REPO, REPO_DEMO_SURFACE), os.path.join(tmp_path, "observations.csv"))
    with open(os.path.join(tmp_path, "project.toml"), "w") as f:
        f.write(f'[data]\nsource = "csv"\nfile = "observations.csv"\n'
                f'[cost]\nfile = "{REPO}/{REPO_DEMO_SURFACE}"\nlabel = "demo"\n'
                f'[sensitivity]\nfine_from = 20\nfine_to = 30\nfine_step = 2\n[delineation]\nthreshold = 25\n')

    def cli(*args):
        result = subprocess.run([sys.executable, os.path.join(REPO, "cli.py"), *args, str(tmp_path)],
                                capture_output=True, text=True, cwd=REPO)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    cli("sensitivity")
    cli("export")
    folder = os.path.join(tmp_path, "paths__demo__2011-2024", "delin__t25__r10")
    with zipfile.ZipFile(os.path.join(folder, "export.zip")) as z:
        names = z.namelist()
        assert "settings.txt" in names and "populations.gpkg" in names and "years/2024.png" in names
        assert "sensitivity/sensitivity_coarse.csv" in names
        assert "Accumulated cost threshold: 25" in z.read("settings.txt").decode()
    # A second delineation with another threshold reuses the paths
    assert "Paths: up to date" in cli("delineate", "--threshold", "10")
