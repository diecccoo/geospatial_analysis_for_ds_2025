#########################################################################
### PHASE 2: Local Indicators of Spatial Association (LISA)           ###
#########################################################################

# Ensure libraries are loaded
library(sf)
library(spdep)
library(tmap)
library(ggplot2)

# Assuming 'trento' (data) and 'knn4.listw' (spatial weights) 
# are already in your environment from Phase 1.

##########################################
### 1. Local Moran's I Computation
##########################################

# We compute the Local Moran's I to identify the specific contribution 
# of each section to the global pattern of spatial dependence.
# To perform bootstrap-based inference, conditional permutation is used.
# Following the course guidelines, we use 9999 simulations for robust inference.
set.seed(1234) # Ensure reproducibility
lmI_local <- localmoran_perm(trento$ianeselli_vote_pct, knn4.listw, nsim = 9999, iseed = 1)

# Extract the simulated p-values
trento$pval_sim <- lmI_local[, "Pr(z != E(Ii)) Sim"]

# Apply Bonferroni correction for multiple testing
# This is a strict but necessary correction when testing multiple spatial units
trento$locmpvPerm <- p.adjust(trento$pval_sim, "bonferroni")


##########################################
### 2. Moran Scatterplot Quadrants (LISA Clusters)
##########################################

# To map the Hotspots (High-High) and Coldspots (Low-Low), we must identify
# the quadrant of the Moran scatterplot each spatial unit belongs to.

# 2.1 Center the variable of interest around its mean
cDV <- trento$ianeselli_vote_pct - mean(trento$ianeselli_vote_pct)

# 2.2 Calculate the spatial lag of the centered variable
lagDV <- lag.listw(knn4.listw, cDV)

# 2.3 Assign quadrants based on the sign of the variable and its spatial lag
trento$quadrant <- NA
trento$quadrant[cDV > 0 & lagDV > 0] <- "High-High (Hotspot)"
trento$quadrant[cDV < 0 & lagDV < 0] <- "Low-Low (Coldspot)"
trento$quadrant[cDV < 0 & lagDV > 0] <- "Low-High (Spatial Outlier)"
trento$quadrant[cDV > 0 & lagDV < 0] <- "High-Low (Spatial Outlier)"

# 2.4 Filter the quadrants using the Bonferroni-corrected significance level (alpha = 0.05)
# Non-significant areas will be marked as "Not Significant"
alpha_level <- 0.05
trento$lisa_cluster <- ifelse(trento$locmpvPerm < alpha_level, trento$quadrant, "Not Significant")

# Convert to factor for proper map coloring
trento$lisa_cluster <- factor(trento$lisa_cluster, 
                              levels = c("High-High (Hotspot)", "Low-Low (Coldspot)", 
                                         "High-Low (Spatial Outlier)", "Low-High (Spatial Outlier)", 
                                         "Not Significant"))

### Moran Scatterplot

# The Moran Scatterplot plots the variable against its spatial lag.
# The slope of the linear regression line in this plot represents the Global Moran's I.
# The four quadrants represent: High-High (top-right), Low-Low (bottom-left), 
# Low-High (top-left), and High-Low (bottom-right).

trento$zDV <- as.numeric(scale(trento$ianeselli_vote_pct))
trento$lag_zDV <- lag.listw(knn4.listw, trento$zDV)

# Creazione del plot
ggplot(trento, aes(x = zDV, y = lag_zDV)) +
  # Disegna i 4 quadranti
  geom_hline(yintercept = 0, linetype = "dashed", color = "darkgrey", size = 0.8) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "darkgrey", size = 0.8) +
  # Aggiunge i punti (colorati per LISA cluster se l'hai calcolato, altrimenti neri)
  geom_point(aes(color = lisa_cluster), size = 2, alpha = 0.8) +
  # Linea di regressione rossa (la cui pendenza è il Moran's I)
  geom_smooth(method = "lm", color = "red", se = FALSE, size = 1.2) +
  # Colori personalizzati per i cluster
  scale_color_manual(values = c("High-High (Hotspot)" = "red", 
                                "Low-Low (Coldspot)" = "blue", 
                                "Not Significant" = "grey70",
                                "Low-High (Spatial Outlier)" = "lightblue",
                                "High-Low (Spatial Outlier)" = "pink")) +
  labs(title = "Moran Scatterplot - Elezioni Trento",
       subtitle = "Pendenza della retta = Global Moran's I (0.60)",
       x = "Voti Ianeselli (Standardizzati)",
       y = "Ritardo Spaziale (Media dei vicini)",
       color = "LISA Cluster") +
  theme_minimal() +
  theme(legend.position = "bottom",
        plot.title = element_text(face = "bold", size = 14))

#####SALVARE O FARE GGPLOT!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

# Note: The function automatically centers the variables and draws the zero-lines 
# that divide the space into the 4 LISA quadrants.


##########################################
### 3. Mapping the Results
##########################################

tmap_mode("view")

# Map 1: Statistical Significance (Bonferroni Corrected)
# Using intervals similar to the professor's script
map_sig <- tm_shape(trento) + 
  tm_polygons("locmpvPerm", 
              fill.scale = tm_scale_intervals(breaks = c(0, 0.001, 0.01, 0.05, 0.1, 1),
                                              values = "-YlOrRd"), 
              fill.legend = tm_legend(title="LISA Significance (Bonferroni)")) +
  tm_layout(title = "Local Moran's I Significance Map")

# Map 2: LISA Cluster Map (Hotspots & Coldspots)
# This map shows WHERE the significant spatial associations are located
colors_lisa <- c("High-High (Hotspot)" = "red", 
                 "Low-Low (Coldspot)" = "blue", 
                 "High-Low (Spatial Outlier)" = "pink", 
                 "Low-High (Spatial Outlier)" = "lightblue", 
                 "Not Significant" = "white")

map_clusters <- tm_shape(trento) + 
  tm_polygons("lisa_cluster", 
              fill.scale = tm_scale_categorical(values = colors_lisa),
              fill.legend = tm_legend(title="LISA Clusters")) +
  tm_layout(title = "Local Moran's I Cluster Map")

# Print the maps
map_sig
tmap_save(map_sig, "LISA_Significance_Map_bonferroni.png")
map_clusters
tmap_save(map_clusters, "LISA_Cluster_Map_bonferroni.png")


# Map 3: LISA Clusters WITHOUT Bonferroni (Raw p-values)
# We use the raw p-values from the 9999 simulations
trento$lisa_cluster_raw <- ifelse(trento$pval_sim < 0.05, trento$quadrant, "Not Significant")

trento$lisa_cluster_raw <- factor(trento$lisa_cluster_raw, 
                                  levels = c("High-High (Hotspot)", "Low-Low (Coldspot)", 
                                             "High-Low (Spatial Outlier)", "Low-High (Spatial Outlier)", 
                                             "Not Significant"))

# Visualizing the comparison
map_raw <- tm_shape(trento) + 
  tm_polygons("lisa_cluster_raw", 
              fill.scale = tm_scale_categorical(values = colors_lisa),
              fill.legend = tm_legend(title="LISA Clusters (Raw p < 0.05)")) +
  tm_layout(title = "LISA Cluster Map - Raw")


map_raw
tmap_save(map_raw, "LISA_Cluster_Map_raw.png")
