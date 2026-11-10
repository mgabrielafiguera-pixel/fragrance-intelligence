"""Pantalla 5 · Metodología y controles: fuente, reglas, cuadre contra CONTROLES y cobertura de imágenes."""
import pandas as pd
import streamlit as st
from lib.db import q, meta, BASE
from lib import ui


def render():
    ui.titulo("Trazabilidad", "Metodología y controles")
    st.caption("Los controles de esta página se calculan sobre la base completa; no responden a los filtros globales.")
    mt = meta()
    st.markdown(f"**Fuente:** `{mt['fuente']}` · sha256 `{mt['sha256_fuente'][:16]}…` · base construida {mt['construido']}. "
                "El Excel se lee en modo solo lectura; el ETL verifica que su hash no cambie.")
    st.markdown("**Flujo:** Excel → `etl/construir_duckdb.py` (tablas `raw_*` 1:1) → `sql/modelo.sql` (vistas `dim_*`, `f_*`, "
                "alcance SUBCATEGORIA = FRAGANCIA) → app Streamlit (consultas SQL con filtros parametrizados) · "
                "`etl/exportar_para_r.py` → `R/estadistica_forecast.R` → `data/r_outputs`.")
    st.info(
        "En la versión pública, los proveedores se agrupan por tipo de abastecimiento "
        "(Nacional / Internacional) para proteger la confidencialidad comercial."
    )

    st.markdown("### Cuadre contra la hoja CONTROLES")
    c = q("""SELECT 'Venta neta USD (montos originales)' control, ROUND(SUM(CAST(VENTA_NETA AS DOUBLE)),2) base FROM raw_ventas
             UNION ALL SELECT 'Unidades netas vendidas (original = redistribuido)', SUM(CAST(UNIDADES AS DOUBLE)) FROM raw_ventas
             UNION ALL SELECT 'Costo de ventas USD', ROUND(SUM(CAST(COSTO_TOTAL AS DOUBLE)),2) FROM raw_ventas
             UNION ALL SELECT 'Compras USD costo nacionalizado', ROUND(SUM(CAST(TOTAL_COSTO_NAC AS DOUBLE)),2) FROM raw_compras
             UNION ALL SELECT 'Unidades compradas netas', SUM(CAST(UNIDADES AS DOUBLE)) FROM raw_compras""")
    ctl = q("SELECT Control control, TRY_CAST(Valor AS DOUBLE) controles FROM raw_controles WHERE Control IS NOT NULL")
    m = c.merge(ctl, on="control", how="left")
    m["diferencia"] = m.base - m.controles
    m["estado"] = m.diferencia.abs().lt(0.05).map({True: "OK", False: "REVISAR"})
    st.dataframe(m, hide_index=True, width="stretch")
    fr = q("SELECT SUM(venta_neta) v, SUM(unidades) u, SUM(margen_bruto) mg, count(*) l FROM f_ventas").iloc[0]
    st.markdown(f"Subconjunto **Fragancias** usado por la app: {ui.num(fr.l)} líneas, {ui.usd(fr.v)} de venta neta, "
                f"{ui.num(fr.u)} unidades, margen {ui.pct(fr.mg / fr.v)}. El resto de Belleza (skin care, maquillaje, corporal) queda fuera.")

    st.markdown("### Definiciones de indicadores")
    st.markdown("""
| Indicador | Cálculo |
|---|---|
| Venta neta | Σ VENTA_NETA (facturas − notas de crédito) |
| Costo de ventas | Σ COSTO_TOTAL = unidades × costo de referencia (promedio ponderado nacionalizado; si no hay compras, costo registrado en la venta) |
| Margen bruto / % | Venta neta − costo de ventas / ÷ venta neta |
| Precio de lista | Costo de referencia × 2,5 (con IVA × 1,16), tolerancia ±5% |
| Compras | Σ TOTAL_COSTO_NAC (costo nacionalizado) |
| Share ganado/perdido | Participación de la marca en la venta anual 2026 − 2025, en puntos porcentuales |
| Rotación | Unidades vendidas ÷ inventario promedio en unidades (cierres mensuales) |
| Cobertura | Inventario final en unidades ÷ venta mensual promedio en unidades |
| Variación de costo | Costo unitario máx ÷ mín − 1, por SKU con 2+ recepciones |
""")
    st.markdown("### Reglas del archivo de trabajo")
    st.dataframe(q("SELECT * FROM raw_reglas"), hide_index=True, width="stretch")

    st.markdown("### Cobertura de imágenes oficiales")
    cob = q("""SELECT marca, count(*) sku, count(imagen_url) con_imagen, count(familia_olfativa) con_familia
               FROM dim_producto GROUP BY 1 HAVING count(imagen_url) > 0 ORDER BY 3 DESC""")
    st.dataframe(cob, hide_index=True, width="stretch")
    man = BASE / "data" / "imagenes_manifest.csv"
    if man.exists():
        mf = pd.read_csv(man)
        mf["host"] = mf.url.str.extract(r"//([^/]+)")
        st.markdown(f"Caché local: {(mf.estado == 'OK').sum()} de {len(mf)} imágenes/logos descargados. Los demás se muestran "
                    "desde la URL oficial (si el sitio lo permite) o con las iniciales de la marca.")
        st.dataframe(pd.crosstab(mf.host, mf.estado), width="stretch")
