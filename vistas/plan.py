"""Pantalla de planificación de compras para 2027."""
import plotly.graph_objects as go
import streamlit as st

from lib import ui
from lib.db import DB, comparacion_costos_abastecimiento, q
from lib.plan import COLCHON, ERROR_MODELO, calcular


MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


@st.cache_data(show_spinner=False)
def _datos_plan():
    marcas, mensual, indice = calcular(str(DB))
    ventas_reales = q("""
        SELECT anio, mes, SUM(unidades) AS unidades
        FROM f_ventas
        WHERE anio IN (2025, 2026)
        GROUP BY anio, mes
        ORDER BY anio, mes
    """)
    comparacion, _ = comparacion_costos_abastecimiento("TRUE", {})
    return marcas, mensual, indice, ventas_reales, comparacion


def _encabezado_tarjeta(titulo):
    st.markdown(
        f'<div class="fi-plan-card-title">{ui.esc(titulo)}</div>',
        unsafe_allow_html=True,
    )


def _numero(valor, sufijo=" un"):
    return f"{ui.num(valor)}{sufijo}"


def _tarjeta_kpi(etiqueta, valor, detalle):
    return (
        '<div class="fi-plan-kpi">'
        f'<div class="fi-plan-kpi-label">{ui.esc(etiqueta)}</div>'
        f'<div class="fi-plan-kpi-value">{ui.esc(valor)}</div>'
        f'<div class="fi-plan-kpi-detail">{ui.esc(detalle)}</div>'
        '</div>'
    )


def _serie_marca(marcas, nombre):
    fila = marcas.loc[marcas["grupo"].str.upper() == nombre.upper()]
    if fila.empty:
        raise ValueError(f"No se encontró la marca requerida en el cálculo: {nombre}")
    return fila.iloc[0]


def _configurar_grafico(fig, altura, leyenda=True):
    ui.plotly_base(fig, altura, leyenda)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=74 if leyenda else 24, b=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
    )
    return fig


