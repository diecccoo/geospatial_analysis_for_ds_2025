##########################################################################
### PHASE 1: Global Autocorrelation and Spatial Weights Matrices       ###
##########################################################################

# Load required packages for spatial analysis and econometrics
library(sf)
library(spdep)
library(tmap)
library(spatialreg) # Required for later stages and LM tests

# 1. Read spatial data 
# Set the working directory to where your R scripts are located
setwd("C:/Users/MyPc/OneDrive/Documenti/Universita/Data Science/Geospatial/geospatial_analysis_for_ds_2025/r_scripts")

# Load the model-ready dataset (moving one folder up to access data/processed/)
trento <- st_read("../data/processed/trento_elections_model_ready.geojson")

# Transform geometries to a metric Coordinate Reference System (UTM Zone 32N, EPSG:32632)
# This is crucial for accurate distance-based measurements in spatial econometrics
trento <- st_transform(trento, 32632) 

# 2. Run Ordinary Least Squares (OLS) model as the baseline
# The spatial analysis starts by estimating a standard non-spatial model
OLS_formula <- ianeselli_vote_pct ~ highly_educated_pct + extra_ue_pct + 
  density + nearest_transport_distance_m
OLS_model <- lm(OLS_formula, data = trento)
summary(OLS_model)

# Extract studentized residuals to inspect spatial dependence later
trento$studres <- rstudent(OLS_model)

# 3. Create Spatial Weights Matrices (W)
# Extract the representative coordinates (centroids) for each spatial unit
coords <- st_centroid(st_geometry(trento))

# --- Option A: k-Nearest Neighbours (KNN) ---
# Recommended approach for this dataset due to irregular/non-contiguous polygons (e.g., Section 58)
# We set k=4 to ensure sufficient connectivity and avoid "islands"
knn4 <- knn2nb(knearneigh(coords, k=4))
knn4.listw <- nb2listw(knn4, style="W") # Row-standardized spatial weights matrix

# --- Option B: Distance-based Neighbors (For academic completeness) ---
# Calculate the minimum critical distance ensuring at least 1 neighbor for all units
knn1 <- knn2nb(knearneigh(coords, k=1))
min_dist <- max(unlist(nbdists(knn1, coords)))
cat("The minimum distance ensuring at least 1 neighbor is:", min_dist, "meters\n")

# Uncomment the following lines if you want to test a distance-band spatial matrix (W)
# Let's assume we use a distance slightly larger than min_dist (e.g., 6000 meters)
# dnb_cutoff <- dnearneigh(coords, 0, 6000) 
# dnb_cutoff.listw <- nb2listw(dnb_cutoff, style="W")


# 4. Global Spatial Autocorrelation Testing (Moran's I)

# Test 4.1: Moran's I on the dependent variable (Vote Percentage)
# Analytical approach
moran.test(trento$ianeselli_vote_pct, knn4.listw, randomisation=TRUE)
# Monte Carlo permutation approach (more robust, as shown in course labs)
set.seed(1234) # Set seed for reproducibility
moran.mc(trento$ianeselli_vote_pct, knn4.listw, nsim=999)

# Test 4.2: Moran's I test on OLS residuals
# This is a key diagnostic tool to detect missing spatial dependence in the linear model
lm.morantest(OLS_model, knn4.listw, resfun=rstudent)


# 5. Diagnostic Lagrange Multiplier (LM) Tests
# As suggested by the Elhorst strategy, we test OLS residuals to check if 
# a Spatial Lag (SAR) or a Spatial Error (SEM) model is more appropriate.
LM_tests <- lm.LMtests(OLS_model, knn4.listw, test=c("LMerr", "LMlag", "RLMerr", "RLMlag", "SARMA"))
summary(LM_tests)


# 6. Map OLS studentized residuals
# Visual inspection of the residuals to spot spatial clusters (High-High or Low-Low)
tmap_mode("view") # Set interactive map mode

ols_residuals <- tm_shape(trento) + 
  tm_polygons("studres", 
              style = "quantile", 
              n = 4,
              palette = "-RdBu", # A divergent palette is excellent for residuals
              title = "OLS Studentized Residuals") +
  tm_layout(title = "Map of OLS Residuals")
tmap_save(ols_residuals, "ols_residuals_map.png")
