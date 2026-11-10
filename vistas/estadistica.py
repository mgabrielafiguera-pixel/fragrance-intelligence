"""Pantalla 4 · Estadística: exploración filtrable (Python) + resultados formales de R (data/r_outputs)."""
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from lib.db import q, BASE
from lib import ui

R_OUT = BASE / "data" / "r_outputs"
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _r(nombre):
    p = R_OUT / f"{nombre}.csv"
    return pd.read_csv(p) if p.exists() else None


def _pv(p):
    return "< 0,001" if p < 0.001 else ui._es(f"{p:.3f}")


def render():
    f = st.session_state["filtros"]
    w, p = f.where()
    ui.titulo("Análisis estadístico · Python + R", "¿Qué dicen los datos?", f.descripcion)
    st.caption("Los análisis exploratorios en Python respetan los filtros globales. Las pruebas y el pronóstico de R usan la base completa de 2025–2026 y no cambian con esos filtros.")
    ver = (R_OUT / "_version.txt")
    if ver.exists():
        st.caption(f"Resultados R: {ver.read_text().strip()}.")
    else:
        st.warning("Aún no hay resultados de R. Ejecuta `python etl/exportar_para_r.py` y luego "
                   "`Rscript R/estadistica_forecast.R` (requiere R y el paquete forecast)."
                   + ("" if shutil.which("Rscript") else " R no está instalado en este equipo."))

    lin = q(f"""SELECT marca, precio_unit, margen_bruto / NULLIF(venta_neta,0) margen_pct, unidades, venta_neta, margen_bruto
                FROM f_ventas JOIN dim_producto USING (sku) WHERE {w} AND mov='FACT' AND venta_neta > 0""", p)
    if lin.empty:
        st.warning("Sin ventas para los filtros."); return

    # 1 · distribución de precios por marca
    c1, c2 = st.columns(2)
    with c1:
        top = lin.groupby("marca").venta_neta.sum().nlargest(8).index
        d = lin[lin.marca.isin(top)].copy(); d["marca"] = d.marca.map(ui.titulo_caso)
        orden = d.groupby("marca").precio_unit.median().sort_values().index.tolist()
        fig = px.box(d, y="marca", x="precio_unit", orientation="h", category_orders={"marca": orden},
                     color_discrete_sequence=[ui.VINO], points=False)
        fig.update_layout(title=dict(text="1 · Distribución del precio unitario por diseñador", font=dict(family="Cormorant Garamond", size=20)),
                          xaxis_title="Precio unitario facturado (USD)", yaxis_title=None)
        st.plotly_chart(ui.plotly_base(fig, 400, False), use_container_width=True)
        med = d.groupby("marca").precio_unit.median()
        st.markdown(f'<div class="fi-note">Mediana más alta: <b>{med.idxmax()}</b> ({ui.usd(med.max())}); más baja: '
                    f'<b>{med.idxmin()}</b> ({ui.usd(med.min())}). Top 8 marcas por venta en el filtro.</div>', unsafe_allow_html=True)
    # 2 · precio vs demanda
    with c2:
        s = q(f"""SELECT sku, marca, SUM(unidades) un, SUM(venta_neta)/NULLIF(SUM(unidades),0) precio
                  FROM f_ventas JOIN dim_producto USING (sku) WHERE {w} GROUP BY 1,2 HAVING SUM(unidades) > 0""", p)
        s = s[(s.precio > 0) & (s.un > 0)].copy()
        rho = s[["precio", "un"]].rank().corr().iloc[0, 1] if len(s) > 3 else np.nan
        fig = px.scatter(s, x="precio", y="un", log_x=True, log_y=True, color_discrete_sequence=[ui.ROSA], opacity=.6,
                         custom_data=["sku", "marca"])
        fig.update_traces(hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}"
                          "<br>Precio promedio: $%{x:,.2f}<br>Unidades: %{y:,.0f}<extra></extra>")
        if len(s) > 3:
            b = np.polyfit(np.log(s.precio), np.log(s.un), 1)
            xs = np.linspace(np.log(s.precio.min()), np.log(s.precio.max()), 50)
            fig.add_scatter(x=np.exp(xs), y=np.exp(b[1] + b[0] * xs), mode="lines", line=dict(color=ui.VINO_OSC, width=2), name="tendencia log-log")
        fig.update_layout(title=dict(text=f"2 · Precio vs unidades por SKU (ρ Spearman = {ui._es(f'{rho:.2f}')})", font=dict(family="Cormorant Garamond", size=20)),
                          xaxis_title="Precio promedio (USD, log)", yaxis_title="Unidades (log)")
        st.plotly_chart(ui.plotly_base(fig, 400, False), use_container_width=True)
        pdm = _r("precio_demanda")
        if pdm is not None:
            r0 = pdm.iloc[0]
            st.markdown(f'<div class="fi-note"><b>R · todo el periodo:</b> Spearman ρ = {ui._es(f"{r0.coeficiente:.3f}")} '
                        f'(p {_pv(r0.p_valor)}, {int(r0.n_sku)} SKU). Relación positiva pero débil: en este portafolio el precio alto '
                        'no reduce la demanda; el cliente elige por marca más que por precio.</div>', unsafe_allow_html=True)

    # 3 · comparación entre marcas (R) y 4 · atípicos
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("#### 3 · Comparación estadística entre marcas · R")
        kw = _r("kruskal_wallis"); ph = _r("posthoc_margen"); de = _r("descriptiva_marcas")
        if kw is not None:
            for r in kw.itertuples():
                st.markdown(f"- **{'Margen %' if r.variable == 'margen_pct' else 'Precio unitario'}**: Kruskal-Wallis H = {ui._es(f'{r.estadistico_H:.1f}')}, "
                            f"gl = {int(r.gl)}, p {_pv(r.p_valor)} ({int(r.marcas)} marcas, {ui.num(r.lineas)} líneas).")
            if ph is not None:
                sig = (ph.p_ajustado < 0.05).sum()
                st.markdown(f"- Post-hoc Wilcoxon por pares (Holm): **{sig} de {len(ph)}** pares de marcas difieren en margen (p < 0,05).")
            st.markdown("Conclusión: las diferencias de margen y precio entre marcas no son ruido; son estadísticamente significativas.")
            if de is not None:
                with st.expander("Descriptiva por marca (R)"):
                    st.dataframe(de, hide_index=True, width="stretch")
                    if ph is not None: st.dataframe(ph, hide_index=True, width="stretch")
        else:
            st.info("Pendiente de ejecutar el script R.")
    with c4:
        def iqr(x):
            a, b = x.quantile([.25, .75]); r = b - a
            return ((x < a - 1.5 * r) | (x > b + 1.5 * r)).sum()
        ui.kpis([("Líneas con precio atípico", ui.num(iqr(lin.precio_unit)), "regla IQR 1,5"),
                 ("Líneas con margen atípico", ui.num(iqr(lin.margen_pct.dropna())), "regla IQR 1,5"),
                 ("Ventas con margen negativo", ui.num((lin.margen_bruto < 0).sum()), f"de {ui.num(len(lin))} líneas facturadas")])
        neg = q(f"""SELECT p.marca, p.etiqueta, v.factura, v.fecha, v.unidades, v.precio_unit, v.costo_unit, v.margen_bruto, v.origen_costo
                    FROM f_ventas v JOIN dim_producto p USING (sku) WHERE {w.replace('fecha', 'v.fecha')} AND v.mov='FACT' AND v.margen_bruto < 0
                    ORDER BY v.margen_bruto LIMIT 200""", p)
        with st.expander("4 · Ver ventas con margen negativo (auditoría)"):
            st.dataframe(neg, hide_index=True, width="stretch")
        st.markdown('<div class="fi-note">Cada atípico debe clasificarse: precio especial, error de registro o producto premium. '
                    'No se eliminan del análisis.</div>', unsafe_allow_html=True)

    # 5 · estacionalidad
    st.markdown("### 5 · Estacionalidad de las ventas")
    c5, c6 = st.columns([3, 2])
    m = q(f"SELECT anio, mes, SUM(venta_neta) v FROM f_ventas WHERE {w} GROUP BY 1,2", p)
    m["indice"] = m.v / m.groupby("anio").v.transform("mean")
    m["Mes"] = m.mes.map(lambda i: MESES[i - 1]); m["Año"] = m.anio.astype(str)
    fig = px.bar(m.sort_values(["anio", "mes"]), x="Mes", y="indice", color="Año", barmode="group",
                 color_discrete_map={"2025": ui.ROSA, "2026": ui.VINO_OSC}, category_orders={"Mes": MESES})
    fig.add_hline(y=1, line_dash="dot", line_color="#6B4E5A")
    fig.update_layout(yaxis_title="Índice (1 = mes promedio del año)", xaxis_title=None)
    c5.plotly_chart(ui.plotly_base(fig, 340), use_container_width=True)
    dic = m[m.mes == 12].set_index("anio").v / m.groupby("anio").v.sum()
    c6.markdown('<div class="fi-panel">' + "".join(
        f"<div style='margin:4px 0'>Diciembre {a}: <b>{ui.pct(x)}</b> de la venta anual</div>" for a, x in dic.items())
        + '<div class="fi-note" style="margin-top:8px">Índice estacional = venta del mes ÷ promedio mensual de su año. '
          'Diciembre (Navidad) es el pico; mayo (Día de las Madres) el segundo. Con 2 años de historia la estacionalidad '
          'es indicativa, no concluyente.</div></div>', unsafe_allow_html=True)

    # 6 · pronóstico (R)
    st.markdown("### 6 · Pronóstico de demanda 2027 · R")
    fc = _r("forecast"); mods = _r("forecast_modelos")
    if fc is None:
        st.info("Estructura lista: al ejecutar R/estadistica_forecast.R aparecerá aquí la serie real + pronóstico con bandas 80% y 95%.")
        return
    series = fc.serie.unique().tolist()
    serie = st.selectbox("Serie", series, format_func=lambda s: "Total fragancias" if s == "TOTAL" else ui.titulo_caso(s), key="fc_serie")
    d = fc[fc.serie == serie]; h = d[d.tipo == "real"]; pr = d[d.tipo == "pronostico"]
    fig = go.Figure()
    fig.add_scatter(x=pd.concat([pr.periodo, pr.periodo[::-1]]), y=pd.concat([pr.hi95, pr.lo95[::-1]]), fill="toself",
                    fillcolor="rgba(232,160,180,.25)", line=dict(width=0), name="IC 95%", hoverinfo="skip")
    fig.add_scatter(x=pd.concat([pr.periodo, pr.periodo[::-1]]), y=pd.concat([pr.hi80, pr.lo80[::-1]]), fill="toself",
                    fillcolor="rgba(184,88,122,.30)", line=dict(width=0), name="IC 80%", hoverinfo="skip")
    fig.add_scatter(x=h.periodo, y=h.valor, mode="lines+markers", line=dict(color=ui.VINO_OSC, width=2.4), name="Real 2025–2026")
    fig.add_scatter(x=pr.periodo, y=pr.valor, mode="lines+markers", line=dict(color=ui.ROSA, width=2.4, dash="dash"), name="Pronóstico 2027")
    fig.update_layout(yaxis_title="Venta neta (USD)")
    st.plotly_chart(ui.plotly_base(fig, 400), use_container_width=True)
    mo = mods[mods.serie == serie].iloc[0]
    hist26 = h[h.periodo.str.startswith("2026")].valor.sum()
    st.markdown(f'<div class="fi-note">Modelo elegido: <b>{mo.modelo}</b> (menor MAPE in-sample entre ETS automático = '
                f'{ui._es(f"{mo.mape_ets:.1f}") if np.isfinite(mo.mape_ets) else "n/d"}% e ingenuo estacional = {ui._es(f"{mo.mape_snaive:.1f}")}%). '
                f'Total 2027 pronosticado: <b>{ui.usd(mo.total_2027)}</b> vs {ui.usd(hist26)} real 2026. Con 24 meses de historia el '
                'pronóstico es orientativo: el error es alto y las bandas son amplias; no usarlo para compras sin juicio comercial.</div>',
                unsafe_allow_html=True)
    with st.expander("Modelos y error por serie"):
        st.dataframe(mods, hide_index=True, width="stretch")
