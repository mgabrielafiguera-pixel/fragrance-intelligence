"""Fase 4 - Exporta desde DuckDB los insumos del análisis estadístico en R (data/export/*.csv).
Uso: python etl/exportar_para_r.py   → luego: Rscript R/estadistica_forecast.R
"""
from pathlib import Path
import duckdb

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "data" / "export"; OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(str(BASE / "data" / "fragancias.duckdb"), read_only=True)
consultas = {
    # serie mensual total y por marca (todas las combinaciones mes × marca, con 0 si no hubo venta)
    "ventas_mensuales_marca": """
        WITH m AS (SELECT DISTINCT strftime(d, '%Y-%m') periodo FROM range(DATE '2025-01-01', DATE '2027-01-01', INTERVAL 1 MONTH) t(d)),
             b AS (SELECT DISTINCT marca FROM dim_producto),
             v AS (SELECT periodo, marca, SUM(venta_neta) venta, SUM(unidades) unidades, SUM(margen_bruto) margen
                   FROM f_ventas JOIN dim_producto USING (sku) GROUP BY 1,2)
        SELECT m.periodo, b.marca, COALESCE(v.venta,0) venta, COALESCE(v.unidades,0) unidades, COALESCE(v.margen,0) margen
        FROM m CROSS JOIN b LEFT JOIN v USING (periodo, marca) ORDER BY 2,1""",
    # líneas de factura (sin devoluciones) para distribución de precios y margen por marca
    "lineas_venta": """
        SELECT factura, fecha, sku, marca, unidades, precio_unit, venta_neta, margen_bruto, margen_bruto/NULLIF(venta_neta,0) margen_pct
        FROM f_ventas JOIN dim_producto USING (sku) WHERE mov = 'FACT' AND venta_neta > 0""",
    # resumen por SKU para relación precio-demanda
    "sku_precio_demanda": """
        SELECT sku, marca, SUM(unidades) unidades, SUM(venta_neta)/NULLIF(SUM(unidades),0) precio_prom
        FROM f_ventas JOIN dim_producto USING (sku) GROUP BY 1,2 HAVING SUM(unidades) > 0""",
}
for nombre, sql in consultas.items():
    df = con.execute(sql).df()
    df.to_csv(OUT / f"{nombre}.csv", index=False)
    print(f"  {nombre}.csv  {len(df)} filas")
