#########################################################################
### PHASE 3: Spatial Regression Models & Elhorst Selection Strategy   ###
#########################################################################

library(spatialreg)
library(texreg) 

# Assicuriamoci che i dati non abbiano valori nulli o infiniti
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

set.seed(1234)
# Visto che il SAR ha vinto la selezione, calcoliamo i suoi impatti:
impSAR <- impacts(SAR, listw = knn4.listw, R = 1000)

print("--- Summary and Impacts of SAR ---")
summary(SAR)
summary(impSAR, zstats = TRUE, short = TRUE)

##########################################
### 4. Exporting Regression Table for LaTeX
##########################################

# 1. Esportazione in console (per leggerla bene)
screenreg(list(OLS_model, SAR, SEM, SDM), 
          custom.model.names = c("OLS", "SAR", "SEM", "SDM"),
          digits = 3,
          caption = "Comparazione dei modelli di regressione spaziale")

# 2. Esportazione in file .tex per Overleaf
texreg(list(OLS_model, SAR, SEM, SDM), 
       custom.model.names = c("OLS", "SAR", "SEM", "SDM"),
       digits = 3,
       stars = c(0.01, 0.05, 0.1), 
       caption = "Regression Results: Spatial Models Comparison",
       label = "tab:spatial_models", 
       file = "spatial_regression_table.tex")
