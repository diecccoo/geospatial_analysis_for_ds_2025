from __future__ import annotations

from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

import geopandas as gpd
import numpy as np
import pandas as pd


# -----------------------------
# Paths and constants
# -----------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

ISTAT_SHP = RAW / "R04_21_WGS84.shp"
ISTAT_CSV = RAW / "R04_indicatori_2021_sezioni.csv"
ISTAT_XLSX = RAW / "R04_indicatori_2021_sezioni.xlsx"
POINTS_GEOJSON = RAW / "sections.geojson"  # 25k address points with id_section
VOTES_CSV = RAW / "Voti_Sindaco.csv"
STOPS_URBANO = RAW / "stops_urbano.txt"
STOPS_EXTRA = RAW / "stops_extraurbano.txt"

OUT_GEOJSON = PROCESSED / "trento_elections_model_ready.geojson"

EPSG_METRIC = 32632
EPSG_OUT = 4326
TRENTO_PROCOM = "22205"
IANESELLI_SURNAME = "ianeselli"


# -----------------------------
# Utility helpers
# -----------------------------
def normalize_key(series: pd.Series) -> pd.Series:
    """Normalize join keys as clean strings."""
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\\.0$", "", regex=True)
        .replace({"nan": np.nan, "None": np.nan, "": np.nan})
    )


def find_col(df: pd.DataFrame, candidates: list[str], required: bool = True) -> str | None:
    """Find the first matching column name among candidate aliases (case-insensitive)."""
    low = {c.lower(): c for c in df.columns}
    for cand in candidates:
        c = low.get(cand.lower())
        if c is not None:
            return c
    if required:
        raise KeyError(f"None of {candidates} found in columns: {list(df.columns)}")
    return None


def _excel_col_to_idx(cell_ref: str) -> int:
    m = re.match(r"([A-Za-z]+)", str(cell_ref))
    if not m:
        return -1
    letters = m.group(1).upper()
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def read_xlsx_first_sheet_without_openpyxl(path: Path) -> pd.DataFrame:
    """
    Lightweight xlsx reader (first sheet) that avoids openpyxl dependency.
    Used only as fallback.
    """
    ns_main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    ns_rel_doc = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    ns_rel_pkg = "http://schemas.openxmlformats.org/package/2006/relationships"

    with zipfile.ZipFile(path, "r") as zf:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        sheets = wb.find(f"{{{ns_main}}}sheets")
        first_sheet = sheets.find(f"{{{ns_main}}}sheet")
        rid = first_sheet.attrib[f"{{{ns_rel_doc}}}id"]

        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        target = None
        for rel in rels.findall(f"{{{ns_rel_pkg}}}Relationship"):
            if rel.attrib.get("Id") == rid:
                target = "xl/" + rel.attrib["Target"].lstrip("/")
                break
        if target is None:
            raise RuntimeError("Could not resolve first worksheet target.")

        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst.findall(f"{{{ns_main}}}si"):
                txt = "".join(t.text or "" for t in si.iter(f"{{{ns_main}}}t"))
                shared.append(txt)

        sheet = ET.fromstring(zf.read(target))
        sheet_data = sheet.find(f".//{{{ns_main}}}sheetData")

        rows = []
        max_col = -1
        for row in sheet_data.findall(f"{{{ns_main}}}row"):
            vals: dict[int, object] = {}
            for c in row.findall(f"{{{ns_main}}}c"):
                col_idx = _excel_col_to_idx(c.attrib.get("r", ""))
                if col_idx < 0:
                    continue
                max_col = max(max_col, col_idx)
                t = c.attrib.get("t")

                if t == "inlineStr":
                    is_el = c.find(f"{{{ns_main}}}is")
                    txt = "" if is_el is None else "".join(x.text or "" for x in is_el.iter(f"{{{ns_main}}}t"))
                    vals[col_idx] = txt
                    continue

                v = c.find(f"{{{ns_main}}}v")
                if v is None:
                    vals[col_idx] = ""
                elif t == "s":
                    vals[col_idx] = shared[int(v.text)]
                else:
                    vals[col_idx] = v.text

            if vals:
                row_list = [""] * (max_col + 1)
                for i, val in vals.items():
                    row_list[i] = val
                rows.append(row_list)

    if not rows:
        raise RuntimeError("No rows found in first worksheet.")

    header = [str(x).strip() for x in rows[0]]
    data = rows[1:]
    fixed = []
    for r in data:
        if len(r) < len(header):
            r = r + [""] * (len(header) - len(r))
        elif len(r) > len(header):
            r = r[: len(header)]
        fixed.append(r)

    return pd.DataFrame(fixed, columns=header)


