from __future__ import annotations

from pathlib import Path
import colorsys
import re

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
from folium.features import DivIcon, GeoJsonPopup, GeoJsonTooltip


# This script lives in data/processed/, so project root is two levels up.
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT_HTML = Path(__file__).resolve().with_name("test_map_buffer_comparison.html")

ISTAT_SHP = RAW / "R04_21_WGS84.shp"
DISTRICTS_GEOJSON = RAW / "districts.geojson"
POINTS_GEOJSON = RAW / "sections.geojson"

EPSG_METRIC = 32632
EPSG_WEB = 4326
BUFFER_M = 40.0


def normalize_key(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\\.0$", "", regex=True)
        .replace({"nan": np.nan, "None": np.nan, "": np.nan})
    )


def find_col(df: pd.DataFrame, candidates: list[str], required: bool = True) -> str | None:
    low = {c.lower(): c for c in df.columns}
    for cand in candidates:
        c = low.get(cand.lower())
        if c is not None:
            return c
    if required:
        raise KeyError(f"None of {candidates} found in columns: {list(df.columns)}")
    return None


def mode_or_nan(series: pd.Series) -> object:
    s = series.dropna().astype(str)
    if s.empty:
        return np.nan
    counts = s.value_counts()
    max_count = counts.max()
    winners = sorted(counts[counts == max_count].index.tolist())
    return winners[0]


def compact_section_label(value: object) -> str:
    text = str(value)
    m = re.findall(r"\d+", text)
    return m[-1] if m else text


def build_color_lookup(values: pd.Series) -> dict[str, str]:
    unique_values = sorted([str(v) for v in pd.Series(values).dropna().unique().tolist()])
    total = len(unique_values)
    if total == 0:
        return {}

    # High-contrast categorical palette first, then deterministic HSV fallback.
    palette = [
        "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b",
        "#e377c2", "#17becf", "#bcbd22", "#7f7f7f", "#4e79a7", "#f28e2b",
        "#e15759", "#76b7b2", "#59a14f", "#edc948", "#b07aa1", "#ff9da7",
        "#9c755f", "#bab0ab", "#006d77", "#ef476f", "#118ab2", "#ffd166",
    ]

    color_lookup: dict[str, str] = {}
    for idx, key in enumerate(unique_values):
        if idx < len(palette):
            color_lookup[key] = palette[idx]
            continue

        hue = (idx - len(palette)) / max(total - len(palette), 1)
        sat = 0.72 if idx % 2 == 0 else 0.86
        val = 0.90 if idx % 3 == 0 else 0.80
        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
        color_lookup[key] = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
    return color_lookup


def load_points_metric() -> gpd.GeoDataFrame:
    points = gpd.read_file(POINTS_GEOJSON).to_crs(EPSG_METRIC)

    id_section_col = find_col(points, ["id_section", "ID_SECTION", "section_id"])
    district_col = find_col(points, ["district", "DISTRICT"], required=False)
    street_col = find_col(points, ["streetname", "street", "via", "address"], required=False)
    house_col = find_col(points, ["housenumber", "number", "civico"], required=False)

    points = points.copy()
    points["id_section"] = normalize_key(points[id_section_col])
    if district_col is None:
        points["district"] = ""
    else:
        points["district"] = points[district_col].astype(str).str.strip()

    street_values = points[street_col].astype(str).str.strip() if street_col else pd.Series("", index=points.index)
    house_values = points[house_col].astype(str).str.strip() if house_col else pd.Series("", index=points.index)
    points["address"] = (street_values + " " + house_values).str.replace(r"\s+", " ", regex=True).str.strip()

    points = points.dropna(subset=["id_section", "geometry"]).copy()
    points = points[~points.geometry.is_empty].copy()
    return points[["id_section", "district", "address", "geometry"]].copy()


def load_districts_metric() -> gpd.GeoDataFrame:
    districts = gpd.read_file(DISTRICTS_GEOJSON).to_crs(EPSG_METRIC)
    district_col = find_col(districts, ["district", "DISTRICT", "name"])
    id_col = find_col(districts, ["id_district", "ID_DISTRICT", "district_id"], required=False)

    out = districts.copy()
    out["district"] = out[district_col].astype(str).str.strip()
    if id_col is None:
        out["id_district"] = np.arange(1, len(out) + 1)
    else:
        out["id_district"] = pd.to_numeric(out[id_col], errors="coerce")

    out = out[["id_district", "district", "geometry"]].copy()
    out = out[out.geometry.is_valid & ~out.geometry.is_empty].copy()
    return out


