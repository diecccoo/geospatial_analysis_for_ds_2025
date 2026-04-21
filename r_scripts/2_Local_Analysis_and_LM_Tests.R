#########################################################################
### PHASE 2: Local Spatial Autocorrelation (LISA) and Model Selection ###
#########################################################################

# Ensure libraries are loaded (sf, spdep, tmap)
# Assuming 'trento', 'OLS_model', and 'knn4.listw' are already in your environment from the previous script

##########################################
### 1. Local Moran's I (LISA)

# Calculate Local Moran's I with permutation bootstrap (more robust)
set.seed(123) # For reproducibility
lmI_local <- localmoran_perm(trento$ianeselli_vote_pct, knn4.listw, nsim = 999) 

# Map the significance (p-values) of the local clusters
# to account for multiple testing
# Usiamo i p-value simulati senza l'estrema correzione di Bonferroni
trento$raw_pval <- lmI_local[, "Pr(z != E(Ii)) Sim"]

tm_shape(trento) + 
  tm_polygons("raw_pval", 
              fill.scale = tm_scale_intervals(breaks = c(0, 0.01, 0.05, 0.1, 1)), 
              fill.legend = tm_legend(title="Local Moran's I (Raw p-values)")) 


##########################################
### 2. Lagrange Multiplier (LM) Tests for Model Selection

# The LM tests help us decide whether a Spatial Error Model (SEM) or 
# a Spatial Autoregressive Model (SAR) is more appropriate.
# We test both the standard and robust versions of the tests.
LM_tests <- lm.RStests(OLS_model, knn4.listw, 
                       test=c("RSerr", "RSlag", "adjRSerr", "adjRSlag"))
summary(LM_tests)
