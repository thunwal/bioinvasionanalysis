"""Job folders of the web app: settings round trip and protection against invalid session ids."""
import pytest

from webapp import jobs


def test_job_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "JOBS_DIR", str(tmp_path))
    job = jobs.new_job()
    jobs.write_config(job, {"cost": {"file": "/data/cost.tif", "label": "demo"},
                            "data": {"source": "csv", "file": "upload/a b.csv", "start_year": 2008}})
    jobs.write_config(job, {"data": {"start_year": None}, "delineation": {"threshold": 4.4}})
    cfg = jobs.config(job)
    assert cfg.cost.file == "/data/cost.tif" and cfg.data.file == "upload/a b.csv"
    assert cfg.data.start_year is None and cfg.delineation.threshold == 4.4


@pytest.mark.parametrize("job", ["../etc", "abc", None, "0" * 31 + "/"])
def test_invalid_job_id(job):
    with pytest.raises(ValueError):
        jobs.job_dir(job)


def test_safe_name():
    assert jobs.safe_name("../../evil name.csv") == "evil_name.csv"