def mode_or_nan(series: pd.Series) -> object:
    """Deterministic mode: highest frequency, then smallest key as tie-break."""
    s = series.dropna().astype(str)
    if s.empty:
        return np.nan
    counts = s.value_counts()
    max_count = counts.max()
    winners = sorted(counts[counts == max_count].index.tolist())
    return winners[0]


# -----------------------------
# Data loading / feature steps
# -----------------------------
def load_istat_tabular_trento() -> pd.DataFrame:
    """Load ISTAT indicators, filter Trento, keep SEZ21_ID, P1, P90, ST19."""
    if ISTAT_CSV.exists():
        tab = pd.read_csv(ISTAT_CSV)
    elif ISTAT_XLSX.exists():
        try:
            tab = pd.read_excel(ISTAT_XLSX, sheet_name=0)
        except ImportError:
            tab = read_xlsx_first_sheet_without_openpyxl(ISTAT_XLSX)
    else:
        raise FileNotFoundError("Neither ISTAT csv nor xlsx found in data/raw.")

    procom_col = find_col(tab, ["PROCOM", "CODCOM"])
    comune_col = find_col(tab, ["COMUNE"], required=False)
    sez_col = find_col(tab, ["SEZ21_ID", "SEZ21"])
    p1_col = find_col(tab, ["P1"])
    p90_col = find_col(tab, ["P90"])
    st19_col = find_col(tab, ["ST19"])

    procom_norm = normalize_key(tab[procom_col])
    mask = procom_norm == TRENTO_PROCOM
    if comune_col is not None:
        mask = mask | tab[comune_col].astype(str).str.contains("trento", case=False, na=False)

    out = tab.loc[mask, [sez_col, p1_col, p90_col, st19_col]].copy()
    out.columns = ["SEZ21_ID", "P1", "P90", "ST19"]
    out["SEZ21_ID"] = normalize_key(out["SEZ21_ID"])
    out["P1"] = pd.to_numeric(out["P1"], errors="coerce").fillna(0)
    out["P90"] = pd.to_numeric(out["P90"], errors="coerce").fillna(0)
    out["ST19"] = pd.to_numeric(out["ST19"], errors="coerce").fillna(0)
    return out


def build_istat_gdf() -> gpd.GeoDataFrame:
    """Create ISTAT polygon layer enriched with P1, P90, and ST19 for Trento."""
    tab = load_istat_tabular_trento()
    shp = gpd.read_file(ISTAT_SHP).to_crs(EPSG_METRIC)

    shp_sez_col = find_col(shp, ["SEZ21_ID", "SEZ21"])
    shp = shp.copy()
    shp["SEZ21_ID"] = normalize_key(shp[shp_sez_col])

    istat_gdf = shp.merge(tab, on="SEZ21_ID", how="inner")
    istat_gdf = istat_gdf.loc[istat_gdf["P1"] > 0].copy()
    return istat_gdf


def load_address_points() -> gpd.GeoDataFrame:
    """Load 25k address points with id_section and project to metric CRS."""
    pts = gpd.read_file(POINTS_GEOJSON).to_crs(EPSG_METRIC)
    sec_col = find_col(pts, ["id_section", "ID_SECTION", "section_id"])
    pts = pts.copy()
    pts["id_section"] = normalize_key(pts[sec_col])
    return pts[["id_section", "geometry"]].copy()


