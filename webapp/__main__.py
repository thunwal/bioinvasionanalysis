"""Starts the web app locally: python -m webapp  (then open http://127.0.0.1:8050)"""
import os

from webapp.app import app

if __name__ == "__main__":
    app.run(debug=os.environ.get("DASH_DEBUG", "1") == "1", host="127.0.0.1", port=8050)
