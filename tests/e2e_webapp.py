"""
Manual end-to-end test of the web app in a headless browser (not run by pytest, as it needs Playwright).

Setup once (in the project environment):  pip install playwright && python -m playwright install chromium
Run:  python -m webapp  (in a second terminal, with DASH_DEBUG=0)
      python tests/e2e_webapp.py . /tmp/e2e        # screenshots and the downloaded zip go to /tmp/e2e
Another server: APP_URL=http://127.0.0.1:7860 python tests/e2e_webapp.py . /tmp/e2e
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

repo, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
sys.path.insert(0, repo)
from tests.synthetic import REPO_DEMO_SURFACE, write_observations  # noqa: E402

observations = write_observations(os.path.join(repo, REPO_DEMO_SURFACE), os.path.join(out, "observations.csv"))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8050")
bad_csv = os.path.join(out, "bad.csv")
with open(bad_csv, "w") as f:
    f.write("lon;lat;Jahr\n8,5;47,3;2020\n")


def step(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto(URL)
    page.get_by_text("Europe, 5 km cells").click()
    page.wait_for_selector("#cost-result >> text=cells of 5000 m")
    step("cost surface: " + page.inner_text("#cost-result").replace("\n", " | "))
    page.screenshot(path=f"{out}/1_cost.png", full_page=True)

    page.click("text=2 Observations")
    page.set_input_files("#obs-upload input[type=file]", bad_csv)
    page.wait_for_selector("#obs-result .error")
    step("bad CSV: " + page.inner_text("#obs-result"))
    page.set_input_files("#obs-upload input[type=file]", observations)
    page.wait_for_selector("#obs-result >> text=Observations imported", timeout=60000)
    step("import: " + page.inner_text("#obs-result").split("\n")[0][:300])
    page.screenshot(path=f"{out}/2_observations.png", full_page=True)
    page.click("#obs-compute")
    page.wait_for_selector("#obs-compute-result >> text=are ready", timeout=600000)
    step("compute: " + page.inner_text("#obs-compute-result")[:400].replace("\n", " | "))

    page.click("text=3 Thresholds")
    page.wait_for_selector("#thr-rule .msg", timeout=60000)
    step("thresholds: threshold input = " + page.input_value("#thr-threshold") + "; " +
         page.inner_text("#thr-ranges").replace("\n", " | ")[:300])
    page.click("#thr-apply")
    page.wait_for_selector("#thr-result >> text=paths kept", timeout=120000)
    step("populations: " + page.inner_text("#thr-result")[:600].replace("\n", " | "))
    page.wait_for_timeout(2000)
    page.screenshot(path=f"{out}/3_thresholds.png", full_page=True)

    page.click("text=4 Export")
    page.wait_for_selector("#exp-current .msg")
    with page.expect_download(timeout=300000) as dl:
        page.click("#exp-build")
    path = os.path.join(out, "results.zip")
    dl.value.save_as(path)
    step(f"export: {os.path.getsize(path):,} bytes")
    page.screenshot(path=f"{out}/4_export.png", full_page=True)
    step("browser console errors: " + ("; ".join(errors[:5]) or "none"))
    browser.close()