def load_istat_metric() -> gpd.GeoDataFrame:
    istat = gpd.read_file(ISTAT_SHP).to_crs(EPSG_METRIC)
    sez_col = find_col(istat, ["SEZ21_ID", "SEZ21"])
    sub_col = find_col(istat, ["COD_AREA_S", "COD_TIPO_S"], required=False)

    istat = istat.copy()
    istat["SEZ21_ID"] = normalize_key(istat[sez_col])
    istat["COD_AREA_S"] = istat[sub_col].astype(str) if sub_col else ""

    istat = istat[["SEZ21_ID", "COD_AREA_S", "geometry"]].copy()
    istat = istat[istat.geometry.is_valid & ~istat.geometry.is_empty].copy()
    return istat


def clip_to_municipal_boundary(gdf_metric: gpd.GeoDataFrame, municipal_boundary) -> gpd.GeoDataFrame:
    if gdf_metric.empty:
        return gdf_metric

    mask = gpd.GeoDataFrame({"geometry": [municipal_boundary]}, crs=EPSG_METRIC)
    filtered = gdf_metric[gdf_metric.geometry.intersects(municipal_boundary)].copy()
    if filtered.empty:
        return filtered

    clipped = gpd.clip(filtered, mask)
    clipped = clipped[clipped.geometry.is_valid & ~clipped.geometry.is_empty].copy()
    return clipped


def build_sections_buffer_dissolve(
    points_metric: gpd.GeoDataFrame,
    municipal_boundary,
    buffer_m: float = BUFFER_M,
) -> gpd.GeoDataFrame:
    """
    Topological approach only:
    1) buffer around each point
    2) dissolve by id_section

    This naturally creates MultiPolygon sections when the same section
    has distant groups of civic points (no artificial bridge lines).
    """
    if points_metric.empty:
        raise ValueError("No points available for section generation.")

    buffered = points_metric[["id_section", "geometry"]].copy()
    buffered["geometry"] = buffered.geometry.buffer(buffer_m)
    buffered = buffered[buffered.geometry.is_valid & ~buffered.geometry.is_empty].copy()

    sections = buffered.dissolve(by="id_section", as_index=False)
    sections = gpd.GeoDataFrame(sections, geometry="geometry", crs=EPSG_METRIC)

    sections["geometry"] = sections.geometry.buffer(0)
    sections = sections[sections.geometry.is_valid & ~sections.geometry.is_empty].copy()

    sections = clip_to_municipal_boundary(sections, municipal_boundary)
    sections["id_section"] = normalize_key(sections["id_section"])

    district_map = (
        points_metric[["id_section", "district"]]
        .dropna(subset=["id_section"])
        .groupby("id_section", as_index=False)["district"]
        .agg(lambda s: mode_or_nan(pd.Series(s)))
    )
    sections = sections.merge(district_map, on="id_section", how="left")

    return sections


def add_layer_circoscrizioni(m: folium.Map, districts_4326: gpd.GeoDataFrame, district_colors: dict[str, str]) -> None:
    fg = folium.FeatureGroup(name="Circoscrizioni", show=True)

    folium.GeoJson(
        districts_4326,
        style_function=lambda feat: {
            "color": district_colors.get(str(feat["properties"].get("district")), "#555555"),
            "weight": 1.8,
            "fillColor": district_colors.get(str(feat["properties"].get("district")), "#555555"),
            "fillOpacity": 0.45,
        },
        highlight_function=lambda _: {"weight": 3.0, "fillOpacity": 0.60},
        tooltip=GeoJsonTooltip(fields=["district"], aliases=["Circoscrizione:"], sticky=True),
        popup=GeoJsonPopup(fields=["id_district", "district"], aliases=["ID:", "Circoscrizione:"], labels=True),
    ).add_to(fg)

    fg.add_to(m)


def add_layer_istat(m: folium.Map, istat_4326: gpd.GeoDataFrame) -> None:
    fg = folium.FeatureGroup(name="Sezioni ISTAT", show=False)

    folium.GeoJson(
        istat_4326,
        style_function=lambda _: {
            "color": "#111111",
            "weight": 0.8,
            "fillColor": "#000000",
            "fillOpacity": 0.0,
        },
        highlight_function=lambda _: {"weight": 1.8},
        popup=GeoJsonPopup(
            fields=["SEZ21_ID", "COD_AREA_S"],
            aliases=["SEZ21_ID:", "COD_AREA_S:"],
            labels=True,
        ),
    ).add_to(fg)

    fg.add_to(m)


