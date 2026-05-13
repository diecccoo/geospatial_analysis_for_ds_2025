# Geospatial Analysis of Electoral Outcomes in Trento: The 2025 Ianeselli Case

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![R](https://img.shields.io/badge/R-4.2%2B-blue.svg)](https://www.r-project.org/)
[![Spatial Econometrics](https://img.shields.io/badge/Method-Spatial_Autoregressive_(SAR)-success.svg)]()
[![Course](https://img.shields.io/badge/Course-Data_Science_UniTN-critical.svg)]()

This repository contains the pipeline for the geospatial analysis and visualization of the May 2025 municipal election outcomes in Trento, Italy. Developed for the Data Science Master's degree at the University of Trento, the project investigates the spatial determinants and neighborhood-level spillovers driving support for the incumbent center-left mayor, Franco Ianeselli.

## 🔗 Live Interactive Map
[![Live Map](https://img.shields.io/badge/Demo-Live_Interactive_Map-blue?style=for-the-badge&logo=googlemaps)](https://diecccoo.github.io/trento_elections_geospatial_analysis_2025/data/processed/trento_electoral_map.html)

> **Check the interactive map in your browser here:** [trento_electoral_map.html](https://diecccoo.github.io/trento_elections_geospatial_analysis_2025/data/processed/trento_electoral_map.html)

## 🎯 Project Overview & Key Findings

Moving beyond traditional, spatially-blind ecological regressions, this study explicitly models spatial dependence across urban precincts. By fusing official electoral counts with granular ISTAT census data and open public transit (GTFS) feeds, the analytical framework highlights two core dynamics:

* **The Educational Spillover (Halo Effect):** Human capital (the share of highly educated residents) acts as the primary structural driver of progressive consensus, fostering a localized cultural climate that radiates across municipal boundaries.
* **Unmasking OLS Bias:** Standard linear models falsely identify proximity to public transit stops as a highly significant predictor. By implementing a **Spatial Autoregressive (SAR)** model, this effect completely vanishes, proving that transit distance merely acted as a spurious correlation capturing unobserved urban centrality.

---

## 📂 Repository Structure

```text
.
├── data/
│   ├── raw/                      # Original boundary files, GTFS feeds, and vote counts
│   └── processed/                # Engineered analytical datasets and output interactive map
│       ├── trento_elections.geojson
│       └── trento_electoral_map.html
│
├── scripts/                      # Python data engineering & interactive map builder
│   ├── build_trento_elections.py 
│   └── trento_electoral_map.py  
│
└── r_scripts/                    # R geospatial analysis & statistical modeling
    ├── 00_data_exploration.R     
    ├── 01_global_autocorrelation.R
    ├── 02_local_analysis.R       
    ├── 03_spatial_regression_models.R 
    └── r_plots/                  # R plots and LaTeX tables
```

## 🗺️ Interactive Web Map 

The core deliverable of this project is the interactive web map hosted at `data/processed/trento_electoral_map.html`. 

Designed as a complete **Electoral & Socio-Demographic Explorer**, the map allows users to dynamically navigate the spatial intersection between voting patterns, urban accessibility, and localized infrastructure grievances.

### 🗂️ Thematic Layers & Spatial Resolution
The map integrates multiple overlapping geographic layers that can be toggled independently via the top-right control panel:

1. **Districts (Circoscrizioni):** The macro-administrative boundaries. Displays aggregated district-level metrics to immediately visualize the broader center-periphery divide. Visibile by default.
2. **Electoral Sections (40m Buffer + Dissolve):** The primary analytical unit ($N=80$). Rather than relying on static or distorted boundaries, section polygons are dynamically reconstructed with topological fidelity by buffering and dissolving residential address points. This approach addresses both the lack of official Italian electoral precinct geometries and the topological inconsistencies of their irregular boundaries.
3. **Civic Points (Addresses):** Extremely granular point layer representing individual street numbers (*civici*). Useful for deep-dive local inspections.
4. **ISTAT Census Blocks:** Displays the underlying micro-census geometry. Illustrates how individual blocks were spatially assigned to electoral sections via majority rules (the **MAUP** resolution logic). Hidden by default.
5. **Bypass Construction Sites:** Custom infrastructural markers highlighting the high-impact excavation areas for the *Bypass Ferroviario* (Trento Nord and Mattarello), providing direct spatial context to the urban debate. Hidden by default.
6. **Public Transport Stops**: Urban and extraurban transit nodes. Allows users to inspect the distribution and density of the transport network across the municipality of Trento. Hidden by default.
7. **Special Electoral Precincts**: Highlights special, hospital, and military voting sections and their civic points. Toggleable layer to inspect the specific precincts excluded from the spatial analysis due to their non-residential or institutional nature.

### 🎨 Visual & Chromatic Logic
The visualization employs a diverging color palette (Red - White - Blue) mapped directly to the incumbent mayor's vote share (`ianeselli_vote_pct`):
* **The 50.0% Anchor:** The colormap midpoint is rigidly anchored at the **50.0%** absolute majority threshold (rendered as a neutral/white tone).
* **Direct Visual Decoding:** Precincts rendered in warm tones (red/orange) instantly signal areas where the candidate fell below the absolute majority, while cool tones (blue) denote comfortable victories. Contrast boundaries are optimized between **45.0% and 70.0%** to maximize legibility across competitive urban areas, since this is the range of votes between each of the 80 precints in the analysis fall.

### ⚡ Interactivity & User Experience
* **Dynamic Tooltips (Hover):** Passing the cursor over any active district or section instantly reveals its identifier, district name, and core vote share.
* **Deep-Dive Popups (Click):** Clicking on a section or civic address opens a table displaying the complete multivariate profile:
  * Official Section ID & District Name.
  * **Vote Share:** Franco Ianeselli's exact percentage.
  * **Human Capital:** Share of highly educated residents (University degree %).
  * **Demographics:** Concentration of non-EU residents and density of the area.
  * **Transit Centrality:** Average metric walking distance to the nearest public transport stop (derived from GTFS feeds).
* **Address Search Bar:** An integrated search plugin allows users to type specific street addresses or Section IDs to automatically zoom, pan, and highlight the targeted feature.

---

## 🛠️ Requirements & Setup

The project requires a Python environment to build the spatial datasets and render the HTML interface, while formal econometric modeling is maintained in R.

### Python Dependencies
Install the required packages using `requirements.txt`:
```bash
pip install -r requirements.txt
```


### R Environment
For the statistical pipeline (`r_scripts/`), ensure your R environment has the following libraries installed:

```r
install.packages(c("sf", "spdep", "spatialreg", "ggplot2", "tmap", "dplyr", "texreg"))
```

🚀 How to Run the Pipeline
To rebuild the spatial datasets and regenerate the map from scratch:

**Pre-process Data & Resolve MAUP:** Merges raw vote counts, reconstructs geometries, and calculates spatial distance matrices.

```bash
python scripts/build_trento_elections.py
```

**Render the Interactive Map:** Compiles the final styled HTML dashboard into `data/processed/`.

```bash
python scripts/trento_electoral_map.py
```
