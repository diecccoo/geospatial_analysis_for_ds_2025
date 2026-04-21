#########################################################################
### PHASE 3: Spatial Regression Models & Elhorst (2010) Strategy      ###
#########################################################################

# Load required package for spatial econometrics
library(spatialreg)

# Reminder of our OLS formula
formula <- ianeselli_vote_pct ~ highly_educated_pct + extra_ue_pct + 
  density + nearest_transport_distance_m

##########################################
### 1. Estimating the Models

# 1. Spatial Durbin Model (SDM) -> Includes spatial lags of Y and X
SDM <- lagsarlm(formula, data = trento, listw=knn4.listw, Durbin=TRUE)

# 2. Spatial Autoregressive Model (SAR) -> Includes spatial lag of Y only
SAR <- lagsarlm(formula, data = trento, listw=knn4.listw)

# 3. Spatial Error Model (SEM) -> Spatial dependence in the error term
SEM <- errorsarlm(formula, data = trento, listw=knn4.listw)

# 4. Spatial Durbin Error Model (SDEM) -> SEM + spatial lags of X
SDEM <- errorsarlm(formula, data = trento, listw=knn4.listw, Durbin=TRUE)

# 5. Spatial Lag of X Model (SLX) -> OLS + spatial lags of X
SLX <- lmSLX(formula, data = trento, listw=knn4.listw)

##########################################
### 2. The Elhorst (2010) Selection Strategy

# We test if the general SDM can be simplified to a narrower model.
# H0: The simpler model (SAR or SEM) is adequate.
# H1: The general model (SDM) is better.

# Test 1: SDM vs SAR
print("Likelihood Ratio Test: SDM vs SAR")
anova(SDM, SAR)

# Test 2: SDM vs SEM
print("Likelihood Ratio Test: SDM vs SEM")
anova(SDM, SEM)

# Check the summary of the best model (We will assume SDM or SAR based on LM tests)
summary(SDM)

