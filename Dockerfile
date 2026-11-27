# Web app image, e.g. for Hugging Face Spaces (see docs/deployment.md).
# The wheels of rasterio, pyogrio and shapely include GDAL/GEOS/PROJ, so no system packages are needed.
FROM python:3.13-slim

# Hugging Face Spaces run containers as user 1000
RUN useradd -m -u 1000 user
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user pyproject.toml .
COPY --chown=user bioinvasion bioinvasion
COPY --chown=user webapp webapp
COPY --chown=user data/cost_surface_gtopo30_esri102031_5km_exp_rescaled.tif data/
RUN pip install --no-cache-dir --no-deps .

USER user
ENV BIOINVASION_JOBS_DIR=/tmp/bioinvasion_jobs \
    MPLCONFIGDIR=/tmp/matplotlib
# Country borders (Natural Earth) for maps and the iNaturalist country assignment, downloaded once at build time
RUN python -c "from bioinvasion.naturalearth import natural_earth; natural_earth('countries')"
EXPOSE 7860
# One worker process (sessions share the job folders on disk); long computations run as background processes
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "600", "-b", "0.0.0.0:7860", "webapp.app:server"]