def add_layer_sezioni_buffer(
    m: folium.Map,
    sections_4326: gpd.GeoDataFrame,
    section_colors: dict[str, str],
) -> None:
    fg = folium.FeatureGroup(name="Sezioni Elettorali (Buffer 40m + Dissolve)", show=True)

    folium.GeoJson(
        sections_4326,
        style_function=lambda feat: {
            "color": section_colors.get(str(feat["properties"].get("id_section")), "#666666"),
            "weight": 1.0,
            "fillColor": section_colors.get(str(feat["properties"].get("id_section")), "#666666"),
            "fillOpacity": 0.30,
        },
        highlight_function=lambda _: {"weight": 2.4, "fillOpacity": 0.45},
        tooltip=GeoJsonTooltip(fields=["id_section"], aliases=["Sezione:"], sticky=True),
        popup=GeoJsonPopup(fields=["id_section"], aliases=["Sezione Elettorale:"], labels=True),
    ).add_to(fg)

    labels = sections_4326.copy()
    labels["label_point"] = labels.geometry.representative_point()

    for row in labels.itertuples(index=False):
        pt = row.label_point
        if pt.is_empty:
            continue

        sec_id = str(row.id_section)
        label_id = compact_section_label(sec_id)
        color = section_colors.get(sec_id, "#555555")

        html = (
            "<div style=\""
            "font-size:9px;"
            "font-weight:700;"
            "color:" + color + ";"
            "text-shadow:0 0 2px #ffffff, 0 0 2px #ffffff;"
            "white-space:nowrap;"
            "\">"
            + label_id
            + "</div>"
        )

        folium.Marker(
            location=[pt.y, pt.x],
            icon=DivIcon(html=html),
        ).add_to(fg)

    fg.add_to(m)


def add_layer_civici(
    m: folium.Map,
    points_4326: gpd.GeoDataFrame,
    section_colors: dict[str, str],
) -> None:
    fg = folium.FeatureGroup(name="Civici", show=False)

    folium.GeoJson(
        points_4326,
        marker=folium.CircleMarker(radius=2.4, fill=True, fill_opacity=0.95, opacity=0.85),
        style_function=lambda feat: {
            "color": section_colors.get(str(feat["properties"].get("id_section")), "#666666"),
            "fillColor": section_colors.get(str(feat["properties"].get("id_section")), "#666666"),
            "weight": 0.5,
        },
        tooltip=GeoJsonTooltip(fields=["address", "id_section"], aliases=["Indirizzo:", "Sezione:"], sticky=True),
        popup=GeoJsonPopup(fields=["address", "id_section"], aliases=["Indirizzo:", "Sezione:"], labels=True),
    ).add_to(fg)

    fg.add_to(m)


def build_map(
    districts_metric: gpd.GeoDataFrame,
    istat_metric: gpd.GeoDataFrame,
    sections_metric: gpd.GeoDataFrame,
    points_metric: gpd.GeoDataFrame,
) -> folium.Map:
    districts_4326 = districts_metric.to_crs(EPSG_WEB)
    istat_4326 = istat_metric.to_crs(EPSG_WEB)
    sections_4326 = sections_metric.to_crs(EPSG_WEB)
    points_4326 = points_metric.to_crs(EPSG_WEB)

    district_colors = build_color_lookup(districts_4326["district"])
    section_colors = build_color_lookup(sections_4326["id_section"])

    center_geom = gpd.GeoSeries([districts_metric.geometry.union_all()], crs=EPSG_METRIC).to_crs(EPSG_WEB).iloc[0]
    center = center_geom.centroid

    m = folium.Map(
        location=[center.y, center.x],
        zoom_start=12,
        tiles="CartoDB Positron",
        control_scale=True,
    )

    add_layer_circoscrizioni(m, districts_4326, district_colors)
    add_layer_istat(m, istat_4326)
    add_layer_sezioni_buffer(m, sections_4326, section_colors)
    add_layer_civici(m, points_4326, section_colors)

    folium.LayerControl(collapsed=False).add_to(m)

    minx, miny, maxx, maxy = districts_4326.total_bounds
    bounds = [[float(miny), float(minx)], [float(maxy), float(maxx)]]
    m.fit_bounds(bounds)
    m.options["maxBounds"] = bounds

    return m


def main() -> None:
    points_metric = load_points_metric()
    districts_metric = load_districts_metric()
    municipal_boundary = districts_metric.geometry.union_all().buffer(0)

    istat_metric = load_istat_metric()
    istat_metric = clip_to_municipal_boundary(istat_metric, municipal_boundary)

    sections_metric = build_sections_buffer_dissolve(points_metric, municipal_boundary, buffer_m=BUFFER_M)

    m = build_map(districts_metric, istat_metric, sections_metric, points_metric)
    m.save(OUT_HTML)

    print(f"Saved map: {OUT_HTML}")
    print(f"District polygons: {len(districts_metric)}")
    print(f"ISTAT polygons (clipped): {len(istat_metric)}")
    print(f"Sections (buffer+dissolve): {len(sections_metric)}")
    print(f"Civic points: {len(points_metric)}")


if __name__ == "__main__":
    main()
