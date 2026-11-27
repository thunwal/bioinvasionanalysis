# Web app image, e.g. for Hugging Face Spaces (see docs/deployment.md).
# The wheels of rasterio, pyogrio and shapely include GDAL/GEOS/PROJ; only libexpat (needed by rasterio's GDAL)
# is missing in the slim base image.
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces run containers as user 1000
RUN useradd -m -u 1000 user
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user pyproject.toml .
COPY --chown=user bioinvasion bioinvasion
COPY --chown=user webapp webapp
# Demo cost surface: downloaded from the GitHub repository at a fixed commit, because Hugging Face Spaces do not
# accept binary files in git. To update it, set the commit of the new version here.
ARG DEMO_SURFACE=https://raw.githubusercontent.com/thunwal/bioinvasionanalysis/8eca1ccad29b6303fe07eba06d5473a9245262d7/data/cost_surface_gtopo30_esri102031_5km_exp_base1_k9.tif
RUN mkdir data && python -c "import urllib.request, sys; urllib.request.urlretrieve(sys.argv[1], 'data/' + sys.argv[1].rsplit('/', 1)[1])" "$DEMO_SURFACE" \
    && chown -R user data
RUN pip install --no-cache-dir --no-deps .

USER user
ENV BIOINVASION_JOBS_DIR=/tmp/bioinvasion_jobs \
    MPLCONFIGDIR=/tmp/matplotlib
# Country borders (Natural Earth) for maps and the iNaturalist country assignment, downloaded once at build time
RUN python -c "from bioinvasion.naturalearth import natural_earth; natural_earth('countries')"
EXPOSE 7860
# One worker process (sessions share the job folders on disk); long computations run as background processes
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "600", "-b", "0.0.0.0:7860", "webapp.app:server"]
