"""Import of presence data: valid files are read as specified, invalid ones are rejected with a clear reason."""
import geopandas as gpd
import pytest
from shapely.geometry import Point

from bioinvasion.sources.files import InvalidPresenceData, read_csv, read_gpkg


def write(tmp_path, text, encoding="utf-8"):
    path = tmp_path / "obs.csv"
    path.write_bytes(text.encode(encoding))
    return str(path)


def test_excel_semicolon_csv(tmp_path):
    """Semicolons, decimal commas, BOM, extra columns: as exported by a German Excel."""
    path = write(tmp_path, "﻿ID;latitude;longitude;year;location;Bemerkung\n"
                           "1;47,37;8,54;2021;Switzerland;x\n2;48,2;16,37;2022;Austria;\n")
    gdf, report = read_csv(path)
    assert list(gdf.columns) == ["year", "location", "source", "source_id", "geometry"]
    assert gdf.crs.to_epsg() == 4326
    assert gdf.geometry.iloc[0].equals(Point(8.54, 47.37))
    assert list(gdf["year"]) == [2021, 2022]
    text = "\n".join(report)
    assert "semicolon" in text and "ID, Bemerkung" in text and "source set to the file name" in text


def test_comma_csv(tmp_path):
    gdf, _ = read_csv(write(tmp_path, "longitude,latitude,year,source\n8.5,47.3,2020,survey\n"))
    assert gdf["source"].iloc[0] == "survey"


@pytest.mark.parametrize("text, message", [
    ("lon,lat,year\n8.5,47.3,2020\n", "must contain the columns longitude, latitude, year"),
    ("longitude,latitude,year\n8.5,147.3,2020\n", "between -90 and 90"),
    ("longitude,latitude,year\n8.5,47.3,2020-05-01\n", "whole numbers"),
    ("longitude,latitude,year\n8.5,47.3,\n", "empty in row(s) 2"),
    ("longitude,latitude,year\n8.5,abc,2020\n", "not a number in row(s) 2"),
    ("longitude;latitude;year\n8.5;47.3;2020\n2600000;1200000;2020\n", "Out of range in row(s) 3"),
])
def test_invalid_csv(tmp_path, text, message):
    with pytest.raises(InvalidPresenceData, match=message.replace("(", r"\(").replace(")", r"\)")):
        read_csv(write(tmp_path, text))


def test_not_utf8(tmp_path):
    with pytest.raises(InvalidPresenceData, match="UTF-8"):
        read_csv(write(tmp_path, "longitude,latitude,year,location\n8.5,47.3,2020,Zürich\n", encoding="cp1252"))


def test_gpkg(tmp_path):
    path = str(tmp_path / "obs.gpkg")
    gdf = gpd.GeoDataFrame({"year": [2020, 2021], "country": ["CH", "AT"]},
                           geometry=[Point(2600000, 1200000), Point(2610000, 1210000)], crs=2056)
    gdf.to_file(path, layer="a")
    out, report = read_gpkg(path)
    assert out.crs.to_epsg() == 4326 and len(out) == 2
    assert "Columns ignored: country" in report
    gdf.to_file(path, layer="b")
    with pytest.raises(InvalidPresenceData, match=r"has 2 layers \(a, b\)"):
        read_gpkg(path)
    assert len(read_gpkg(path, layer="b")[0]) == 2
