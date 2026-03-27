from __future__ import annotations

from pathlib import Path

import geopandas as gpd


def main() -> None:
    # Project paths
    project_root = Path(__file__).resolve().parents[1]
    input_geojson = project_root / "data" / "processed" / "trento_elections_model_ready.geojson"
    output_html = project_root / "data" / "processed" / "test_map_ianeselli.html"

    # 1) Load GeoJSON
    gdf = gpd.read_file(input_geojson)

    # 2) Quick geometry-type check
    geom_counts = gdf.geom_type.value_counts()
    print("Geometry type counts:")
    print(geom_counts.to_string())

    allowed = {"Polygon", "MultiPolygon"}
    found = set(geom_counts.index)
    if found.issubset(allowed):
        print("OK: all geometries are Polygon/MultiPolygon.")
    else:
        print("WARNING: non-polygon geometries detected.")
        print("Found:", sorted(found))

    # 3) Build interactive choropleth using GeoPandas explore()
    tooltip_fields = [
        "district",
        "id_section",
        "total_votes",
        "ianeselli_votes",
        "ianeselli_vote_pct",
        "highly_educated_pct",
        "density",
    ]

    # Keep only tooltip columns that actually exist to avoid runtime errors
    tooltip_fields = [c for c in tooltip_fields if c in gdf.columns]

    m = gdf.explore(
        column="ianeselli_vote_pct",
        cmap="OrRd",
        scheme="quantiles",
        legend=True,
        tooltip=tooltip_fields,
        popup=False,
        style_kwds={"weight": 0.8, "fillOpacity": 0.7},
    )

    # 4) Save interactive map as HTML
    output_html.parent.mkdir(parents=True, exist_ok=True)
    m.save(output_html)

    print(f"Saved interactive map to: {output_html}")


if __name__ == "__main__":
    main()
