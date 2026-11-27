"""Smoke test: the demo project runs from import to export through cli.py (about 15 s)."""
import os
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(REPO, "examples", "isodontia")


def test_demo_export(tmp_path):
    with open(os.path.join(tmp_path, "project.toml"), "w") as f:
        f.write(f'[data]\nsource = "csv"\nfile = "{DEMO}/isodontia_mexicana_gbif_20241227.csv"\n'
                f'[cost]\nfile = "{REPO}/data/cost_surface_gtopo30_esri102031_5km_exp_rescaled.tif"\nlabel = "demo"\n'
                f'[sweep]\nfine_from = 0.1\nfine_to = 0.3\nfine_step = 0.05\n[delineation]\nthreshold = 0.19\n')

    def cli(*args):
        result = subprocess.run([sys.executable, os.path.join(REPO, "cli.py"), *args, str(tmp_path)],
                                capture_output=True, text=True, cwd=REPO)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    cli("sweep")
    cli("export")
    folder = os.path.join(tmp_path, "paths__demo__1993-2024", "delin__t0.19__r10")
    with zipfile.ZipFile(os.path.join(folder, "export.zip")) as z:
        names = z.namelist()
        assert "settings.txt" in names and "populations.gpkg" in names and "years/2024.png" in names
        assert "Accumulated cost threshold: 0.19" in z.read("settings.txt").decode()
    # A second delineation with another threshold reuses the paths
    assert "Paths: up to date" in cli("delineate", "--threshold", "0.1")
