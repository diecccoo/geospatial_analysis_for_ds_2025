# Load required packages
library(sf)
library(spdep)
library(tmap)

# 1. Read spatial data 
# Moving one level up from R_scripts/ to access data/processed/
setwd("C:/Users/MyPc/OneDrive/Documenti/Universita/Data Science/Geospatial/geospatial_analysis_for_ds_2025/r_scripts")
trento <- st_read("../data/processed/trento_elections_model_ready.geojson")

# Transform to a metric CRS (UTM Zone 32N) for accurate distance measurements
trento <- st_transform(trento, 32632) 

# 2. Run Ordinary Least Squares (OLS) model as baseline
OLS_model <- lm(ianeselli_vote_pct ~ highly_educated_pct + extra_ue_pct + 
                  density + nearest_transport_distance_m, data = trento)
summary(OLS_model)

# 3. Create Spatial Weights Matrix
# Compute centroids of polygons
coords <- st_centroid(st_geometry(trento))

# Option A: k-Nearest Neighbours (k=4)
knn4 <- knn2nb(knearneigh(coords, k=4))
knn4.listw <- nb2listw(knn4, style="W")

# Option B: Critical cut-off distance
# Find the minimum distance ensuring at least 1 neighbor for all units
knn1 <- knn2nb(knearneigh(coords, k=1))
min_dist <- max(unlist(nbdists(knn1, coords)))
cat("Minimum distance for at least 1 neighbor:", min_dist, "meters\n")

# To use cut-off, uncomment below and replace DIST with a value slightly > min_dist
# dnb_cutoff <- dnearneigh(coords, 0, DIST) 
# dnb_cutoff.listw <- nb2listw(dnb_cutoff, style="W")

# 4. Global Spatial Autocorrelation (Moran's I)
# Test on the dependent variable
moran.test(trento$ianeselli_vote_pct, knn4.listw, randomisation=TRUE)

# Test on OLS residuals
trento$studres <- rstudent(OLS_model)
lm.morantest(OLS_model, knn4.listw, resfun=rstudent)

# 5. Map OLS studentized residuals
tmap_mode("view") # Set interactive map
tm_shape(trento) + 
  tm_polygons("studres", fill.scale = tm_scale_intervals(style="quantile", n=4),
              fill.legend = tm_legend(title="OLS Studentized Residuals"))
