"""
Import of presence data from CSV or GeoPackage into the standard presence schema used by the analysis:

    year       integer, year of the observation
    location   text, e.g. country or region (may be empty); names the populations, e.g. "France 2008"
    source     text, where the observation comes from (may be empty)
    source_id  text, ID of the observation in its source (may be empty)
    geometry   point, WGS84 (EPSG:4326)

The files are checked strictly. Nothing is guessed or repaired: if a file does not match the specification below,
the import stops with InvalidPresenceData that explains which rule is violated and in which rows.

CSV specification
    - Encoding UTF-8 ("CSV UTF-8" in Excel; a byte order mark is allowed).
    - Separator comma or semicolon, recognised from the header line. With semicolons, a decimal comma is accepted
      in longitude and latitude (Excel's default in e.g. German locales).
    - Required columns: longitude, latitude (WGS84 decimal degrees), year (integer).
    - Optional columns: location, source, source_id. All other columns are ignored.

GeoPackage specification
    - One layer with point geometries and a defined coordinate reference system (any CRS; converted to WGS84).
      If the file has several layers, the layer must be named.
    - Required column: year (integer). Optional columns: location, source, source_id. All other columns are ignored.
"""
import os
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

REQUIRED_CSV = ["longitude", "latitude", "year"]
OPTIONAL = ["location", "source", "source_id"]
MAX_LISTED = 10


class InvalidPresenceData(Exception):
    """Presence data does not match the specification. The message says why."""


def _rows(mask, offset=2):
    """Row numbers as shown in a spreadsheet (header = row 1) for a boolean mask."""
    rows = list(np.flatnonzero(np.asarray(mask)) + offset)
    more = f" and {len(rows) - MAX_LISTED} more" if len(rows) > MAX_LISTED else ""
    return ", ".join(str(r) for r in rows[:MAX_LISTED]) + more


def _standardise(df, geometry, crs, name, report):
    """Builds the standard schema from validated columns and records dropped columns in the report."""
    dropped = [c for c in df.columns if c not in REQUIRED_CSV + OPTIONAL]
    report.append(f"Columns ignored: {', '.join(dropped) if dropped else 'none'}")
    out = gpd.GeoDataFrame({
        "year": df["year"].to_numpy(dtype="int32"),
        "location": df["location"].fillna("").astype(str).to_numpy() if "location" in df else "",
        "source": df["source"].fillna("").astype(str).to_numpy() if "source" in df else name,
        "source_id": df["source_id"].fillna("").astype(str).to_numpy() if "source_id" in df else "",
    }, geometry=geometry, crs=crs).to_crs(4326)
    if "source" not in df:
        report.append(f"No 'source' column: source set to the file name '{name}'")
    report.append(f"Observations imported: {len(out)} ({out['year'].min()}-{out['year'].max()})")
    return out, report


def _check_year(values, report_rows):
    text = values.astype(str).str.strip()
    bad = ~text.str.fullmatch(r"-?\d+")
    if bad.any():
        raise InvalidPresenceData(f"Column 'year' must contain whole numbers (e.g. 2021), without dates or empty cells. "
                          f"Invalid in row(s) {report_rows(bad)}.")
    return text.astype(int)


