#########################################################################
### PHASE 0: Exploratory Data Analysis (EDA)                          ###
#########################################################################
library(sf)
library(dplyr)
library(ggplot2)
library(tmap)
library(ggcorrplot)
library(tidyr)
library(ggpubr)


setwd("..") #Same as script 1
trento <- st_read("../data/processed/trento_elections_model_ready.geojson") #from the root

trento <- trento[!is.na(trento$ianeselli_vote_pct) & !is.na(trento$highly_educated_pct), ]

##########################################
### 1. Analisi Tabellari (Contesto NIMBY e Competitività)
##########################################

df <- st_drop_geometry(trento)

cat("\n--- TOP 5 Sections ---\n")
top_5 <- df %>% 
  arrange(desc(ianeselli_vote_pct)) %>% 
  select(id_section, district, ianeselli_vote_pct) %>% 
  head(5)
print(top_5)

cat("\n--- FLOP 5 Sections ---\n")
flop_5 <- df %>% 
  arrange(ianeselli_vote_pct) %>% 
  select(id_section, district, ianeselli_vote_pct) %>% 
  head(5)
print(flop_5)



##########################################
### 2. Analisi Univariata: Distribuzione dei Voti
##########################################

hist_plot <- ggplot(trento, aes(x = ianeselli_vote_pct)) +
  geom_histogram(aes(y = ..density..), bins = 15, fill = "steelblue", color = "white", alpha = 0.7) +
  geom_density(color = "darkblue", size = 1.2) +
  geom_vline(aes(xintercept = mean(ianeselli_vote_pct)), color = "red", linetype = "dashed", size = 1) +
  geom_vline(aes(xintercept = median(ianeselli_vote_pct)), color = "orange", linetype = "dashed", size = 1) +
  labs(title = "Distribution of Votes for Ianeselli",
       subtitle = "Red dashed: Mean | Orange dashed: Median",
       x = "Vote Percentage (%)",
       y = "Density") +
  theme_minimal() +
  theme(plot.title = element_text(face = "bold", size = 14))

print(hist_plot)


##########################################
### 3. Boxplot Spaziale: Polarizzazione Centro-Periferia
##########################################

box_plot <- ggplot(trento, aes(x = reorder(district, ianeselli_vote_pct, FUN = median), 
                               y = ianeselli_vote_pct)) +
  stat_boxplot(geom = 'errorbar', width = 0.2) +
  geom_boxplot(outlier.shape = NA, fill = "lightgrey", alpha = 0.5) +
  geom_hline(aes(yintercept = mean(ianeselli_vote_pct)), color = "red", linetype = "dashed") +
  coord_flip() + 
  labs(title = "Spatial Polarization of Voting",
       subtitle = "Vote distribution across different districts. Red line: City average",
       x = "District",
       y = "Vote Percentage (%)") +
  theme_minimal() +
  theme(legend.position = "none",
        plot.title = element_text(face = "bold", size = 14))

print(box_plot)


##########################################
### 4. Griglia di Scatterplot Bivariati (2x2)
##########################################


df_long <- st_drop_geometry(trento) %>%
  select(id_section, district, ianeselli_vote_pct, 
         highly_educated_pct, extra_ue_pct, density, nearest_transport_distance_m) %>%
  pivot_longer(
    cols = c(highly_educated_pct, extra_ue_pct, density, nearest_transport_distance_m),
    names_to = "Variable",
    values_to = "Value"
  )

df_long$Variable <- factor(df_long$Variable, 
                           levels = c("highly_educated_pct", "extra_ue_pct", 
                                      "density", "nearest_transport_distance_m"),
                           labels = c("Highly Educated (%)", "Extra-UE Citizens (%)", 
                                      "Density (people/km²)", "Distance to Transport (m)"))

scatter_grid <- ggplot(df_long, aes(x = Value, y = ianeselli_vote_pct)) +
  geom_point(aes(color = district), size = 1, alpha = 0.5) +
  geom_smooth(method = "lm", color = "black", linetype = "dashed", se = TRUE, size = 0.6) +
  facet_wrap(~ Variable, scales = "free_x", ncol = 2) +
  
  stat_cor(method = "pearson", label.x.npc = "left", label.y.npc = "top", size = 3) +
  
  labs(title = "Linear trends across different socio-demographic indicators",
       y = "Ianeselli Vote Percentage (%)",
       x = NULL, 
       color = "District") +
  theme_minimal() +
  theme(legend.position = "bottom", 
        legend.title = element_text(face = "bold"),
        strip.text = element_text(face = "bold", size = 8), 
        plot.title = element_text(face = "bold", size = 10))