def render():
    marcas, mensual, indice, ventas_reales, comparacion = _datos_plan()
    venta_total = int(marcas["proy_2027"].sum())
    stock_total = int(marcas["stock_dic_2026"].sum())
    compra_total = int(marcas["compra_2027"].sum())
    llegada_diciembre = int(mensual.loc[mensual["mes"] == 12, "compra_llegada"].sum())
    rango_min = round(venta_total * (1 - ERROR_MODELO))
    rango_max = round(venta_total * (1 + ERROR_MODELO))
    stock_objetivo_diciembre = int(
        mensual.loc[mensual["mes"] == 12, "stock_objetivo"].sum()
    )
    pct_importado = (
        (marcas["compra_2027"] * marcas["pct_importado"]).sum()
        / compra_total
    )
    pct_nacional = 100 - pct_importado
    brecha_costos = float(comparacion["brecha"].median() * 100)
    sku_comparables = len(comparacion)
    meses_historia = ventas_reales[["anio", "mes"]].drop_duplicates().shape[0]
    anio_inicio = int(ventas_reales["anio"].min())
    anio_fin = int(ventas_reales["anio"].max())
    creed = _serie_marca(marcas, "CREED")
    montblanc = _serie_marca(marcas, "MONTBLANC")

    por_mes = mensual.groupby("mes", as_index=False)[
        ["venta_proy", "stock_objetivo", "compra_llegada"]
    ].sum().sort_values("mes")
    por_mes["nombre_mes"] = por_mes["mes"].map(lambda mes: MESES[int(mes) - 1])
    ventas_por_anio = ventas_reales.pivot(
        index="mes", columns="anio", values="unidades"
    ).reindex(range(1, 13))
    for anio in (2025, 2026):
        if anio not in ventas_por_anio:
            ventas_por_anio[anio] = 0

    marcas_grafico = marcas.sort_values("compra_2027", ascending=False)
    marcas_tabla = marcas.sort_values("compra_2027", ascending=False).copy()
    marcas_tabla["Rango"] = marcas_tabla.apply(
        lambda fila: f"{ui.num(fila['rango_min'])}–{ui.num(fila['rango_max'])} un",
        axis=1,
    )
    marcas_tabla["Proyección 2027"] = marcas_tabla["proy_2027"].map(
        lambda valor: _numero(valor)
    )
    marcas_tabla["Stock dic-2026"] = marcas_tabla["stock_dic_2026"].map(
        lambda valor: _numero(valor)
    )
    marcas_tabla["Compra 2027"] = marcas_tabla["compra_2027"].map(
        lambda valor: _numero(valor)
    )
    marcas_tabla["% importado"] = marcas_tabla["pct_importado"].map(
        lambda valor: f"{ui.num(valor)}%"
    )
    marcas_tabla = marcas_tabla.rename(columns={"grupo": "Marca"})[
        ["Marca", "Proyección 2027", "Rango", "Stock dic-2026", "Compra 2027", "% importado"]
    ]

    st.markdown("""
    <style>
    .fi-plan-banner {
      padding: 32px 38px; border-radius: 22px; color: #FFFFFF;
      background: radial-gradient(circle at 12% 0%, #8E3B5A 0%, #4A1F33 48%, #2A1520 100%);
      margin: 4px 0 8px;
    }
    .fi-plan-banner-eyebrow { color: #E6C99A; letter-spacing: 3px; font-size: 12px; font-weight: 700; }
    .fi-plan-banner-title {
      color: #FFFFFF; font: 600 46px/1.05 'Cormorant Garamond', Georgia, serif;
      margin: 8px 0 10px;
    }
    .fi-plan-banner-rule { height: 2px; width: 52px; background: #C9A46A; margin: 12px 0; }
    .fi-plan-banner-subtitle { color: #E6C99A; font-size: 18px; font-weight: 600; }
    .fi-plan-banner-copy { color: #F7EDF0; font-size: 14px; margin: 6px 0 0; }
    .fi-plan-card-title {
      background: #4A1F33; color: #FFFFFF; border-radius: 12px;
      padding: 10px 14px; font-weight: 700; line-height: 1.3; margin-bottom: 12px;
    }
    .fi-plan-kpi-grid {
      display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px;
    }
    .fi-plan-kpi {
      min-height: 105px; padding: 12px; border-radius: 12px;
      background: #F4E8D0; border: 1px solid #E6C99A;
    }
    .fi-plan-kpi-label { color: #4A1F33; font-size: 12px; font-weight: 600; }
    .fi-plan-kpi-value {
      color: #5E2139; font: 700 25px/1.15 'Cormorant Garamond', Georgia, serif;
      margin: 5px 0;
    }
    .fi-plan-kpi-detail { color: #6C5360; font-size: 11px; line-height: 1.35; }
    .fi-plan-findings { list-style: none; padding: 0; margin: 2px 0 0; }
    .fi-plan-findings li { margin: 0 0 11px; line-height: 1.45; color: #3A2630; }
    .fi-plan-check { color: #C9A46A; font-weight: 800; padding-right: 7px; }
    .fi-plan-big-number {
      color: #5E2139; font: 700 56px/1 'Cormorant Garamond', Georgia, serif;
      margin: 12px 0 4px;
    }
    .fi-plan-pill {
      display: inline-block; border-radius: 20px; padding: 7px 12px;
      background: #2A1520; color: #E6C99A; font-weight: 700; margin: 10px 0;
    }
    .fi-plan-note { color: #6C5360; font-size: 12px; line-height: 1.5; }
    .fi-plan-conclusion { color: #3A2630; line-height: 1.55; }
    .fi-plan-conclusion em {
      display: block; color: #5E2139; font: italic 600 20px 'Cormorant Garamond', Georgia, serif;
      margin-top: 12px;
    }
    .fi-plan-footer {
      border-radius: 12px; background: #2A1520; color: #E9D6DD;
      padding: 15px 20px; display: flex; justify-content: space-between;
      gap: 10px; align-items: center; margin-top: 18px;
    }
    .fi-plan-footer strong {
      color: #E6C99A; font: italic 600 20px 'Cormorant Garamond', Georgia, serif;
    }
    @media (max-width: 700px) {
      .fi-plan-banner { padding: 24px 20px; }
      .fi-plan-banner-title { font-size: 36px; }
      .fi-plan-kpi-grid { grid-template-columns: 1fr; }
      .fi-plan-footer { display: block; }
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(
        '<section class="fi-plan-banner">'
        '<div class="fi-plan-banner-eyebrow">PLANIFICACIÓN · 2027</div>'
        '<div class="fi-plan-banner-title">Fragrance Intelligence</div>'
        '<div class="fi-plan-banner-rule"></div>'
        '<div class="fi-plan-banner-subtitle">Plan de compras 2027 por marca y por mes</div>'
        f'<div class="fi-plan-banner-copy">De {ui.num(meses_historia)} meses de ventas, compras e inventario a cuántas unidades '
        'comprar, de qué marca y cuándo deben llegar.</div>'
        '</section>',
        unsafe_allow_html=True,
    )
    st.caption("Esta pantalla usa toda la base: no responde a los filtros de marca ni de periodo.")

    resumen_col, ventas_col, hallazgos_col = st.columns([1, 1.6, 1])
    with resumen_col:
        with st.container(border=True):
            _encabezado_tarjeta("Resumen ejecutivo")
            st.markdown(
                f'<p class="fi-plan-note">La proyección usa la demanda histórica y el stock de cierre '
                f'para convertir la venta esperada en una compra por marca y momento de llegada.</p>'
                '<div class="fi-plan-kpi-grid">'
                + _tarjeta_kpi(
                    "Venta proyectada 2027",
                    _numero(venta_total),
                    f"Rango {ui.num(rango_min)}–{ui.num(rango_max)} un",
                )
                + _tarjeta_kpi("Stock al cierre de 2026", _numero(stock_total), "Inventario disponible")
                + _tarjeta_kpi("Compra sugerida 2027", _numero(compra_total), "Plan agregado por marca")
                + _tarjeta_kpi(
                    "Deben llegar antes del 1 de diciembre",
                    _numero(llegada_diciembre),
                    "Llegada requerida para diciembre",
                )
                + "</div>",
                unsafe_allow_html=True,
            )
    with ventas_col:
        with st.container(border=True):
            _encabezado_tarjeta("Evolución de ventas mensuales (unidades)")
            fig_ventas = go.Figure()
            fig_ventas.add_trace(go.Scatter(
                name="2025 real",
                x=MESES,
                y=ventas_por_anio[2025].tolist(),
                mode="lines+markers",
                line=dict(color="#CDB3BD", width=3),
            ))
            fig_ventas.add_trace(go.Scatter(
                name="2026 real",
                x=MESES,
                y=ventas_por_anio[2026].tolist(),
                mode="lines+markers",
                line=dict(color="#8E3B5A", width=3),
            ))
            fig_ventas.add_trace(go.Scatter(
                name="2027 proyección",
                x=por_mes["nombre_mes"],
                y=por_mes["venta_proy"],
                mode="lines+markers",
                line=dict(color="#C9A46A", width=3, dash="dot"),
            ))
            fig_ventas.add_annotation(
                x="Dic",
                y=int(por_mes.loc[por_mes["mes"] == 12, "venta_proy"].iloc[0]),
                text=f"2027: {ui.num(por_mes.loc[por_mes['mes'] == 12, 'venta_proy'].iloc[0])}",
                showarrow=False,
                yshift=15,
                font=dict(color="#5E2139", size=12),
            )
            fig_ventas.update_layout(
                hovermode="x unified",
                yaxis_title="Unidades",
                xaxis_title=None,
            )
            _configurar_grafico(fig_ventas, 315)
            st.plotly_chart(fig_ventas, use_container_width=True, config={"displayModeBar": False})
            st.markdown(
                f'<div class="fi-plan-note">Diciembre vende {ui.num(indice.loc[12], 2)} veces un mes normal; '
                f'mayo {ui.num(indice.loc[5], 2)} por el Día de las Madres.</div>',
                unsafe_allow_html=True,
            )
    with hallazgos_col:
        with st.container(border=True):
            _encabezado_tarjeta("Hallazgos clave")
            porcentaje_diciembre = llegada_diciembre / compra_total * 100
            importadas = marcas.loc[marcas["pct_importado"] == 100]
            importadas_texto = ", ".join(
                f"{fila.grupo} ({ui.num(fila.pct_importado)}%)"
                for fila in importadas.itertuples()
            )
            st.markdown(
                '<ul class="fi-plan-findings">'
                f'<li><span class="fi-plan-check">✓</span>~{ui.num(venta_total)} un en 2027 '
                f'(±{ui.num(ERROR_MODELO * 100)}%).</li>'
                f'<li><span class="fi-plan-check">✓</span>Arranca con {ui.num(stock_total)} un en inventario; '
                f'falta comprar {ui.num(compra_total)}.</li>'
                f'<li><span class="fi-plan-check">✓</span>Diciembre concentra {ui.num(porcentaje_diciembre)}% '
                f'de la compra ({ui.num(llegada_diciembre)} de {ui.num(compra_total)} un).</li>'
                f'<li><span class="fi-plan-check">✓</span>Creed necesita {ui.num(creed["compra_2027"])} un '
                f'(tiene {ui.num(creed["stock_dic_2026"])}); Montblanc necesita '
                f'{ui.num(montblanc["compra_2027"])} (tiene {ui.num(montblanc["stock_dic_2026"])}).</li>'
                f'<li><span class="fi-plan-check">✓</span>{ui.num(pct_importado)}% de la compra es importada; '
                f'esas unidades se piden un mes antes.</li>'
                '</ul>',
                unsafe_allow_html=True,
            )

    st.markdown(" ")
    with st.container(border=True):
        compra_col, grafico_col = st.columns([1, 3.4])
        with compra_col:
            _encabezado_tarjeta("Proyección de compra mensual para 2027")
            promedio_mensual = compra_total / 12
            st.markdown(
                f'<div class="fi-plan-big-number">{ui.num(compra_total)}</div>'
                '<div>unidades a comprar en 2027</div>'
                f'<div class="fi-plan-pill">{ui.num(llegada_diciembre)} en diciembre</div>'
                f'<div class="fi-plan-note">Promedio del plan: {ui.num(promedio_mensual)} un/mes '
                f'({ui.num(compra_total)} ÷ 12).</div>',
                unsafe_allow_html=True,
            )
        with grafico_col:
            fig_compra = go.Figure()
            fig_compra.add_trace(go.Bar(
                name="Venta 2025 real",
                x=por_mes["nombre_mes"],
                y=ventas_por_anio[2025].tolist(),
                marker_color="#CDB3BD",
                hovertemplate="%{x}<br>Venta 2025: %{y:,.0f} un<extra></extra>",
            ))
            color_venta_proy = [
                "#5E2139" if mes == 12 else "#8E3B5A"
                for mes in por_mes["mes"]
            ]
            fig_compra.add_trace(go.Bar(
                name="Venta 2027 proyectada",
                x=por_mes["nombre_mes"],
                y=por_mes["venta_proy"],
                marker_color=color_venta_proy,
                hovertemplate="%{x}<br>Venta 2027: %{y:,.0f} un<extra></extra>",
            ))
            fig_compra.add_trace(go.Bar(
                name="Compra que debe llegar 2027",
                x=por_mes["nombre_mes"],
                y=por_mes["compra_llegada"],
                text=[
                    "" if mes == 12 else ui.num(valor)
                    for mes, valor in zip(por_mes["mes"], por_mes["compra_llegada"])
                ],
                textposition="outside",
                textfont=dict(color="#5E2139", size=10),
                marker_color="#C9A46A",
                hovertemplate="%{x}<br>Compra que debe llegar: %{y:,.0f} un<extra></extra>",
            ))
            fig_compra.add_annotation(
                x="Dic",
                y=llegada_diciembre,
                text=f"<b>{ui.num(llegada_diciembre)}</b>",
                showarrow=False,
                yshift=18,
                font=dict(color="#5E2139", size=12),
            )
            fig_compra.add_vrect(
                x0=10.5, x1=11.5, fillcolor="#E8A0B4", opacity=0.20,
                line_width=0, layer="below",
            )
            fig_compra.update_layout(
                barmode="group",
                yaxis_title="Unidades",
                xaxis_title=None,
            )
            _configurar_grafico(fig_compra, 390)
            st.plotly_chart(fig_compra, use_container_width=True, config={"displayModeBar": False})
            st.caption(
                "Las series mensuales se redondean por marca; sus sumas pueden diferir en una unidad "
                "frente a los totales anuales redondeados por marca."
            )

    marca_col, abastecimiento_col, conclusion_col = st.columns(3)
    with marca_col:
        with st.container(border=True):
            _encabezado_tarjeta("Compra 2027 por marca (unidades)")
            fig_marcas = go.Figure()
            fig_marcas.add_trace(go.Bar(
                name="Stock dic-2026",
                y=marcas_grafico["grupo"],
                x=marcas_grafico["stock_dic_2026"],
                orientation="h",
                marker_color="#CDB3BD",
                hovertemplate="%{y}<br>Stock dic-2026: %{x:,.0f} un<extra></extra>",
            ))
            colores_compra = [
                "#5E2139" if grupo == "CREED" else "#8E3B5A"
                for grupo in marcas_grafico["grupo"]
            ]
            fig_marcas.add_trace(go.Bar(
                name="Compra 2027",
                y=marcas_grafico["grupo"],
                x=marcas_grafico["compra_2027"],
                orientation="h",
                marker_color=colores_compra,
                text=marcas_grafico["compra_2027"].map(ui.num),
                textposition="outside",
                hovertemplate="%{y}<br>Compra 2027: %{x:,.0f} un<extra></extra>",
            ))
            fig_marcas.update_layout(
                barmode="stack",
                xaxis_title="Unidades",
                yaxis_title=None,
            )
            fig_marcas.update_yaxes(
                categoryorder="array",
                categoryarray=marcas_grafico["grupo"].tolist(),
            )
            _configurar_grafico(fig_marcas, max(360, len(marcas_grafico) * 38))
            st.plotly_chart(fig_marcas, use_container_width=True, config={"displayModeBar": False})
    with abastecimiento_col:
        with st.container(border=True):
            _encabezado_tarjeta("¿Nacional o importado?")
            fig_abastecimiento = go.Figure(go.Pie(
                labels=["Importado", "Nacional"],
                values=[pct_importado, pct_nacional],
                hole=0.64,
                sort=False,
                marker=dict(colors=["#8E3B5A", "#C9A46A"]),
                textinfo="label+percent",
                hovertemplate="%{label}: %{percent}<extra></extra>",
            ))
            fig_abastecimiento.update_layout(showlegend=False)
            _configurar_grafico(fig_abastecimiento, 255, leyenda=False)
            st.plotly_chart(
                fig_abastecimiento,
                use_container_width=True,
                config={"displayModeBar": False},
            )
            st.markdown(
                f'<div class="fi-plan-note"><b>Importado ({ui.num(pct_importado)}%):</b> '
                f'{ui.esc(importadas_texto)}; lo de diciembre se pide en octubre.</div>'
                f'<div class="fi-plan-note" style="margin-top:9px"><b>Nacional '
                f'({ui.num(pct_nacional)}%):</b> el costo nacional es {ui.num(brecha_costos, 1)}% mayor '
                f'en mediana en {ui.num(sku_comparables)} SKU comparables; cotizar importación antes de diciembre.</div>',
                unsafe_allow_html=True,
            )
    with conclusion_col:
        with st.container(border=True):
            _encabezado_tarjeta("Conclusión")
            st.markdown(
                '<div class="fi-plan-conclusion">'
                f'2027 no exige vender más, exige comprar a tiempo. La demanda se mantiene cerca de '
                f'{ui.num(venta_total)} unidades proyectadas, pero diciembre necesita '
                f'{ui.num(stock_objetivo_diciembre)} unidades al día 1 y deben llegar '
                f'{ui.num(llegada_diciembre)}. El plan es por marca; la compra final se decide por SKU, '
                f'empezando por los líderes que cerraron 2026 sin stock.'
                '<em>Analizar hoy para comprar a tiempo mañana.</em></div>',
                unsafe_allow_html=True,
            )

    st.markdown("### Plan anual por marca")
    st.dataframe(marcas_tabla, hide_index=True, width="stretch")

    with st.expander("Cómo se calcula"):
        st.markdown(f"""
1. **Base:** unidades vendidas en {anio_fin}, proyectadas con el modelo ingenuo estacional (error del {ui.num(ERROR_MODELO * 100)}%).
2. **Reparto mensual:** se distribuye la proyección con el índice estacional promedio de {anio_inicio}–{anio_fin}.
3. **Stock objetivo:** unidades proyectadas para el mes más un {ui.num(COLCHON * 100)}% de seguridad.
4. **Compra sugerida:** stock objetivo menos existencias disponibles; la compra importada se pide un mes antes.

**Limitaciones:** el plan se calcula por marca; la decisión final de compra debe hacerse por SKU. Usa {ui.num(meses_historia)} meses de historia. La comparación de costos nacional/importado se basa en {ui.num(sku_comparables)} SKU comprados por ambas vías. Los plazos son supuestos: un mes para importado y una semana para nacional.
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
    st.markdown(
        '<div class="fi-plan-footer"><strong>Fragrance Intelligence</strong>'
        f'<span>Cifras en unidades · base {anio_inicio}–{anio_fin} · plan de referencia</span></div>',
        unsafe_allow_html=True,
    )
