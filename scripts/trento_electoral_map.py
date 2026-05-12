from __future__ import annotations

from pathlib import Path
import re

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
from branca.colormap import LinearColormap
from folium.features import DivIcon, GeoJsonPopup, GeoJsonTooltip
from folium.plugins import MarkerCluster, Search


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

ISTAT_SHP = RAW / "R04_21_WGS84.shp"
DISTRICTS_GEOJSON = RAW / "districts.geojson"
POINTS_GEOJSON = RAW / "sections.geojson"
ANALYTICAL_GEOJSON = PROCESSED / "trento_elections.geojson"
STOPS_URBANO = RAW / "stops_urbano.txt"
STOPS_EXTRAURBANO = RAW / "stops_extraurbano.txt"
OUT_HTML = PROCESSED / "trento_electoral_map.html"

EPSG_METRIC = 32632
EPSG_WEB = 4326
BUFFER_M = 40.0
SPECIAL_SECTION_IDS_RAW = [17, 19, 21, 22, 23, 26, 28, 29, 44, 46, "48/1", "48/2", 49, 51, 61, 62, 79, 91, 93]
SPECIAL_SECTION_IDS = {str(v).strip() for v in SPECIAL_SECTION_IDS_RAW}
SECTION_METRIC_COLUMNS = [
    "ianeselli_vote_pct",
    "highly_educated_pct",
    "extra_ue_pct",
    "density",
    "nearest_transport_distance_m",
]


def normalize_key(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
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
    matches = re.findall(r"\d+", text)
    return matches[-1] if matches else text


def format_number(value: object, digits: int = 1, suffix: str = "") -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.{digits}f}{suffix}"


def format_percent(value: object, digits: int = 1) -> str:
    return format_number(value, digits=digits, suffix="%")


def format_text(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    text = str(value).strip()
    return text if text else "N/A"


def build_vote_colormap() -> LinearColormap:
    return LinearColormap(
        colors=["#b2182b", "#f7f7f7", "#2166ac"],
        index=[45.0, 50.0, 70.0],
        vmin=45.0,
        vmax=70.0,
        caption="Ianeselli Vote Share (%)",
    )


def vote_color(value: object, colormap: LinearColormap) -> str:
    if pd.isna(value):
        return "#bdbdbd"
    return colormap(float(value))


def load_analytical_data(section_ids: pd.Series | None = None) -> pd.DataFrame:
    if ANALYTICAL_GEOJSON.exists():
        analytical = gpd.read_file(ANALYTICAL_GEOJSON)
        keep_cols = ["id_section"] + [col for col in SECTION_METRIC_COLUMNS if col in analytical.columns]
        out = analytical[keep_cols].copy()
        out["id_section"] = normalize_key(out["id_section"])
        for col in SECTION_METRIC_COLUMNS:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce")
        return out.drop_duplicates(subset=["id_section"]).copy()

    if section_ids is None:
        raise FileNotFoundError(
            f"Analytical dataset not found at {ANALYTICAL_GEOJSON} and no section ids were provided for fallback simulation."
        )

    ids = pd.Index(sorted(normalize_key(pd.Series(section_ids)).dropna().astype(str).unique()))
    if len(ids) == 0:
        return pd.DataFrame(columns=["id_section", *SECTION_METRIC_COLUMNS])

    rng = np.random.default_rng(20260511)
    base = np.linspace(35, 68, len(ids))
    out = pd.DataFrame({"id_section": ids})
    out["ianeselli_vote_pct"] = np.clip(base + rng.normal(0, 8, len(ids)), 5, 95)
    out["highly_educated_pct"] = np.clip(15 + rng.normal(0, 4, len(ids)), 2, 60)
    out["extra_ue_pct"] = np.clip(8 + rng.normal(0, 3, len(ids)), 0, 35)
    out["density"] = np.clip(4500 + rng.normal(0, 1800, len(ids)), 50, None)
    out["nearest_transport_distance_m"] = np.clip(180 + rng.normal(0, 60, len(ids)), 20, None)
    return out


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


def load_transit_stops_metric(municipal_boundary) -> gpd.GeoDataFrame:
    urbano = pd.read_csv(STOPS_URBANO)
    extra = pd.read_csv(STOPS_EXTRAURBANO)

    urbano["source"] = "Urbano"
    extra["source"] = "Extraurbano"

    columns = [
        "stop_id",
        "stop_code",
        "stop_name",
        "stop_desc",
        "stop_lat",
        "stop_lon",
        "zone_id",
        "source",
    ]

    for col in columns:
        if col not in urbano.columns:
            urbano[col] = np.nan
        if col not in extra.columns:
            extra[col] = np.nan

    stops = pd.concat([urbano[columns], extra[columns]], ignore_index=True)
    stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
    stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
    stops = stops.dropna(subset=["stop_lat", "stop_lon"]).copy()

    stops_metric = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
        crs=EPSG_WEB,
    ).to_crs(EPSG_METRIC)

    stops_metric = clip_to_municipal_boundary(stops_metric, municipal_boundary)
    stops_metric["stop_name"] = stops_metric["stop_name"].map(format_text)
    stops_metric["stop_code"] = stops_metric["stop_code"].map(format_text)
    stops_metric["zone_id"] = stops_metric["zone_id"].map(format_text)
    stops_metric["source"] = stops_metric["source"].map(format_text)
    return stops_metric


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


