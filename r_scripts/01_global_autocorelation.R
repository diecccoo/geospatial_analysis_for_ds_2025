##########################################################################
### PHASE 1: Global Autocorrelation and Spatial Weights Matrices       ###
##########################################################################

library(sf)
library(spdep)
library(tmap)
library(spatialreg)

setwd("..") #SET YOUR WD


trento <- st_read("../data/processed/trento_elections.geojson") #from the root of the repository
trento <- st_transform(trento, 32632) 

# 2. Run Ordinary Least Squares (OLS) model as the baseline
OLS_formula <- ianeselli_vote_pct ~ highly_educated_pct + extra_ue_pct + 
  density + nearest_transport_distance_m
OLS_model <- lm(OLS_formula, data = trento)
summary(OLS_model)

# Extract studentized residuals to inspect spatial dependence later
trento$studres <- rstudent(OLS_model)

# 3. Create Spatial Weights Matrices (W)
coords <- st_centroid(st_geometry(trento))

# --- Option A: k-Nearest Neighbours (KNN) ---
# Used approach for this dataset, due to its irregular/non-contiguous polygons (e.g., Section 58)
# We set k=4 to ensure sufficient connectivity, trying to avoid islands
knn4 <- knn2nb(knearneigh(coords, k=4))
knn4.listw <- nb2listw(knn4, style="W")

# --- Option B: Distance-based Neighbors (For academic completeness) ---
knn1 <- knn2nb(knearneigh(coords, k=1))
min_dist <- max(unlist(nbdists(knn1, coords)))
print(min_dist) # This is the minimum distance to ensure all units have at least one neighbor

# Uncomment the following lines if you want to test a distance-band spatial matrix (W)

# dnb_cutoff <- dnearneigh(coords, 0, 6000) 
# dnb_cutoff.listw <- nb2listw(dnb_cutoff, style="W")


# 4. Global Spatial Autocorrelation Testing (Moran's I)

# Test 4.1: Moran's I on the dependent variable (Vote Percentage)
moran.test(trento$ianeselli_vote_pct, knn4.listw, randomisation=TRUE)
# Monte Carlo permutation approach (more robust, as shown in course labs)
set.seed(1234)
moran.mc(trento$ianeselli_vote_pct, knn4.listw, nsim=999)

# Test 4.2: Moran's I test on OLS residuals
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

print(ols_residuals)
tmap_save(ols_residuals, "ols_residuals_map.png")