def reconstruct_section_polygons(istat_gdf: gpd.GeoDataFrame, address_points: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    1) Spatial join ISTAT polygons with address points.
    2) For each SEZ21_ID, assign the most frequent (mode) electoral id_section.
    3) Dissolve ISTAT polygons by winning id_section to reconstruct electoral polygons.
    """
    joined = gpd.sjoin(
        istat_gdf[["SEZ21_ID", "P1", "P90", "ST19", "geometry"]],
        address_points[["id_section", "geometry"]],
        how="left",
        predicate="intersects",
    )

    block_to_section = (
        joined.groupby("SEZ21_ID", as_index=False)["id_section"]
        .apply(mode_or_nan)
        .rename(columns={None: "id_section"})
    )

    if "id_section" not in block_to_section.columns:
        val_col = [c for c in block_to_section.columns if c != "SEZ21_ID"][0]
        block_to_section = block_to_section.rename(columns={val_col: "id_section"})

    assigned = istat_gdf.merge(block_to_section, on="SEZ21_ID", how="left")
    assigned = assigned.dropna(subset=["id_section"]).copy()

    sections_poly = assigned.dissolve(by="id_section", as_index=False, aggfunc={"P1": "sum", "P90": "sum", "ST19": "sum"})
    sections_poly = gpd.GeoDataFrame(sections_poly, geometry="geometry", crs=istat_gdf.crs)
    sections_poly["id_section"] = normalize_key(sections_poly["id_section"])
    return sections_poly


def aggregate_votes() -> pd.DataFrame:
    votes = pd.read_csv(VOTES_CSV, sep=";")
    sec_col = find_col(votes, ["Sezione"])
    cog_col = find_col(votes, ["Cognome"])
    v_col = find_col(votes, ["Voti"])

    votes = votes.copy()
    votes["id_section"] = normalize_key(votes[sec_col])
    votes[v_col] = pd.to_numeric(votes[v_col], errors="coerce").fillna(0)

    total_votes = votes.groupby("id_section", dropna=False)[v_col].sum().rename("total_votes")
    ianeselli_votes = (
        votes.loc[votes[cog_col].astype(str).str.contains(IANESELLI_SURNAME, case=False, na=False)]
        .groupby("id_section", dropna=False)[v_col]
        .sum()
        .rename("ianeselli_votes")
    )

    out = pd.concat([total_votes, ianeselli_votes], axis=1).fillna(0).reset_index()
    out["ianeselli_vote_pct"] = np.where(
        out["total_votes"] > 0,
        out["ianeselli_votes"] / out["total_votes"] * 100,
        np.nan,
    )
    return out


def load_stops_metric() -> gpd.GeoDataFrame:
    s1 = pd.read_csv(STOPS_URBANO)
    s2 = pd.read_csv(STOPS_EXTRA)
    stops = pd.concat([s1, s2], ignore_index=True)

    lat_col = find_col(stops, ["stop_lat", "lat", "latitude"])
    lon_col = find_col(stops, ["stop_lon", "lon", "longitude"])

    stops = stops.copy()
    stops[lat_col] = pd.to_numeric(stops[lat_col], errors="coerce")
    stops[lon_col] = pd.to_numeric(stops[lon_col], errors="coerce")
    stops = stops.dropna(subset=[lat_col, lon_col]).copy()

    gdf = gpd.GeoDataFrame(stops, geometry=gpd.points_from_xy(stops[lon_col], stops[lat_col]), crs=4326)
    return gdf.to_crs(EPSG_METRIC)


def compute_section_avg_transit_distance_from_points(
    address_points: gpd.GeoDataFrame,
    stops_metric: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """
    Compute section-level average nearest transit distance from individual address points.
    Distances are Euclidean meters in EPSG:32632.
    """
    pts_metric = address_points.to_crs(EPSG_METRIC) if address_points.crs != EPSG_METRIC else address_points
    stops_metric = stops_metric.to_crs(EPSG_METRIC) if stops_metric.crs != EPSG_METRIC else stops_metric

    pts_nearest = gpd.sjoin_nearest(
        pts_metric[["id_section", "geometry"]],
        stops_metric[["geometry"]],
        how="left",
        distance_col="pt_transit_dist_m",
    )

    avg_transit_dist = (
        pts_nearest.groupby("id_section", as_index=False)["pt_transit_dist_m"]
        .mean()
        .rename(columns={"pt_transit_dist_m": "nearest_transport_distance_m"})
    )
    avg_transit_dist["id_section"] = normalize_key(avg_transit_dist["id_section"])
    return avg_transit_dist


# -----------------------------
# Main pipeline
# -----------------------------
def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)

    # 1) Building blocks: ISTAT polygons + indicators
    istat_gdf = build_istat_gdf()

    # 2) Voter points
    address_points = load_address_points()

    # 3-4-5) Spatial join + mode assignment + dissolve to reconstructed section polygons
    sections_gdf = reconstruct_section_polygons(istat_gdf, address_points)

    # 6) Merge votes
    votes_df = aggregate_votes()
    sections_gdf = sections_gdf.merge(votes_df, on="id_section", how="left")

    # Optional district label from points (most frequent district name per id_section)
    points_full = gpd.read_file(POINTS_GEOJSON)
    district_col = find_col(points_full, ["district", "DISTRICT"], required=False)
    if district_col is not None:
        points_full = points_full.copy()
        sec_col = find_col(points_full, ["id_section", "ID_SECTION", "section_id"])
        points_full["id_section"] = normalize_key(points_full[sec_col])
        district_map = (
            points_full[["id_section", district_col]]
            .dropna(subset=["id_section"])
            .groupby("id_section", as_index=False)[district_col]
            .agg(lambda s: mode_or_nan(pd.Series(s)))
            .rename(columns={district_col: "district"})
        )
        sections_gdf = sections_gdf.merge(district_map, on="id_section", how="left")

    # 7) Indicators
    sections_gdf["area_km2"] = sections_gdf.geometry.area / 1_000_000
    sections_gdf["highly_educated_pct"] = np.where(
        sections_gdf["P1"] > 0,
        sections_gdf["P90"] / sections_gdf["P1"] * 100,
        np.nan,
    )
    sections_gdf["extra_ue_pct"] = np.where(
        sections_gdf["P1"] > 0,
        sections_gdf["ST19"] / sections_gdf["P1"] * 100,
        np.nan,
    )
    sections_gdf["density"] = np.where(
        sections_gdf["area_km2"] > 0,
        sections_gdf["P1"] / sections_gdf["area_km2"],
        np.nan,
    )

    stops_metric = load_stops_metric()
    avg_transit_dist = compute_section_avg_transit_distance_from_points(address_points, stops_metric)
    sections_gdf = sections_gdf.merge(avg_transit_dist, on="id_section", how="left")

    # 8) Final cleanup + export
    keep_cols = [
        "id_section",
        "district",
        "total_votes",
        "ianeselli_votes",
        "ianeselli_vote_pct",
        "highly_educated_pct",
        "extra_ue_pct",
        "density",
        "nearest_transport_distance_m",
        "geometry",
    ]
    keep_cols = [c for c in keep_cols if c in sections_gdf.columns]

    final = sections_gdf[keep_cols].copy()

    SEZIONI_SPECIALI = [
        "17", "19", "21", "22", "23", "26", "28", "29",
        "44", "46", "48/1", "48/2", "49", "51", "61", "62",
        "79", "91", "93",
    ]
    final = final.loc[~final["id_section"].isin(SEZIONI_SPECIALI)].copy()

    final = final.dropna(subset=["ianeselli_vote_pct", "highly_educated_pct", "density"])
    final = final.to_crs(EPSG_OUT)
    final.to_file(OUT_GEOJSON, driver="GeoJSON")

    print(f"Saved: {OUT_GEOJSON}")
    print(f"Rows: {len(final)}")
    print("Geometry types:", final.geom_type.value_counts().to_dict())
    print(f"Unique id_section: {final['id_section'].nunique()}")


if __name__ == "__main__":
    main()