def read_csv(path):
    """Reads a CSV file as specified in the module docstring. Returns (GeoDataFrame, report lines)."""
    name = os.path.basename(path)
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except UnicodeDecodeError:
        raise InvalidPresenceData(f"'{name}' is not UTF-8 encoded. In Excel, save it as 'CSV UTF-8 (comma delimited)'.")
    header = text.split("\n", 1)[0].strip()
    matches = [sep for sep in (",", ";") if set(REQUIRED_CSV) <= {c.strip() for c in header.split(sep)}]
    if len(matches) != 1:
        found = ", ".join(f"'{c.strip()}'" for c in re.split(r"[;,]", header))
        raise InvalidPresenceData(f"The header line of '{name}' must contain the columns {', '.join(REQUIRED_CSV)} "
                          f"(lower case), separated by commas or by semicolons. Found: {found}.")
    sep = matches[0]
    df = pd.read_csv(path, sep=sep, dtype=str, encoding="utf-8-sig", keep_default_na=False, na_values=[""])
    df.columns = [c.strip() for c in df.columns]
    if df.columns.duplicated().any():
        raise InvalidPresenceData(f"Duplicate column names in '{name}': {', '.join(df.columns[df.columns.duplicated()])}.")
    decimal = "comma" if sep == ";" else "point"
    report = [f"Source: CSV file '{name}'", f"Rows read: {len(df)}",
              f"Separator: {'semicolon' if sep == ';' else 'comma'} (recognised from the header line); "
              f"decimal mark in coordinates: point{' or comma' if sep == ';' else ''}"]

    coords = {}
    for col, limit in (("longitude", 180), ("latitude", 90)):
        raw = df[col].str.strip()
        if decimal == "comma":
            raw = raw.str.replace(",", ".", regex=False)
        value = pd.to_numeric(raw, errors="coerce")
        bad = value.isna()
        if bad.any():
            raise InvalidPresenceData(f"Column '{col}' must contain decimal degrees (WGS84), e.g. 47.37. Missing or not a "
                              f"number in row(s) {_rows(bad)}.")
        bad = value.abs() > limit
        if bad.any():
            raise InvalidPresenceData(f"Column '{col}' must lie between -{limit} and {limit} (WGS84 decimal degrees). "
                              f"Out of range in row(s) {_rows(bad)}. Coordinates in other reference systems are not "
                              f"accepted; please convert them to WGS84 first.")
        coords[col] = value
    if df["year"].isna().any():
        raise InvalidPresenceData(f"Column 'year' is empty in row(s) {_rows(df['year'].isna())}.")
    df["year"] = _check_year(df["year"], _rows)
    return _standardise(df, gpd.points_from_xy(coords["longitude"], coords["latitude"]), 4326, name, report)


def gpkg_layers(path):
    return [layer for layer, _ in pyogrio.list_layers(path)]


def read_gpkg(path, layer=None):
    """Reads a GeoPackage as specified in the module docstring. Returns (GeoDataFrame, report lines)."""
    name = os.path.basename(path)
    layers = gpkg_layers(path)
    if layer:
        if layer not in layers:
            raise InvalidPresenceData(f"Layer '{layer}' not found in '{name}'. Layers: {', '.join(layers)}.")
    elif len(layers) == 1:
        layer = layers[0]
    else:
        raise InvalidPresenceData(f"'{name}' has {len(layers)} layers ({', '.join(layers)}). Please choose one.")
    gdf = gpd.read_file(path, layer=layer)
    report = [f"Source: GeoPackage '{name}', layer '{layer}'", f"Rows read: {len(gdf)}"]
    if gdf.crs is None:
        raise InvalidPresenceData(f"Layer '{layer}' has no coordinate reference system defined.")
    report.append(f"Coordinate reference system: {gdf.crs.to_string()} (converted to WGS84)")
    if gdf.geometry.isna().any() or gdf.geometry.is_empty.any():
        bad = gdf.geometry.isna() | gdf.geometry.is_empty
        raise InvalidPresenceData(f"Layer '{layer}' has rows without geometry: row(s) {_rows(bad, offset=1)} "
                          f"(counting features from 1).")
    if not (gdf.geom_type == "Point").all():
        types = ", ".join(sorted(set(gdf.geom_type) - {"Point"}))
        raise InvalidPresenceData(f"Layer '{layer}' must contain single points only, but also contains: {types}.")
    if "year" not in gdf.columns:
        raise InvalidPresenceData(f"Layer '{layer}' has no column 'year'. Columns: {', '.join(gdf.columns.drop('geometry'))}.")
    if gdf["year"].isna().any():
        raise InvalidPresenceData(f"Column 'year' is empty in feature(s) {_rows(gdf['year'].isna(), offset=1)}.")
    if pd.api.types.is_float_dtype(gdf["year"]) and (gdf["year"] % 1 == 0).all():
        gdf["year"] = gdf["year"].astype(int)  # integer column read as float by the GDAL driver
    gdf["year"] = _check_year(gdf["year"], lambda m: _rows(m, offset=1))
    return _standardise(gdf.drop(columns="geometry"), gdf.geometry.values, gdf.crs, name, report)
