#########################################################################
### PHASE 0: Exploratory Data Analysis (EDA)                          ###
#########################################################################

# Installiamo i pacchetti mancanti (se necessario)
install.packages(c("ggplot2", "dplyr", "sf", "tmap", "ggcorrplot"))

library(sf)
library(dplyr)
library(ggplot2)
library(tmap)
library(ggcorrplot)

# 1. Caricamento Dati
setwd("C:/Users/MyPc/OneDrive/Documenti/Universita/Data Science/Geospatial/geospatial_analysis_for_ds_2025/r_scripts")
trento <- st_read("../data/processed/trento_elections_model_ready.geojson")

# Rimuoviamo eventuali NA per l'esplorazione
trento <- trento[!is.na(trento$ianeselli_vote_pct) & !is.na(trento$highly_educated_pct), ]

##########################################
### 1. Analisi Tabellari (Contesto NIMBY e Competitività)
##########################################

# Creiamo un dataframe senza geometrie per manipolare le tabelle comodamente
df <- st_drop_geometry(trento)

cat("\n--- TOP 5 SEZIONI (Roccaforti Ianeselli) ---\n")
top_5 <- df %>% 
  arrange(desc(ianeselli_vote_pct)) %>% 
  select(id_section, district, ianeselli_vote_pct) %>% 
  head(5)
print(top_5)

cat("\n--- FLOP 5 SEZIONI (Voti più bassi) ---\n")
flop_5 <- df %>% 
  arrange(ianeselli_vote_pct) %>% 
  select(id_section, district, ianeselli_vote_pct) %>% 
  head(5)
print(flop_5)

cat("\n--- SEZIONI IN BILICO (Voto tra 49% e 51%) ---\n")
bilico <- df %>% 
  filter(ianeselli_vote_pct >= 49 & ianeselli_vote_pct <= 51) %>% 
  select(id_section, district, ianeselli_vote_pct) %>%
  arrange(ianeselli_vote_pct)
print(bilico)


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

# Ordiniamo le circoscrizioni in base alla mediana dei voti per una lettura migliore
box_plot <- ggplot(trento, aes(x = reorder(district, ianeselli_vote_pct, FUN = median), 
                               y = ianeselli_vote_pct)) +
  stat_boxplot(geom = 'errorbar', width = 0.2) +
  geom_boxplot(outlier.shape = NA, fill = "lightgrey", alpha = 0.5) +
  # Aggiungiamo i puntini delle singole sezioni sopra il boxplot
  geom_hline(aes(yintercept = mean(ianeselli_vote_pct)), color = "red", linetype = "dashed") +
  coord_flip() + # Giriamo il grafico in orizzontale per leggere bene i nomi dei quartieri
  labs(title = "Spatial Polarization of Voting",
       subtitle = "Vote distribution across different districts. Red line: City average",
       x = "District",
       y = "Vote Percentage (%)") +
  theme_minimal() +
  theme(legend.position = "none", # Togliamo la legenda perché i nomi sono già sull'asse Y
        plot.title = element_text(face = "bold", size = 14))

print(box_plot)


##########################################
### 4. Griglia di Scatterplot Bivariati (2x2)
##########################################
library(tidyr)
library(dplyr)
install.packages("ggpubr")
library(ggpubr) # Libreria magica per le equazioni e i fit nei grafici accademici

# 1. Ristrutturiamo i dati (formato long)
df_long <- st_drop_geometry(trento) %>%
  select(id_section, district, ianeselli_vote_pct, 
         highly_educated_pct, extra_ue_pct, density, nearest_transport_distance_m) %>%
  pivot_longer(
    cols = c(highly_educated_pct, extra_ue_pct, density, nearest_transport_distance_m),
    names_to = "Variable",
    values_to = "Value"
  )

# Rinominiamo le variabili
df_long$Variable <- factor(df_long$Variable, 
                           levels = c("highly_educated_pct", "extra_ue_pct", 
                                      "density", "nearest_transport_distance_m"),
                           labels = c("Highly Educated (%)", "Extra-UE Citizens (%)", 
                                      "Density (people/km²)", "Distance to Transport (m)"))

# 2. Creazione della Griglia con i coefficienti di Correlazione (r e p-value)
scatter_grid <- ggplot(df_long, aes(x = Value, y = ianeselli_vote_pct)) +
  geom_point(aes(color = district), size = 2, alpha = 0.7) +
  geom_smooth(method = "lm", color = "black", linetype = "dashed", se = TRUE, size = 0.8) +
  facet_wrap(~ Variable, scales = "free_x", ncol = 2) +
  
  # LA MAGIA: Questa riga calcola e stampa automaticamente 'r' di Pearson e il p-value!
  stat_cor(method = "pearson", label.x.npc = "left", label.y.npc = "top", size = 4) +
  
  labs(title = "Linear trends across different socio-demographic indicators",
       y = "Ianeselli Vote Percentage (%)",
       x = NULL, 
       color = "District") +
  theme_minimal() +
  theme(legend.position = "bottom", 
        legend.title = element_text(face = "bold"),
        strip.text = element_text(face = "bold", size = 11), 
        plot.title = element_text(face = "bold", size = 14))

print(scatter_grid)


##########################################
### 5. Matrice di Correlazione (Assenza di Multicollinearità)
##########################################

# Selezioniamo solo le variabili numeriche continue
vars_numeric <- df %>% 
  select(ianeselli_vote_pct, highly_educated_pct, extra_ue_pct, density, nearest_transport_distance_m)

# Rinominiamo le colonne per renderle più leggibili nel grafico
colnames(vars_numeric) <- c("Votes", "Education", "Extra_UE", "Density", "Transport_Dist")

# Calcoliamo la matrice di correlazione di Pearson
corr_matrix <- cor(vars_numeric, use = "complete.obs")

# Creiamo la Heatmap
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
### 6. Mappa Choropleth (Visualizzazione Descrittiva Finale)
##########################################


tmap_mode("plot") # Assicurati di essere in modalità "plot" per esportarla staticamente

# Creiamo una mappa con una scala di colori divergente (es. Rosso-Bianco-Blu)
# centrata esattamente sul 50% (la soglia della maggioranza).

map_desc <- tm_shape(trento) +
  tm_polygons("ianeselli_vote_pct",
              title = "Ianeselli Vote Share (%)",
              style = "cont",      
              palette = "-RdBu",   
              midpoint = 50,       # Forza il bianco esattamente sul 50%
              border.col = "grey30", 
              lwd = 0.3) +           
  tm_layout(main.title = "Electoral Geography: Vote Share by Section", # Usa main.title!
            main.title.position = "center",                            # Centra il titolo in alto
            main.title.size = 1.5,
            main.title.fontface = "bold",
            frame = FALSE,         
            legend.outside = TRUE, 
            legend.outside.position = "right",
            legend.title.fontface = "bold")

print(map_desc)

