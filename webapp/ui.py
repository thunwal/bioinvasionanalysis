"""Small building blocks shared by the pages."""
import base64
import os

from dash import dcc, html

from webapp import jobs

LEVEL_CLASS = {"ok": "msg ok", "info": "msg info", "warn": "msg warn", "tip": "msg tip", "error": "msg error"}


def flat(*items):
    """Dash children must be a flat list: flattens nested lists and drops None."""
    out = []
    for item in items:
        if isinstance(item, (list, tuple)):
            out += flat(*item)
        elif item is not None:
            out.append(item)
    return out


def messages(items):
    """List of (level, Markdown text) as coloured notes."""
    return [html.Div(dcc.Markdown(text), className=LEVEL_CLASS[level]) for level, text in items]


def error(text):
    return messages([("error", str(text))])


def log_box(lines):
    """The log of a computation, collapsed, for transparency."""
    if not lines:
        return None
    return html.Details([html.Summary("Log of this step"), html.Pre("\n".join(lines))])


def save_upload(job, contents, filename, subfolder):
    """Saves a dcc.Upload file into the job folder. Returns the path relative to the job folder."""
    data = base64.b64decode(contents.split(",", 1)[1])
    if len(data) > jobs.MAX_UPLOAD_MB * 1e6:
        raise ValueError(f"The file is larger than {jobs.MAX_UPLOAD_MB} MB.")
    rel = os.path.join(subfolder, jobs.safe_name(filename))
    path = os.path.join(jobs.job_dir(job), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return rel


class Log(list):
    """Collects the log lines of pipeline functions (pass as log=...)."""

    def __call__(self, msg):
        self.append(msg)