print(scatter_grid)


##test 2

scatter_grid2 <- ggplot(df_long, aes(x = Value, y = ianeselli_vote_pct)) +
  geom_point(aes(color = district), size = 1.5, alpha = 0.6) + 
  geom_smooth(method = "lm", color = "black", linetype = "dashed", se = TRUE, size = 0.7) +
  facet_wrap(~ Variable, scales = "free_x", ncol = 2) +
  stat_cor(method = "pearson", label.x.npc = "left", label.y.npc = "top", size = 4) + # font leggermente ridotto
  labs(title = "Linear trends across socio-demographic indicators",
       y = "Ianeselli Vote Share (%)", x = NULL, color = "District") +
  theme_minimal() +
  theme(legend.position = "bottom", 
        legend.title = element_text(face = "bold"),
        strip.text = element_text(face = "bold", size = 11), 
        plot.title = element_text(face = "bold", size = 13))

print(scatter_grid2)
ggsave("scatter.png", plot = scatter_grid2, width = 12, height = 8, dpi = 300)

##########################################
### 5. Correlation Matrix
##########################################

vars_numeric <- df %>% 
  select(ianeselli_vote_pct, highly_educated_pct, extra_ue_pct, density, nearest_transport_distance_m)

colnames(vars_numeric) <- c("Votes", "Education", "Extra_UE", "Density", "Transport_Dist")

corr_matrix <- cor(vars_numeric, use = "complete.obs")

corr_plot <- ggcorrplot(corr_matrix, 
                        method = "square", 
                        type = "lower", # Mostra solo il triangolo inferiore (meno ridondante)
                        lab = TRUE,     # Mostra i numeri di correlazione
                        lab_size = 4,
                        colors = c("#6D9EC1", "white", "#E46726"),
                        title = "Pearson Correlation Matrix",
                        ggtheme = theme_minimal())

print(corr_plot)


##########################################
### 6. Choropleth Map: Vote Share by Section
##########################################


tmap_mode("plot") 
map_desc <- tm_shape(trento) +
  tm_polygons("ianeselli_vote_pct",
              title = "Ianeselli Vote Share (%)",
              style = "cont",      
              palette = c("#08306b", "#4292c6", "#f7f7f7", "#ef3b2c", "#67000d"),   
              midpoint = 50,      
              border.col = "grey30", 
              lwd = 0.3) +           
  tm_layout(main.title = "Electoral Geography: Vote Share by Section", 
            main.title.position = "center",                            
            main.title.size = 1.5,
            main.title.fontface = "bold",
            frame = FALSE,         
            legend.outside = TRUE, 
            legend.outside.position = "right",
            legend.title.fontface = "bold")

print(map_desc)
tmap_save(map_desc, 
        filename = "choropleth.pdf", 
        width = 10,       
        height = 8, 
        units = "in",     
        device = cairo_pdf) 


#########################################################################
### SAVE GRAPHS FOR LATEX                                     ###
#########################################################################




ggsave("histogram.pdf", plot = hist_plot, 
       width = 8, height = 6, device = cairo_pdf)

ggsave("boxplot.pdf", plot = box_plot, 
       width = 9, height = 8, device = cairo_pdf)

ggsave("scatter.pdf", plot = scatter_grid2, 
       width = 10, height = 8, device = cairo_pdf)

ggsave("plot_4_correlation.pdf", plot = corr_plot, 
       width = 8, height = 8, device = cairo_pdf)


hist_plot <- ggplot(trento, aes(x = ianeselli_vote_pct)) +

  geom_histogram(binwidth = 3, 
                 fill = "steelblue", 
                 color = "white", 
                 alpha = 0.8) +
  geom_vline(aes(xintercept = mean(ianeselli_vote_pct)), color = "red", linetype = "dashed", size = 1) +
  geom_vline(aes(xintercept = median(ianeselli_vote_pct)), color = "orange", linetype = "dashed", size = 1) +
  labs(title = "Distribution of Electoral Sections by Vote Share",
       subtitle = "Bins of 3%. Red: Mean | Orange: Median",
       x = "Ianeselli Vote Share (%)",
       y = "Number of Sections") + # Ora l'asse Y indica il conteggio
  theme_minimal() +
  theme(plot.title = element_text(face = "bold", size = 14))

print(hist_plot)

ggsave("histogram.pdf", plot = hist_plot, 
       width = 8, height = 6, device = cairo_pdf)
