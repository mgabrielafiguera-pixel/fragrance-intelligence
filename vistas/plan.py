"""Pantalla de planificación de compras para 2027."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import ui
from lib.db import DB
from lib.plan import ERROR_MODELO, calcular


MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


@st.cache_data(show_spinner=False)
def _datos_plan():
    return calcular(str(DB))


def render():
    marcas, mensual, _ = _datos_plan()
    venta_total = int(marcas["proy_2027"].sum())
    stock_total = int(marcas["stock_dic_2026"].sum())
    compra_total = int(marcas["compra_2027"].sum())
    llegada_diciembre = int(mensual.loc[mensual["mes"] == 12, "compra_llegada"].sum())
    rango_min = round(venta_total * (1 - ERROR_MODELO))
    rango_max = round(venta_total * (1 + ERROR_MODELO))

    st.caption("Plan calculado con toda la base; no responde a los filtros globales de marca ni de periodo.")
    ui.titulo("PLANIFICACIÓN · 2027", "Plan de compras 2027")
    ui.kpis([
        ("Venta proyectada 2027", f"{ui.num(venta_total)} un",
         f"Rango {ui.num(rango_min)}–{ui.num(rango_max)} un"),
        ("Stock al cierre de 2026", f"{ui.num(stock_total)} un", "Inventario disponible en diciembre"),
        ("Compra sugerida 2027", f"{ui.num(compra_total)} un", "Plan agregado por marca"),
        ("Llegada necesaria en diciembre", f"{ui.num(llegada_diciembre)} un",
         "Compra que debe llegar antes de diciembre"),
    ])

    por_mes = mensual.groupby("mes", as_index=False)[["venta_proy", "compra_llegada"]].sum()
    por_mes = por_mes.sort_values("mes")
    nombres_meses = [MESES[int(mes) - 1] for mes in por_mes["mes"]]
    color_llegadas = ["#5E2139" if mes == 12 else "#8E3B5A" for mes in por_mes["mes"]]

    st.markdown("### Venta proyectada y compras que deben llegar")
    fig_mensual = go.Figure()
    fig_mensual.add_trace(go.Bar(
        name="Venta proyectada",
        x=nombres_meses,
        y=por_mes["venta_proy"],
        marker_color="#CDB3BD",
        hovertemplate="%{x}<br>Venta proyectada: %{y:,.0f} un<extra></extra>",
    ))
    fig_mensual.add_trace(go.Bar(
        name="Compra que debe llegar",
        x=nombres_meses,
        y=por_mes["compra_llegada"],
        marker_color=color_llegadas,
        hovertemplate="%{x}<br>Compra que debe llegar: %{y:,.0f} un<extra></extra>",
    ))
    fig_mensual.update_layout(
        barmode="group",
        title="Unidades por mes",
        xaxis_title="Mes",
        yaxis_title="Unidades",
    )
    st.plotly_chart(ui.plotly_base(fig_mensual, 400), use_container_width=True)

    marcas_grafico = marcas.sort_values("compra_2027", ascending=True)
    categorias = marcas_grafico["grupo"].tolist()
    st.markdown("### Stock y compra sugerida por marca")
    fig_marcas = go.Figure()
    fig_marcas.add_trace(go.Bar(
        name="Stock dic-2026",
        y=categorias,
        x=marcas_grafico["stock_dic_2026"],
        orientation="h",
        marker_color="#CDB3BD",
        hovertemplate="%{y}<br>Stock dic-2026: %{x:,.0f} un<extra></extra>",
    ))
    fig_marcas.add_trace(go.Bar(
        name="Compra sugerida 2027",
        y=categorias,
        x=marcas_grafico["compra_2027"],
        orientation="h",
        marker_color="#8E3B5A",
        hovertemplate="%{y}<br>Compra sugerida 2027: %{x:,.0f} un<extra></extra>",
    ))
    fig_marcas.update_layout(
        barmode="stack",
        title="Unidades por marca",
        xaxis_title="Unidades",
        yaxis_title=None,
    )
    fig_marcas.update_yaxes(categoryorder="array", categoryarray=categorias)
    st.plotly_chart(ui.plotly_base(fig_marcas, max(360, len(categorias) * 34)), use_container_width=True)

    st.markdown("### Plan anual por marca")
    tabla = marcas.sort_values("compra_2027", ascending=False).copy()
    tabla["Rango"] = tabla.apply(
        lambda fila: f"{ui.num(fila['rango_min'])}–{ui.num(fila['rango_max'])} un",
        axis=1,
    )
    tabla["Proyección 2027"] = tabla["proy_2027"].map(lambda valor: f"{ui.num(valor)} un")
    tabla["Stock dic-2026"] = tabla["stock_dic_2026"].map(lambda valor: f"{ui.num(valor)} un")
    tabla["Compra 2027"] = tabla["compra_2027"].map(lambda valor: f"{ui.num(valor)} un")
    tabla["% importado"] = tabla["pct_importado"].map(lambda valor: f"{ui.num(valor)}%")
    tabla = tabla.rename(columns={"grupo": "Marca"})[
        ["Marca", "Proyección 2027", "Rango", "Stock dic-2026", "Compra 2027", "% importado"]
    ]
    st.dataframe(tabla, hide_index=True, width="stretch")

    with st.expander("Cómo se calcula"):
        st.markdown("""
1. **Base:** unidades vendidas en 2026, proyectadas con el modelo ingenuo estacional (error del 19%).
2. **Reparto mensual:** se distribuye la proyección con el índice estacional promedio de 2025–2026.
3. **Stock objetivo:** unidades proyectadas para el mes más un 30% de seguridad.
4. **Compra sugerida:** stock objetivo menos existencias disponibles; la compra importada se pide un mes antes.

**Limitaciones:** el plan se calcula por marca; la decisión final de compra debe hacerse por SKU. Usa 24 meses de historia. La comparación de costos nacional/importado se basa en 10 SKU comprados por ambas vías. Los plazos son supuestos: un mes para importado y una semana para nacional.
""")

    mensual_csv = mensual.rename(columns={
        "grupo": "Marca",
        "mes": "Mes",
        "venta_proy": "Venta proyectada",
        "stock_objetivo": "Stock objetivo",
        "compra_llegada": "Compra que debe llegar",
        "stock_fin": "Stock al cierre",
    }).copy()
    mensual_csv["Mes"] = mensual_csv["Mes"].map(lambda mes: MESES[int(mes) - 1])
    st.download_button(
        "Descargar plan mensual por marca (CSV)",
        mensual_csv.to_csv(index=False).encode("utf-8-sig"),
        "plan_compras_2027.csv",
        "text/csv",
        width="stretch",
    )