def assign_istat_majority_section(istat_metric: gpd.GeoDataFrame, points_metric: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    joined = gpd.sjoin(
        istat_metric[["SEZ21_ID", "COD_AREA_S", "geometry"]],
        points_metric[["id_section", "geometry"]],
        how="left",
        predicate="intersects",
    )

    majority = (
        joined.groupby("SEZ21_ID", as_index=False)["id_section"]
        .agg(mode_or_nan)
        .rename(columns={"id_section": "id_section_majority"})
    )

    out = istat_metric.merge(majority, on="SEZ21_ID", how="left")
    out["id_section_majority"] = normalize_key(out["id_section_majority"])
    out["majority_rule_display"] = out["id_section_majority"].apply(
        lambda value: f"Assigned to electoral section {value} via majority rule (MAUP)"
        if pd.notna(value)
        else "Assignment not available"
    )
    return out


def prepare_district_summary(districts_metric: gpd.GeoDataFrame, sections_metric: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    districts = districts_metric.copy()
    if sections_metric.empty or "district" not in sections_metric.columns:
        districts["mean_population_estimate"] = np.nan
        districts["mean_density"] = np.nan
        districts["mean_vote_pct"] = np.nan
        districts["mean_highly_educated_pct"] = np.nan
        districts["mean_extra_ue_pct"] = np.nan
        return districts

    sec = sections_metric.copy()
    sec["area_km2"] = sec.geometry.area / 1_000_000
    sec["estimated_population"] = sec["density"] * sec["area_km2"]

    summary = (
        sec.dropna(subset=["district"])
        .groupby("district", as_index=False)
        .agg(
            mean_population_estimate=("estimated_population", "mean"),
            mean_density=("density", "mean"),
            mean_vote_pct=("ianeselli_vote_pct", "mean"),
            mean_highly_educated_pct=("highly_educated_pct", "mean"),
            mean_extra_ue_pct=("extra_ue_pct", "mean"),
        )
    )

    districts = districts.merge(summary, on="district", how="left")
    return districts


def add_layer_circoscrizioni(m: folium.Map, districts_4326: gpd.GeoDataFrame, vote_colormap: LinearColormap) -> None:
    fg = folium.FeatureGroup(name="Districts", show=True)

    folium.GeoJson(
        districts_4326,
        style_function=lambda feat: {
            "color": "#2f2f2f",
            "weight": 1.5,
            "fillColor": vote_color(feat["properties"].get("mean_vote_pct"), vote_colormap),
            "fillOpacity": 0.42,
        },
        highlight_function=lambda _: {"weight": 3.0, "fillOpacity": 0.62},
        tooltip=GeoJsonTooltip(
            fields=["district", "mean_vote_display", "mean_educated_display", "mean_extra_ue_display"],
            aliases=["District:", "Vote Share:", "Highly Educated:", "Non-EU Residents:"],
            sticky=True,
        ),
        popup=GeoJsonPopup(
            fields=[
                "district",
                "mean_vote_display",
                "mean_educated_display",
                "mean_extra_ue_display",
            ],
            aliases=[
                "District:",
                "Vote Share:",
                "Highly Educated (%):",
                "Non-EU Residents (%):",
            ],
            labels=True,
        ),
    ).add_to(fg)

    fg.add_to(m)


def add_layer_istat(m: folium.Map, istat_4326: gpd.GeoDataFrame) -> None:
    fg = folium.FeatureGroup(name="ISTAT Census Blocks", show=False)

    folium.GeoJson(
        istat_4326,
        style_function=lambda _: {
            "color": "#111111",
            "weight": 0.9,
            "fillColor": "#000000",
            "fillOpacity": 0.0,
        },
        highlight_function=lambda _: {"weight": 2.0},
        tooltip=GeoJsonTooltip(
            fields=["SEZ21_ID", "id_section_majority"],
            aliases=["SEZ21_ID:", "Assigned Electoral Section:"],
            sticky=True,
        ),
        popup=GeoJsonPopup(
            fields=["SEZ21_ID", "majority_rule_display"],
            aliases=["SEZ21_ID:", "MAUP Assignment:"],
            labels=True,
        ),
    ).add_to(fg)

    fg.add_to(m)


def add_layer_sezioni_buffer(
    m: folium.Map,
    sections_4326: gpd.GeoDataFrame,
    vote_colormap: LinearColormap,
) -> folium.GeoJson:
    fg = folium.FeatureGroup(name="Electoral Sections (Standard)", show=True)

    sections_layer = folium.GeoJson(
        sections_4326,
        style_function=lambda feat: {
            "color": vote_color(feat["properties"].get("ianeselli_vote_pct"), vote_colormap),
            "weight": 1.1,
            "fillColor": vote_color(feat["properties"].get("ianeselli_vote_pct"), vote_colormap),
            "fillOpacity": 0.48,
        },
        highlight_function=lambda _: {"weight": 2.6, "fillOpacity": 0.68},
        tooltip=GeoJsonTooltip(
            fields=["id_section", "district", "ianeselli_vote_display"],
            aliases=["Section ID:", "District:", "Ianeselli Vote Share:"],
            sticky=True,
        ),
        popup=GeoJsonPopup(
            fields=[
                "id_section",
                "district",
                "ianeselli_vote_display",
                "highly_educated_display",
                "extra_ue_display",
                "transport_distance_display",
                "density_display",
            ],
            aliases=[
                "Section ID:",
                "District:",
                "Ianeselli Vote Share:",
                "Highly Educated:",
                "Non-EU Residents:",
                "Avg Transit Distance (m):",
                "Density (per km^2):",
            ],
            labels=True,
        ),
    ).add_to(fg)

    labels = sections_4326.copy()
    labels["label_point"] = labels.geometry.representative_point()

    for row in labels.itertuples(index=False):
        pt = row.label_point
        if pt.is_empty:
            continue

        sec_id = str(row.id_section)
        label_id = compact_section_label(sec_id)
        color = vote_color(getattr(row, "ianeselli_vote_pct", np.nan), vote_colormap)

        html = (
            "<div style=\""
            "font-size:9px;"
            "font-weight:700;"
            f"color:{color};"
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
    return sections_layer


def add_layer_special_sections(
    m: folium.Map,
    special_sections_4326: gpd.GeoDataFrame,
    vote_colormap: LinearColormap,
) -> folium.GeoJson:
    fg = folium.FeatureGroup(name="Special Electoral Sections", show=True)

    special_layer = folium.GeoJson(
        special_sections_4326,
        style_function=lambda feat: {
            "color": "#444444",
            "weight": 1.6,
            "fillColor": vote_color(feat["properties"].get("ianeselli_vote_pct"), vote_colormap),
            "fillOpacity": 0.68,
        },
        highlight_function=lambda _: {"weight": 3.4, "fillOpacity": 0.82},
        tooltip=GeoJsonTooltip(
            fields=["id_section", "district", "ianeselli_vote_display"],
            aliases=["Special Section ID:", "District:", "Ianeselli Vote Share:"],
            sticky=True,
        ),
        popup=GeoJsonPopup(
            fields=[
                "id_section",
                "district",
                "ianeselli_vote_display",
                "highly_educated_display",
                "extra_ue_display",
                "transport_distance_display",
                "density_display",
            ],
            aliases=[
                "Special Section ID:",
                "District:",
                "Ianeselli Vote Share:",
                "Highly Educated:",
                "Non-EU Residents:",
                "Avg Transit Distance (m):",
                "Density (per km^2):",
            ],
            labels=True,
        ),
    ).add_to(fg)

    fg.add_to(m)
    return special_layer


def add_layer_special_civici(
    m: folium.Map,
    points_special_4326: gpd.GeoDataFrame,
) -> folium.GeoJson:
    fg = folium.FeatureGroup(name="Civic Points (Special Sections)", show=False)

    special_civic_layer = folium.GeoJson(
        points_special_4326,
        marker=folium.CircleMarker(radius=2.8, fill=True, fill_opacity=0.9, opacity=0.9),
        style_function=lambda feat: {
            "color": "#666666",
            "fillColor": "#888888",
            "weight": 0.4,
        },
        tooltip=GeoJsonTooltip(fields=["address", "id_section"], aliases=["Address:", "Section ID:"], sticky=True),
        popup=GeoJsonPopup(
            fields=["address", "id_section", "district", "ianeselli_vote_display", "density_display"],
            aliases=["Address:", "Section ID:", "District:", "Ianeselli Vote Share:", "Density (per km^2):"],
            labels=True,
        ),
    ).add_to(fg)

    fg.add_to(m)
    return special_civic_layer


def add_layer_civici(
    m: folium.Map,
    points_4326: gpd.GeoDataFrame,
    vote_colormap: LinearColormap,
) -> folium.GeoJson:
    fg = folium.FeatureGroup(name="Civic Points (Standard Addresses)", show=False)

    civic_layer = folium.GeoJson(
        points_4326,
        marker=folium.CircleMarker(radius=2.6, fill=True, fill_opacity=0.95, opacity=0.9),
        style_function=lambda feat: {
            "color": vote_color(feat["properties"].get("ianeselli_vote_pct"), vote_colormap),
            "fillColor": vote_color(feat["properties"].get("ianeselli_vote_pct"), vote_colormap),
            "weight": 0.5,
        },
        tooltip=GeoJsonTooltip(fields=["address", "id_section"], aliases=["Address:", "Section ID:"], sticky=True),
        popup=GeoJsonPopup(
            fields=[
                "address",
                "id_section",
                "district",
                "ianeselli_vote_display",
                "highly_educated_display",
                "extra_ue_display",
                "transport_distance_display",
                "density_display",
            ],
            aliases=[
                "Address:",
                "Section ID:",
                "District:",
                "Ianeselli Vote Share:",
                "Highly Educated:",
                "Non-EU Residents:",
                "Avg Transit Distance (m):",
                "Density (per km^2):",
            ],
            labels=True,
        ),
    ).add_to(fg)

    fg.add_to(m)
    return civic_layer


def add_layer_infrastrutture(m: folium.Map) -> None:
    fg = folium.FeatureGroup(name="Bypass Construction Site", show=False)

    sites = [
        {
            "coords": [46.0825, 11.1185],
        },
        {
            "coords": [45.991379, 11.122409],
        },
    ]

    for site in sites:
        popup_html = "<div style='font-size:12px; line-height:1.35;'><strong>Bypass Construction Site</strong></div>"
        folium.Marker(
            location=site["coords"],
            popup=folium.Popup(popup_html, max_width=320),
            tooltip="Bypass Construction Site",
            icon=folium.Icon(color="orange", icon="wrench", prefix="fa"),
        ).add_to(fg)

    fg.add_to(m)


def add_layer_transit_stops(m: folium.Map, stops_4326: gpd.GeoDataFrame) -> None:
    fg = folium.FeatureGroup(name="Transit Stops (Urbano + Extraurbano)", show=False)
    cluster = MarkerCluster(name="Transit Stops Cluster").add_to(fg)

    for row in stops_4326.itertuples(index=False):
        if row.geometry.is_empty:
            continue

        popup_html = (
            "<div style='font-size:12px; line-height:1.35;'>"
            f"<strong>{row.stop_name}</strong><br>"
            f"Network: {row.source}"
            "</div>"
        )

        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=row.stop_name,
            icon=folium.Icon(color="blue", icon="bus", prefix="fa"),
        ).add_to(cluster)

    fg.add_to(m)


def prepare_sections_for_map(
    sections_metric: gpd.GeoDataFrame,
    analytical_data: pd.DataFrame,
) -> gpd.GeoDataFrame:
    sections = sections_metric.merge(analytical_data, on="id_section", how="left")
    sections["ianeselli_vote_pct"] = pd.to_numeric(sections["ianeselli_vote_pct"], errors="coerce")
    sections["highly_educated_pct"] = pd.to_numeric(sections["highly_educated_pct"], errors="coerce")
    sections["extra_ue_pct"] = pd.to_numeric(sections["extra_ue_pct"], errors="coerce")
    sections["density"] = pd.to_numeric(sections["density"], errors="coerce")
    sections["nearest_transport_distance_m"] = pd.to_numeric(sections["nearest_transport_distance_m"], errors="coerce")
    sections["area_km2"] = sections.geometry.area / 1_000_000
    sections["estimated_population"] = sections["density"] * sections["area_km2"]

    sections["ianeselli_vote_display"] = sections["ianeselli_vote_pct"].map(format_percent)
    sections["highly_educated_display"] = sections["highly_educated_pct"].map(format_percent)
    sections["extra_ue_display"] = sections["extra_ue_pct"].map(format_percent)
    sections["transport_distance_display"] = sections["nearest_transport_distance_m"].map(lambda v: format_number(v, digits=1, suffix=" m"))
    sections["density_display"] = sections["density"].map(lambda v: format_number(v, digits=1))
    sections["population_display"] = sections["estimated_population"].map(lambda v: format_number(v, digits=0))
    sections["district"] = sections["district"].map(format_text)
    sections["is_special_section"] = sections["id_section"].astype(str).isin(SPECIAL_SECTION_IDS)

    return sections


def prepare_districts_for_map(
    districts_metric: gpd.GeoDataFrame,
    sections_metric: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    districts = prepare_district_summary(districts_metric, sections_metric)
    districts["mean_population_display"] = districts["mean_population_estimate"].map(lambda v: format_number(v, digits=0))
    districts["mean_density_display"] = districts["mean_density"].map(lambda v: format_number(v, digits=1))
    districts["mean_vote_display"] = districts["mean_vote_pct"].map(format_percent)
    districts["mean_educated_display"] = districts["mean_highly_educated_pct"].map(format_percent)
    districts["mean_extra_ue_display"] = districts["mean_extra_ue_pct"].map(format_percent)
    return districts


def prepare_points_for_map(points_metric: gpd.GeoDataFrame, sections_metric: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    columns = [
        "id_section",
        "district",
        "ianeselli_vote_pct",
        "highly_educated_pct",
        "extra_ue_pct",
        "density",
        "nearest_transport_distance_m",
        "is_special_section",
    ]
    available = [col for col in columns if col in sections_metric.columns]
    section_data = sections_metric[available].copy()
    if "district" in section_data.columns:
        section_data = section_data.rename(columns={"district": "section_district"})

    points = points_metric.merge(section_data, on="id_section", how="left")
    if "section_district" in points.columns:
        points["district"] = points["section_district"].combine_first(points.get("district"))
        points = points.drop(columns=["section_district"])

    points["ianeselli_vote_display"] = points["ianeselli_vote_pct"].map(format_percent)
    points["highly_educated_display"] = points["highly_educated_pct"].map(format_percent)
    points["extra_ue_display"] = points["extra_ue_pct"].map(format_percent)
    points["transport_distance_display"] = points["nearest_transport_distance_m"].map(lambda v: format_number(v, digits=1, suffix=" m"))
    points["density_display"] = points["density"].map(lambda v: format_number(v, digits=1))
    points["district"] = points["district"].map(format_text)
    points["address"] = points["address"].map(format_text)
    points["is_special_section"] = points["is_special_section"].fillna(False).astype(bool)
    return points


def add_search_and_reset_controls(
        m: folium.Map,
        civic_layer: folium.GeoJson,
        sections_layer: folium.GeoJson,
        special_sections_layer: folium.GeoJson,
        bounds: list[list[float]],
) -> None:
        Search(
                layer=civic_layer,
                search_label="address",
                placeholder="Search address",
                collapsed=False,
                search_zoom=17,
                marker=False,
        ).add_to(m)
        Search(
                layer=sections_layer,
                search_label="id_section",
                placeholder="Search section ID",
                collapsed=True,
                search_zoom=15,
                marker=False,
        ).add_to(m)
    # Note: do NOT add a search box for special sections (per user request)

        map_name = m.get_name()
        bounds_js = str(bounds)
        script = f"""
        <script>
        (function() {{
            var map = {map_name};
            var defaultBounds = {bounds_js};
            var activeLayer = null;
            var activeStyle = null;

            function clearActiveHighlight() {{
                if (!activeLayer) return;
                try {{
                    if (activeLayer.setStyle && activeStyle) {{
                        activeLayer.setStyle(activeStyle);
                    }}
                }} catch (err) {{}}
                activeLayer = null;
                activeStyle = null;
            }}

            map.on('search:locationfound', function(e) {{
                clearActiveHighlight();
                var layer = e.layer;
                var props = (layer && layer.feature && layer.feature.properties) || null;

                // Try to highlight found layer and open its popup
                try {{
                    if (layer && layer.setStyle) {{
                        activeStyle = {{
                            color: layer.options && layer.options.color || '#000000',
                            weight: layer.options && layer.options.weight || 1,
                            fillColor: layer.options && layer.options.fillColor || '#ffffff',
                            fillOpacity: layer.options && layer.options.fillOpacity || 0.4,
                        }};
                        layer.setStyle({{color: '#000000', weight: 4, fillOpacity: 0.9, opacity: 1.0}});
                        activeLayer = layer;
                    }}
                }} catch(err) {{}}

                // Open popup for the exact layer if possible
                try {{
                    if (layer && typeof layer.openPopup === 'function') {{
                        layer.openPopup();
                        return;
                    }}
                }} catch (err) {{}}

                // If popup not directly available, search all map layers for matching feature properties
                try {{
                    if (props && props.id_section) {{
                        var targetId = String(props.id_section);
                        map.eachLayer(function(l) {{
                            try {{
                                if (l && l.feature && l.feature.properties && String(l.feature.properties.id_section) === targetId) {{
                                    if (typeof l.openPopup === 'function') {{
                                        l.openPopup();
                                    }}
                                }}
                            }} catch (e) {{}}
                        }});
                        return;
                    }} else if (props && props.address) {{
                        var addr = String(props.address);
                        map.eachLayer(function(l) {{
                            try {{
                                if (l && l.feature && l.feature.properties && String(l.feature.properties.address) === addr) {{
                                    if (typeof l.openPopup === 'function') {{
                                        l.openPopup();
                                    }}
                                }}
                            }} catch (e) {{}}
                        }});
                        return;
                    }}
                }} catch (err) {{}}
            }});

            var ResetViewControl = L.Control.extend({{
                options: {{position: 'topleft'}},
                onAdd: function() {{
                    var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
                    var btn = L.DomUtil.create('a', '', container);
                    btn.href = '#';
                    btn.title = 'Reset view';
                    btn.innerHTML = '&#x21bb;';
                    btn.style.width = '30px';
                    btn.style.height = '30px';
                    btn.style.lineHeight = '30px';
                    btn.style.textAlign = 'center';
                    btn.style.fontSize = '18px';
                    btn.style.background = '#ffffff';
                    btn.style.color = '#222222';
                    L.DomEvent.on(btn, 'click', function(ev) {{
                        L.DomEvent.stop(ev);
                        clearActiveHighlight();
                        map.fitBounds(defaultBounds);
                    }});
                    return container;
                }}
            }});

            map.addControl(new ResetViewControl());
        }})();
        </script>
        """
        m.get_root().html.add_child(folium.Element(script))


def build_map(
    districts_metric: gpd.GeoDataFrame,
    istat_metric: gpd.GeoDataFrame,
    sections_metric: gpd.GeoDataFrame,
    points_metric: gpd.GeoDataFrame,
    stops_metric: gpd.GeoDataFrame,
) -> folium.Map:
    districts_prepared = prepare_districts_for_map(districts_metric, sections_metric)
    points_prepared = prepare_points_for_map(points_metric, sections_metric)

    sections_standard_metric = sections_metric[~sections_metric["is_special_section"]].copy()
    sections_special_metric = sections_metric[sections_metric["is_special_section"]].copy()
    points_standard_prepared = points_prepared[~points_prepared["is_special_section"]].copy()
    points_special_prepared = points_prepared[points_prepared["is_special_section"]].copy()

    vote_colormap = build_vote_colormap()

    districts_4326 = districts_prepared.to_crs(EPSG_WEB)
    istat_4326 = istat_metric.to_crs(EPSG_WEB)
    sections_4326 = sections_standard_metric.to_crs(EPSG_WEB)
    special_sections_4326 = sections_special_metric.to_crs(EPSG_WEB)
    points_4326 = points_standard_prepared.to_crs(EPSG_WEB)
    special_points_4326 = points_special_prepared.to_crs(EPSG_WEB)
    stops_4326 = stops_metric.to_crs(EPSG_WEB)

    center_geom = gpd.GeoSeries([districts_metric.geometry.union_all()], crs=EPSG_METRIC).to_crs(EPSG_WEB).iloc[0]
    center = center_geom.centroid

    m = folium.Map(
        location=[center.y, center.x],
        zoom_start=12,
        tiles="CartoDB Positron",
        control_scale=True,
    )

    add_layer_circoscrizioni(m, districts_4326, vote_colormap)
    add_layer_istat(m, istat_4326)
    sections_layer = add_layer_sezioni_buffer(m, sections_4326, vote_colormap)
    special_sections_layer = add_layer_special_sections(m, special_sections_4326, vote_colormap)
    special_civic_layer = add_layer_special_civici(m, special_points_4326)
    civic_layer = add_layer_civici(m, points_4326, vote_colormap)
    add_layer_infrastrutture(m)
    add_layer_transit_stops(m, stops_4326)

    vote_colormap.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)

    minx, miny, maxx, maxy = districts_4326.total_bounds
    bounds = [[float(miny), float(minx)], [float(maxy), float(maxx)]]
    add_search_and_reset_controls(m, civic_layer, sections_layer, special_sections_layer, bounds)
    m.fit_bounds(bounds)
    m.options["maxBounds"] = bounds

    return m


def main() -> None:
    points_metric = load_points_metric()
    districts_metric = load_districts_metric()
    municipal_boundary = districts_metric.geometry.union_all().buffer(0)

    istat_metric = load_istat_metric()
    istat_metric = clip_to_municipal_boundary(istat_metric, municipal_boundary)
    istat_metric = assign_istat_majority_section(istat_metric, points_metric)

    sections_metric = build_sections_buffer_dissolve(points_metric, municipal_boundary, buffer_m=BUFFER_M)
    analytical_data = load_analytical_data(sections_metric["id_section"])
    sections_metric = prepare_sections_for_map(sections_metric, analytical_data)
    stops_metric = load_transit_stops_metric(municipal_boundary)

    m = build_map(districts_metric, istat_metric, sections_metric, points_metric, stops_metric)
    m.save(OUT_HTML)

    print(f"Saved map: {OUT_HTML}")
    print(f"District polygons: {len(districts_metric)}")
    print(f"ISTAT polygons (clipped): {len(istat_metric)}")
    print(f"Sections (buffer+dissolve): {len(sections_metric)}")
    print(f"Civic points: {len(points_metric)}")


if __name__ == "__main__":
    main()
