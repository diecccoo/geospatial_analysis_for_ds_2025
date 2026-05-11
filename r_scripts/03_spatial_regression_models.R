#########################################################################
### PHASE 3: Spatial Regression Models & Elhorst Selection Strategy   ###
#########################################################################
library(spatialreg)
library(texreg) 

trento <- trento[!is.na(trento$ianeselli_vote_pct) & !is.na(trento$highly_educated_pct), ]

##########################################
### 1. Estimating the Models
##########################################

SDM <- lagsarlm(ianeselli_vote_pct ~ highly_educated_pct + extra_ue_pct + 
                  density + nearest_transport_distance_m, 
                data = trento, listw = knn4.listw, Durbin = TRUE)

SAR <- lagsarlm(ianeselli_vote_pct ~ highly_educated_pct + extra_ue_pct + 
                  density + nearest_transport_distance_m, 
                data = trento, listw = knn4.listw)

SEM <- errorsarlm(ianeselli_vote_pct ~ highly_educated_pct + extra_ue_pct + 
                    density + nearest_transport_distance_m, 
                  data = trento, listw = knn4.listw)

SDEM <- errorsarlm(ianeselli_vote_pct ~ highly_educated_pct + extra_ue_pct + 
                     density + nearest_transport_distance_m, 
                   data = trento, listw = knn4.listw, Durbin = TRUE)

##########################################
### 2. Elhorst Selection Strategy (Model Selection)
##########################################

test_sdm_sar <- anova(SDM, SAR)
test_sdm_sem <- anova(SDM, SEM)

print("--- Test SDM vs SAR ---")
print(test_sdm_sar)

print("--- Test SDM vs SEM ---")
print(test_sdm_sem)

##########################################
### 3. Model Summary and Impacts (SAR)
##########################################

###Since SAR is the best model, we compute impacts
set.seed(1234)
impSAR <- impacts(SAR, listw = knn4.listw, R = 1000)

print("--- Summary and Impacts of SAR ---")
summary(SAR)
summary(impSAR, zstats = TRUE, short = TRUE)

##########################################
### 4. Exporting Regression Table for LaTeX
##########################################

reg <- screenreg(list(OLS_model, SAR, SEM, SDM), 
          custom.model.names = c("OLS", "SAR", "SEM", "SDM"),
          digits = 3,
          caption = "Comparazione dei modelli di regressione spaziale")

print(reg)

texreg(list(OLS_model, SAR, SEM, SDM), 
       custom.model.names = c("OLS", "SAR", "SEM", "SDM"),
       digits = 3,
       stars = c(0.01, 0.05, 0.1), 
       caption = "Regression Results: Spatial Models Comparison",
       label = "tab:spatial_models", 
       file = "spatial_regression_table.tex")



####RESIDUAL MAPS for paper####

trento$ols_raw <- residuals(OLS_model)
trento$sar_raw <- residuals(SAR)


absolute_breaks <- c(-15, -7, -2, 2, 7, 15)

map_ols_raw <- tm_shape(trento) +
  tm_polygons("ols_raw",
              style = "fixed", breaks = absolute_breaks, palette = "-RdBu", midpoint = 0,
              title = "Error (%)", border.col = "grey30", lwd = 0.3) +
  tm_layout(main.title = "OLS Errors", main.title.size = 1, frame = FALSE)

map_sar_raw <- tm_shape(trento) +
  tm_polygons("sar_raw",
              style = "fixed", breaks = absolute_breaks, palette = "-RdBu", midpoint = 0,
              title = "Error (%)", border.col = "grey30", lwd = 0.3) +
  tm_layout(main.title = "SAR Errors", main.title.size = 1, frame = FALSE)

tmap_arrange(map_ols_raw, map_sar_raw, ncol = 2)

print(map_ols_raw)
print(map_sar_raw)

tmap_save(map_ols_raw, "OLS_Error_Map.pdf", width = 8, height = 7, units = "in")
tmap_save(map_sar_raw, "SAR_Error_Map.pdf", width = 8, height = 7, units = "in")

moran.test(residuals(SAR), knn4.listw) 


###RUBUSTNESS CHECK


knn5.listw <- nb2listw(knn2nb(knearneigh(coords, k=5)), style="W")
knn6.listw <- nb2listw(knn2nb(knearneigh(coords, k=6)), style="W")

SAR_k5 <- lagsarlm(ianeselli_vote_pct ~ highly_educated_pct + extra_ue_pct + density + nearest_transport_distance_m, data = trento, listw = knn5.listw)
SAR_k6 <- lagsarlm(ianeselli_vote_pct ~ highly_educated_pct + extra_ue_pct + density + nearest_transport_distance_m, data = trento, listw = knn6.listw)


summary(SAR_k5)
summary(SAR_k6)


set.seed(1234)

impacts_knn5 <- impacts(SAR_k5, listw = knn5.listw, R = 1000)
impacts_knn6 <- impacts(SAR_k6, listw = knn6.listw, R = 1000)

summary(impacts_knn5, zstats = TRUE, short = TRUE)
summary(impacts_knn6, zstats = TRUE, short = TRUE)
