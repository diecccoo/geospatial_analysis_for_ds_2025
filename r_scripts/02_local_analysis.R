#########################################################################
### PHASE 2: Local Indicators of Spatial Association (LISA)           ###
#########################################################################
library(sf)
library(spdep)
library(tmap)
library(ggplot2)

# IMPORTANT: you need to have 'trento' (data) and 'knn4.listw' (spatial weights) 
# in your environment from the first r script.

##########################################
### 1. Local Moran's I Computation
##########################################

# We compute the Local Moran's I to identify the specific contribution 
# of each section to the global pattern of spatial dependence.
set.seed(1234) # Ensure reproducibility
lmI_local <- localmoran_perm(trento$ianeselli_vote_pct, knn4.listw, nsim = 9999, iseed = 1)

# Extract the simulated p-values
trento$pval_sim <- lmI_local[, "Pr(z != E(Ii)) Sim"]

# Apply Bonferroni correction for multiple testing
trento$locmpvPerm <- p.adjust(trento$pval_sim, "bonferroni")


##########################################
### 2. Moran Scatterplot Quadrants (LISA Clusters)
##########################################
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
alpha_level <- 0.05
trento$lisa_cluster <- ifelse(trento$locmpvPerm < alpha_level, trento$quadrant, "Not Significant")

# Convert to factor for proper map coloring
trento$lisa_cluster <- factor(trento$lisa_cluster, 
                              levels = c("High-High (Hotspot)", "Low-Low (Coldspot)", 
                                         "High-Low (Spatial Outlier)", "Low-High (Spatial Outlier)", 
                                         "Not Significant"))

### Moran Scatterplot
trento$zDV <- as.numeric(scale(trento$ianeselli_vote_pct))
trento$lag_zDV <- lag.listw(knn4.listw, trento$zDV)


##########################################
### 3. Mapping the Results
##########################################

tmap_mode("view")

# Map 1: Statistical Significance (Bonferroni Corrected)
map_sig <- tm_shape(trento) + 
  tm_polygons("locmpvPerm", 
              fill.scale = tm_scale_intervals(breaks = c(0, 0.001, 0.01, 0.05, 0.1, 1),
                                              values = "-YlOrRd"), 
              fill.legend = tm_legend(title="LISA Significance (Bonferroni)")) +
  tm_layout(title = "Local Moran's I Significance Map")

# Map 2: LISA Cluster Map (Hotspots & Coldspots)
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


#########################################################################
### SALVATAGGIO ESDA (MORAN & LISA) PER LATEX                         ###
#########################################################################

tmap_mode("plot")

tmap_save(map_raw, 
          filename = "LISA_raw.pdf", 
          width = 8, height = 7, units = "in")

tmap_save(map_clusters, 
          filename = "LISA_bonferroni.pdf", 
          width = 8, height = 7, units = "in")

tmap_save(map_sig, 
          filename = "LISA_significance.pdf", 
          width = 8, height = 7, units = "in")

pdf("Moran_Scatterplot.pdf", width = 8, height = 8)

mplot <- moran.plot(trento$ianeselli_vote_pct, 
                    listw = knn4.listw, 
                    main = "Moran Scatterplot - Ianeselli Vote Share",
                    xlab = "Vote Share", 
                    ylab = "Spatially Lagged Vote Share",
                    pch = 19,      # Usa pallini pieni
                    col = "black") # Colore dei punti

grid()
dev.off()
