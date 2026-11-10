"""Pantalla 3 · Rentabilidad e inventario: margen por marca/producto, matriz rotación × margen, inventario y cobertura."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from lib.db import q
from lib import ui


def _rot_sku(f) -> pd.DataFrame:
    """Rotación por SKU = unidades vendidas en el periodo ÷ inventario promedio (promedio de inventarios finales mensuales)."""
    wv, pv = f.where("v.fecha", "v.sku")
    wi, pi = f.where_periodo()
    return q(f"""
      WITH inv AS (SELECT sku, AVG(inv_final_un) inv_prom, arg_max(inv_final_un, periodo) inv_final,
                          arg_max(valor_inv_final, periodo) valor_final, count(*) meses
                   FROM f_inventario WHERE {wi} GROUP BY 1),
           ven AS (SELECT v.sku, SUM(unidades) un, SUM(venta_neta) venta, SUM(margen_bruto) margen, SUM(costo_total) costo,
                          SUM(precio_lista * unidades) lista
                   FROM f_ventas v WHERE {wv} GROUP BY 1)
      SELECT p.sku, p.marca, p.etiqueta, p.imagen_url, COALESCE(ven.un,0) un, COALESCE(ven.venta,0) venta,
             COALESCE(ven.margen,0) margen, ven.costo, ven.margen / NULLIF(ven.venta,0) margen_pct,
             ven.venta / NULLIF(ven.un,0) precio, ven.costo / NULLIF(ven.un,0) costo_un,
             inv.inv_prom, inv.inv_final, inv.valor_final, inv.meses,
             COALESCE(ven.un,0) / NULLIF(inv.inv_prom,0) rotacion,
             inv.inv_final / NULLIF(COALESCE(ven.un,0) / NULLIF(inv.meses,0),0) cobertura_meses
      FROM dim_producto p LEFT JOIN inv USING (sku) LEFT JOIN ven USING (sku)
      WHERE inv.sku IS NOT NULL OR ven.sku IS NOT NULL""", pv | pi)


def render():
    f = st.session_state["filtros"]
    ui.titulo("Ventas × compras × inventario", "Rentabilidad e inventario", f.descripcion)
    s = _rot_sku(f)
    if s.venta.sum() == 0:
        st.warning("No hay ventas con los filtros seleccionados."); return
    venta, margen, costo = s.venta.sum(), s.margen.sum(), s.costo.sum()
    wi, pi = f.where_periodo()
    invm = q(f"""SELECT periodo, SUM(valor_inv_final) valor, SUM(inv_final_un) un FROM f_inventario WHERE {wi}
                 GROUP BY 1 ORDER BY 1""", pi)
    mb = s.groupby("marca").agg(venta=("venta", "sum"), margen=("margen", "sum"), un=("un", "sum"), inv_prom=("inv_prom", "sum")).reset_index()
    mb["margen_pct"] = mb.margen / mb.venta
    mb["rotacion"] = mb.un / mb.inv_prom
    meses = len(invm)
    venta_mes_un = s.un.sum() / max(meses, 1)
    rapida = mb[mb.venta >= mb.venta.quantile(.5)].sort_values("rotacion", ascending=False).iloc[0]
    ui.kpis([
        ("Margen bruto", ui.usd(margen), f"{ui.pct(margen / venta)} sobre ventas"),
        ("Costo de ventas", ui.usd(costo), "costo de referencia × unidades"),
        ("Inventario final", ui.usd(invm.valor.iloc[-1]), f"{invm.periodo.iloc[-1]} · {ui.num(invm.un.iloc[-1])} un"),
        ("SKU con stock", ui.num((s.inv_final > 0).sum()), "al cierre del periodo"),
        ("Cobertura", f"{ui.num(invm.un.iloc[-1] / venta_mes_un, 1)} meses", "inventario final ÷ venta mensual prom."),
        ("Marca más rápida", ui.titulo_caso(rapida.marca), f"rotación {ui.num(rapida.rotacion, 1)} veces · mitad superior en venta"),
    ])

    # --- productos destacados: alta rotación con imagen ---
    st.markdown("### Perfumes de mayor rotación (con venta relevante)")
    dest = s[(s.un >= 10) & (s.inv_prom >= 2) & s.rotacion.notna()].sort_values("rotacion", ascending=False).head(8)
    cards = []
    for r in dest.itertuples():
        alerta = "Quiebre: sin stock" if (r.inv_final or 0) <= 0 else (f"Cobertura {ui.num(r.cobertura_meses, 1)} meses" if pd.notna(r.cobertura_meses) else "")
        cards.append(f'''<div class="fi-card" translate="no" style="background:#5E2A42;color:#F8EAF0"><div class="ph">{ui.foto(r.imagen_url, r.marca, f"Frasco {r.marca} {r.etiqueta}")}</div>
          <div class="br" translate="no" style="color:#E8A0B4">{ui.esc(r.marca)} · ROTACIÓN {ui.num(r.rotacion, 1)}</div>
          <div class="nm" translate="no" style="color:#F8EAF0">{ui.esc(ui.titulo_caso(r.etiqueta))}</div>
          <div class="big" style="color:#fff">{ui.usd(r.venta)}</div>
          <div class="sm" style="color:#F1C9D7">{ui.num(r.un)} un · margen {ui.pct(r.margen_pct, 0)} · stock {ui.num(r.inv_final)} un</div>
          <div class="sm" style="color:{'#FFB3C7' if (r.inv_final or 0) <= 0 else '#F1C9D7'};font-weight:600">{ui.esc(alerta)}</div></div>''')
    st.markdown(f'<div translate="no" style="background:#4A1F33;border-radius:24px;padding:18px"><div class="fi-grid" translate="no">{"".join(cards)}</div></div>',
                unsafe_allow_html=True)
    st.markdown('<div class="fi-note">Rotación = unidades vendidas ÷ inventario promedio en unidades (promedio de cierres mensuales). '
                'Mínimo 10 unidades vendidas e inventario promedio ≥ 2 un (evita rotaciones infladas por denominadores casi cero). El inventario inicial al 01-01-2025 es el mínimo calculado para no tener saldos negativos '
                '(regla de la fase 2), por lo que la rotación de 2025 puede estar sobrestimada.</div>', unsafe_allow_html=True)

    # --- matriz rotación × margen por marca ---
    c1, c2 = st.columns(2)
    with c1:
        m = mb[(mb.venta > 0) & mb.rotacion.notna()].sort_values("venta", ascending=False).head(20)
        xr, ym = m.rotacion.median(), m.margen_pct.median() * 100
        fig = px.scatter(m, x="rotacion", y=m.margen_pct * 100, size="venta", text=m.marca.map(ui.titulo_caso), size_max=46,
                         color_discrete_sequence=[ui.VINO])
        fig.update_traces(textposition="top center", textfont_size=10, marker=dict(opacity=.6, line=dict(color=ui.VINO_OSC, width=1)),
                          hovertemplate="%{text}<br>rotación %{x:.2f} · margen %{y:.1f}%<extra></extra>")
        fig.add_vline(x=xr, line_dash="dot", line_color="#C9AEB8"); fig.add_hline(y=ym, line_dash="dot", line_color="#C9AEB8")
        for tx, x, y, col in [("Estrellas", 1, 1, ui.ORO), ("Baja rotación · alto margen", 0, 1, "#6B4E5A"),
                              ("Alta rotación · bajo margen", 1, 0, "#6B4E5A"), ("Revisar", 0, 0, ui.VINO_OSC)]:
            fig.add_annotation(text=tx, xref="paper", yref="paper", x=x, y=y, showarrow=False, font=dict(color=col, size=11),
                               xanchor="right" if x else "left", yanchor="top" if y else "bottom")
        fig.update_layout(title=dict(text="Matriz rotación vs margen por diseñador (top 20 por venta)", font=dict(family="Cormorant Garamond", size=20)),
                          xaxis_title="Rotación (veces en el periodo)", yaxis_title="Margen bruto %")
        st.plotly_chart(ui.plotly_base(fig, 440, False), use_container_width=True)
        st.markdown('<div class="fi-note">Líneas punteadas = medianas de las marcas mostradas. Tamaño de la burbuja = venta neta.</div>', unsafe_allow_html=True)
    with c2:
        t = mb.sort_values("venta", ascending=False).head(12)
        prom = margen / venta
        fig = go.Figure(go.Bar(y=t.marca.map(ui.titulo_caso)[::-1], x=(t.margen_pct * 100)[::-1], orientation="h",
                               marker_color=[ui.VINO_OSC if x >= prom else ui.ROSA_CL for x in t.margen_pct][::-1],
                               text=[ui.pct(x) for x in t.margen_pct][::-1], textposition="outside",
                               customdata=t[["venta", "margen"]].values[::-1],
                               hovertemplate="%{y}<br>venta $%{customdata[0]:,.0f} · margen $%{customdata[1]:,.0f}<extra></extra>"))
        fig.add_vline(x=prom * 100, line_dash="dot", line_color=ui.VINO)
        fig.update_layout(title=dict(text="Margen % por diseñador (top 12 por venta)", font=dict(family="Cormorant Garamond", size=20)),
                          xaxis=dict(ticksuffix="%", range=[0, max(70, t.margen_pct.max() * 110)]))
        st.plotly_chart(ui.plotly_base(fig, 440, False), use_container_width=True)
        st.markdown(f'<div class="fi-note">Oscuro = sobre el margen promedio ({ui.pct(prom)}); rosa = por debajo.</div>', unsafe_allow_html=True)

    # --- cuadrantes a nivel perfume ---
    st.markdown("### Alta rotación · bajo margen vs baja rotación · alto margen (por perfume)")
    min_un = st.slider("Mínimo de unidades vendidas para entrar al análisis", 1, 30, 5, key="rent_min")
    b = s[(s.un >= min_un) & s.rotacion.notna() & s.margen_pct.notna()].copy()
    if len(b) >= 4:
        rr, mm = b.rotacion.median(), b.margen_pct.median()
        cols = ["etiqueta", "marca", "un", "rotacion", "precio", "costo_un", "margen_pct", "venta"]
        cfg = {"etiqueta": "Perfume", "marca": "Marca", "un": "Un", "rotacion": st.column_config.NumberColumn("Rotación", format="%.2f"),
               "precio": st.column_config.NumberColumn("Precio prom.", format="$%.0f"),
               "costo_un": st.column_config.NumberColumn("Costo un.", format="$%.0f"),
               "margen_pct": st.column_config.NumberColumn("Margen %", format="%.3f"),
               "venta": st.column_config.NumberColumn("Venta", format="$%.0f")}
        a1, a2 = st.columns(2)
        a1.markdown(f'**Mucha rotación, margen bajo** <span class="fi-note">(rotación ≥ {ui.num(rr, 2)} y margen < {ui.pct(mm)})</span>', unsafe_allow_html=True)
        a1.dataframe(b[(b.rotacion >= rr) & (b.margen_pct < mm)].sort_values("un", ascending=False)[cols].head(12),
                     hide_index=True, width="stretch", column_config=cfg)
        a1.markdown('<div class="fi-note">Candidatos a renegociar costo o revisar precio.</div>', unsafe_allow_html=True)
        a2.markdown(f'**Poca rotación, margen alto** <span class="fi-note">(rotación < {ui.num(rr, 2)} y margen ≥ {ui.pct(mm)})</span>', unsafe_allow_html=True)
        a2.dataframe(b[(b.rotacion < rr) & (b.margen_pct >= mm)].sort_values("margen_pct", ascending=False)[cols].head(12),
                     hide_index=True, width="stretch", column_config=cfg)
        a2.markdown('<div class="fi-note">Oportunidad de impulso comercial; validar costos muy bajos antes de concluir.</div>', unsafe_allow_html=True)

    # --- precio facturado vs lista (costo × 2,5) ---
    c3, c4 = st.columns(2)
    with c3:
        w, p = f.where()
        cl = q(f"""SELECT COALESCE(comparacion_lista,'SIN DATO') comp, count(*) lineas, SUM(venta_neta) venta
                   FROM f_ventas WHERE {w} AND mov='FACT' GROUP BY 1 ORDER BY lineas DESC""", p)
        fig = px.bar(cl, x="lineas", y="comp", orientation="h", color_discrete_sequence=[ui.ROSA], text="lineas")
        fig.update_layout(title=dict(text="Precio facturado vs precio de lista (costo × 2,5)", font=dict(family="Cormorant Garamond", size=20)),
                          yaxis_title=None, xaxis_title="Líneas de factura")
        st.plotly_chart(ui.plotly_base(fig, 320, False), use_container_width=True)
        st.markdown('<div class="fi-note">Tolerancia ±5%. "Lista con IVA" = lista × 1,16. La mayoría de las ventas se factura por debajo de la lista teórica.</div>',
                    unsafe_allow_html=True)
    with c4:
        fig = go.Figure(go.Bar(x=invm.periodo, y=invm.valor, marker_color=[ui.ROSA if x < "2026" else ui.VINO for x in invm.periodo],
                               hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
        fig.update_layout(title=dict(text="Valor del inventario al cierre de cada mes (a costo)", font=dict(family="Cormorant Garamond", size=20)),
                          yaxis_title="USD")
        st.plotly_chart(ui.plotly_base(fig, 320, False), use_container_width=True)

    with st.expander("Tabla de rentabilidad y rotación por SKU (trazabilidad)"):
        st.dataframe(s.drop(columns=["imagen_url"]).sort_values("venta", ascending=False), hide_index=True, width="stretch")
        st.download_button("Descargar CSV", s.to_csv(index=False).encode("utf-8"), "rentabilidad_sku.csv", "text/csv")
