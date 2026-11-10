# =====================================================================
# Fragrance Intelligence · Análisis estadístico en R
# Entradas : data/export/*.csv   (python etl/exportar_para_r.py)
# Salidas  : data/r_outputs/*.csv (las lee la pantalla "Estadística (R)" de la app)
# Paquetes : forecast (install.packages("forecast")); el resto es R base.
# Ejecutar desde la carpeta de la app:  Rscript R/estadistica_forecast.R
# =====================================================================
suppressPackageStartupMessages(library(forecast))
dir.create("data/r_outputs", showWarnings = FALSE, recursive = TRUE)
out <- function(df, nombre) write.csv(df, file.path("data/r_outputs", paste0(nombre, ".csv")), row.names = FALSE)

mm   <- read.csv("data/export/ventas_mensuales_marca.csv", stringsAsFactors = FALSE)
lin  <- read.csv("data/export/lineas_venta.csv", stringsAsFactors = FALSE)
skus <- read.csv("data/export/sku_precio_demanda.csv", stringsAsFactors = FALSE)

# ---------- 1. Estadística descriptiva por marca (precio unitario y margen %) ----------
top_marcas <- names(sort(tapply(lin$venta_neta, lin$marca, sum), decreasing = TRUE))[1:8]
desc <- do.call(rbind, lapply(top_marcas, function(m) {
  x <- lin[lin$marca == m, ]
  data.frame(marca = m, lineas = nrow(x),
             precio_media = mean(x$precio_unit), precio_mediana = median(x$precio_unit), precio_sd = sd(x$precio_unit),
             precio_cv = sd(x$precio_unit) / mean(x$precio_unit),
             margen_mediana = median(x$margen_pct, na.rm = TRUE), margen_iqr = IQR(x$margen_pct, na.rm = TRUE))
}))
out(desc, "descriptiva_marcas")

# ---------- 2. Comparación entre marcas: Kruskal-Wallis + post-hoc Wilcoxon (Holm) ----------
sub <- lin[lin$marca %in% top_marcas & !is.na(lin$margen_pct), ]
kw_m <- kruskal.test(margen_pct ~ factor(marca), data = sub)
kw_p <- kruskal.test(precio_unit ~ factor(marca), data = sub)
out(data.frame(variable = c("margen_pct", "precio_unit"),
               estadistico_H = c(kw_m$statistic, kw_p$statistic), gl = c(kw_m$parameter, kw_p$parameter),
               p_valor = c(kw_m$p.value, kw_p$p.value), marcas = length(top_marcas), lineas = nrow(sub)), "kruskal_wallis")
pw <- pairwise.wilcox.test(sub$margen_pct, sub$marca, p.adjust.method = "holm", exact = FALSE)$p.value
pw_df <- as.data.frame(as.table(pw)); names(pw_df) <- c("marca_a", "marca_b", "p_ajustado")
out(pw_df[!is.na(pw_df$p_ajustado), ], "posthoc_margen")

# ---------- 3. Relación precio–demanda (por SKU) ----------
sp <- cor.test(skus$precio_prom, skus$unidades, method = "spearman", exact = FALSE)
pe <- cor.test(log(skus$precio_prom), log(skus$unidades), method = "pearson")
out(data.frame(prueba = c("Spearman precio vs unidades", "Pearson log(precio) vs log(unidades)"),
               coeficiente = c(sp$estimate, pe$estimate), p_valor = c(sp$p.value, pe$p.value), n_sku = nrow(skus)), "precio_demanda")

# ---------- 4. Atípicos (regla IQR 1,5) ----------
iqr_flag <- function(x) { q <- quantile(x, c(.25, .75), na.rm = TRUE); r <- diff(q); x < q[1] - 1.5 * r | x > q[2] + 1.5 * r }
out(data.frame(variable = c("precio_unit", "margen_pct", "margen_negativo"),
               lineas_atipicas = c(sum(iqr_flag(lin$precio_unit), na.rm = TRUE), sum(iqr_flag(lin$margen_pct), na.rm = TRUE),
                                   sum(lin$margen_bruto < 0)), lineas_total = nrow(lin)), "atipicos")

# ---------- 5. Estacionalidad (índice estacional = venta del mes ÷ promedio mensual del año) ----------
tot <- aggregate(cbind(venta, unidades) ~ periodo, data = mm, sum)
tot$anio <- substr(tot$periodo, 1, 4); tot$mes <- as.integer(substr(tot$periodo, 6, 7))
tot$indice <- ave(tot$venta, tot$anio, FUN = function(v) v / mean(v))
est <- aggregate(indice ~ mes, data = tot, mean)
est$indice_2025 <- tot$indice[tot$anio == "2025"]; est$indice_2026 <- tot$indice[tot$anio == "2026"]
out(est, "estacionalidad")

# ---------- 6. Pronóstico 2027 (12 meses): total y top 5 marcas ----------
pronostica <- function(v, nombre) {
  y <- ts(v, start = c(2025, 1), frequency = 12)
  # 24 meses = 2 ciclos: se compara ETS automático contra el ingenuo estacional y se elige el de menor MAPE in-sample
  m_ets <- ets(y); m_sn <- snaive(y, h = 12, level = c(80, 95))
  mape_ets <- accuracy(m_ets)[, "MAPE"]; mape_sn <- accuracy(m_sn)[, "MAPE"]
  usa_ets <- is.finite(mape_ets) && (!is.finite(mape_sn) || mape_ets <= mape_sn)
  fc <- if (usa_ets) forecast(m_ets, h = 12, level = c(80, 95)) else m_sn
  hist <- data.frame(serie = nombre, periodo = sprintf("%d-%02d", 2025 + (seq_along(v) - 1) %/% 12, (seq_along(v) - 1) %% 12 + 1),
                     tipo = "real", valor = v, lo80 = NA, hi80 = NA, lo95 = NA, hi95 = NA)
  pron <- data.frame(serie = nombre, periodo = sprintf("2027-%02d", 1:12), tipo = "pronostico",
                     valor = pmax(as.numeric(fc$mean), 0), lo80 = pmax(fc$lower[, 1], 0), hi80 = fc$upper[, 1],
                     lo95 = pmax(fc$lower[, 2], 0), hi95 = fc$upper[, 2])
  list(datos = rbind(hist, pron),
       modelo = data.frame(serie = nombre, modelo = if (usa_ets) m_ets$method else "Ingenuo estacional",
                           mape_ets = mape_ets, mape_snaive = mape_sn, total_2027 = sum(pron$valor)))
}
series <- list(TOTAL = tot$venta[order(tot$periodo)])
top5 <- names(sort(tapply(mm$venta, mm$marca, sum), decreasing = TRUE))[1:5]
for (m in top5) { x <- mm[mm$marca == m, ]; series[[m]] <- x$venta[order(x$periodo)] }
res <- lapply(names(series), function(n) pronostica(series[[n]], n))
out(do.call(rbind, lapply(res, `[[`, "datos")), "forecast")
out(do.call(rbind, lapply(res, `[[`, "modelo")), "forecast_modelos")
writeLines(paste("Generado:", format(Sys.time(), "%Y-%m-%d %H:%M"), "|", R.version.string,
                 "| forecast", as.character(packageVersion("forecast"))), "data/r_outputs/_version.txt")
cat("OK: data/r_outputs\n")
