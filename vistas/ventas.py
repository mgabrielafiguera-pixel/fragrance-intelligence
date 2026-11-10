"""Pantalla 1 · Ventas: rankings, Top 10 con imagen, participación y share ganado/perdido, evolución mensual."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from lib.db import q, ranking, NIVELES
from lib import ui


def _logos() -> dict:
    return dict(q("SELECT marca, logo_url FROM dim_marca WHERE logo_url IS NOT NULL").values)


def render():
    f = st.session_state["filtros"]
    w, p = f.where()
    ui.titulo(f"Belleza · Fragancias · {f.desde[:7]} a {f.hasta[:7]}", "Desempeño comercial", f.descripcion)

    tot = q(f"""SELECT SUM(venta_neta) venta, SUM(unidades) un, SUM(margen_bruto) mg,
                    SUM(venta_neta) FILTER (WHERE anio=2025) v25, SUM(venta_neta) FILTER (WHERE anio=2026) v26,
                    SUM(-unidades) FILTER (WHERE mov='N/CR') dev, count(DISTINCT factura) FILTER (WHERE mov='FACT') facturas
                FROM f_ventas WHERE {w}""", p).iloc[0]
    if pd.isna(tot.venta):
        st.warning("No hay ventas con los filtros seleccionados."); return
    marca_l = q(f"""SELECT marca, SUM(venta_neta) v FROM f_ventas JOIN dim_producto USING (sku) WHERE {w}
                    GROUP BY 1 ORDER BY 2 DESC LIMIT 1""", p).iloc[0]
    frag_l = ranking(f, "Fragancia (versión)", "unidades", 1).iloc[0]
    yoy = (tot.v26 / tot.v25 - 1) if tot.v25 and tot.v26 and not pd.isna(tot.v25) and not pd.isna(tot.v26) else None
    ui.kpis([
        ("Ventas netas", ui.usd(tot.venta), f"2026 vs 2025: {ui.pct(yoy, 1, True)}" if yoy is not None else "periodo filtrado"),
        ("Unidades vendidas", ui.num(tot.un), f"netas de {ui.num(tot.dev or 0)} un devueltas"),
        ("Marca líder", ui.titulo_caso(marca_l.marca), f"{ui.pct(marca_l.v / tot.venta)} de los ingresos"),
        ("Fragancia líder (un)", ui.titulo_caso(frag_l.nombre), f"{ui.titulo_caso(frag_l.marca)} · {ui.num(frag_l.unidades)} un"),
        ("Precio promedio", ui.usd(tot.venta / tot.un), "venta neta ÷ unidades"),
        ("Margen bruto", ui.pct(tot.mg / tot.venta), f"{ui.usd(tot.mg)} de margen"),
    ])

    c1, c2 = st.columns([3, 1])
    nivel = c2.selectbox("Nivel del ranking", list(NIVELES), index=4, key="nivel_rank",
                         help="Marca > Colección > Modelo > Versión > SKU. 'Diseñador' = campo MARCA del maestro.")
    logos = _logos()

    # --- tarjetas héroe: líder en unidades y en ingresos ---
    lu = ranking(f, nivel, "unidades", 1).iloc[0]
    li = ranking(f, nivel, "venta", 1).iloc[0]

    def hero(r, clase, tag):
        return f'''<div class="fi-hcard {clase}" translate="no"><div class="ph">{ui.foto(r.imagen_url, r.marca, f"Frasco {r.marca} {r.nombre}")}</div>
        <div style="flex:1 1 200px" translate="no">{ui.logo_html(logos.get(r.marca), r.marca)}
        <div class="tag" translate="no">{ui.esc(tag)}</div><div class="nm" translate="no">{ui.esc(ui.titulo_caso(r.nombre))}</div>
        <div class="sb" translate="no">{ui.esc(ui.titulo_caso(r.marca))}{' · ' + str(int(r.n_sku)) + ' SKU' if r.n_sku > 1 else ''}</div>
        <div class="nums"><div><b>{ui.num(r.unidades)}</b><span>unidades</span></div><div><b>{ui.usd(r.venta)}</b><span>ingresos</span></div>
        <div><b>{ui.pct(r.margen_pct, 0)}</b><span>margen</span></div></div></div></div>'''
    st.markdown(f'<div class="fi-hero" translate="no">{hero(lu, "dark", "LÍDER EN UNIDADES")}{hero(li, "light", "LÍDER EN INGRESOS")}</div>',
                unsafe_allow_html=True)

    # --- Top 10 con imagen ---
    st.markdown(f"### Top 10 · {nivel.lower()}")
    t1, t2, t3, t4 = st.tabs(["Por unidades", "Por ingresos", "Por margen bruto $", "Por margen % (mín. 10 un)"])
    descargas = {}
    for tab, orden, et in [(t1, "unidades", "unidades"), (t2, "venta", "ingresos"), (t3, "margen", "margen"), (t4, "margen_pct", "margen %")]:
        with tab:
            df = ranking(f, nivel, orden, 10, min_un=10 if orden == "margen_pct" else 0)
            ui.tarjetas(df, orden, et, logos)
            descargas[orden] = df
    with st.expander("Ver tabla del ranking (trazabilidad)"):
        d = ranking(f, nivel, "venta", 50)
        st.dataframe(d.drop(columns=["imagen_url"]), hide_index=True, width="stretch",
                     column_config={"venta": st.column_config.NumberColumn("Venta neta", format="$%.0f"),
                                    "margen": st.column_config.NumberColumn("Margen bruto", format="$%.0f"),
                                    "costo": st.column_config.NumberColumn("Costo de ventas", format="$%.0f"),
                                    "margen_pct": st.column_config.NumberColumn("Margen %", format="%.3f"),
                                    "precio_prom": st.column_config.NumberColumn("Precio prom.", format="$%.1f")})
        st.download_button("Descargar CSV", d.to_csv(index=False).encode("utf-8"), "ranking_ventas.csv", "text/csv")

    # --- marcas: top 10 con logo + participación + share ganado/perdido ---
    col_a, col_b = st.columns(2)
    br = q(f"""SELECT marca, SUM(venta_neta) venta, SUM(margen_bruto)/NULLIF(SUM(venta_neta),0) mg
               FROM f_ventas JOIN dim_producto USING (sku) WHERE {w} GROUP BY 1 ORDER BY 2 DESC""", p)
    with col_a:
        top = br.head(10)
        mx = top.venta.max()
        filas = "".join(f'''<div class="fi-brandrow" translate="no"><div>{ui.logo_html(logos.get(r.marca), r.marca, "") or f"<span translate='no' style='font-size:11px;font-weight:600'>{ui.esc(r.marca)}</span>"}</div>
            <div class="b"><div style="width:{r.venta / mx * 100:.0f}%"></div></div><div style="text-align:right;font-weight:600">{ui.usd(r.venta)}</div></div>'''
                        for r in top.itertuples())
        st.markdown(f'<div class="fi-panel" translate="no"><h3 style="margin:0 0 8px;font-size:22px">Top 10 diseñadores por ventas</h3>{filas}</div>',
                    unsafe_allow_html=True)
    with col_b:
        k = 5
        sh = br.copy(); sh["share"] = sh.venta / sh.venta.sum()
        top5 = sh.head(k)[["marca", "share"]]
        resto = pd.DataFrame([{"marca": f"Otras {len(sh) - k} marcas", "share": sh.share.iloc[k:].sum()}]) if len(sh) > k else pd.DataFrame()
        pie = pd.concat([top5, resto])
        fig = go.Figure(go.Pie(labels=[ui.titulo_caso(m) for m in pie.marca], values=pie.share, hole=.62, sort=False,
                               marker=dict(colors=ui.SERIE[:len(top5)] + [ui.GRIS]), textinfo="percent",
                               hovertemplate="%{label}: %{percent}<extra></extra>"))
        fig = ui.plotly_base(fig, 360)
        fig.update_layout(title=dict(text="Participación en ingresos", font=dict(family="Cormorant Garamond", size=22)),
                          legend=dict(orientation="v", x=1.0, y=0.5, xanchor="left", yanchor="middle"), margin=dict(t=50))
        st.plotly_chart(fig, use_container_width=True)

    # share ganado / perdido: 2026 vs 2025 con los mismos filtros de producto (ignora el rango de fechas)
    ws, ps = f.sku_sql()
    sy = q(f"""WITH t AS (SELECT marca, anio, SUM(venta_neta) v FROM f_ventas JOIN dim_producto USING (sku) WHERE {ws} GROUP BY 1,2),
               s AS (SELECT marca, anio, v / SUM(v) OVER (PARTITION BY anio) sh FROM t)
               SELECT marca, COALESCE(MAX(sh) FILTER (WHERE anio=2025),0) s25, COALESCE(MAX(sh) FILTER (WHERE anio=2026),0) s26
               FROM s GROUP BY 1""", ps)
    sy["delta_pp"] = (sy.s26 - sy.s25) * 100
    sy = sy.sort_values("delta_pp")
    sel = pd.concat([sy.head(5), sy.tail(5)]).drop_duplicates("marca")
    sel = sel[sel.delta_pp.abs() > 0.005]
    if len(sel):
        fig = go.Figure(go.Bar(x=sel.delta_pp, y=[ui.titulo_caso(m) for m in sel.marca], orientation="h",
                               marker_color=[ui.VERDE if d > 0 else ui.ROJO for d in sel.delta_pp],
                               text=[ui._es(f"{d:+.1f}") for d in sel.delta_pp], textposition="outside",
                               customdata=sel[["s25", "s26"]] * 100,
                               hovertemplate="%{y}<br>2025: %{customdata[0]:.1f}% → 2026: %{customdata[1]:.1f}%<extra></extra>"))
        fig.update_layout(title=dict(text="Share ganado y perdido · 2026 vs 2025 (puntos porcentuales)",
                                     font=dict(family="Cormorant Garamond", size=22)))
        st.plotly_chart(ui.plotly_base(fig, 360, False), use_container_width=True)
        st.markdown('<div class="fi-note">Este gráfico aplica los filtros de producto, pero ignora el rango de fechas seleccionado: '
                    'compara siempre los dos años completos (2025 y 2026).</div>', unsafe_allow_html=True)

    # --- evolución mensual ---
    st.markdown("### Evolución mensual")
    c1, c2 = st.columns([1, 3])
    met = c1.radio("Métrica", ["Venta neta", "Unidades", "Margen bruto"], key="evo_met")
    col = {"Venta neta": "venta_neta", "Unidades": "unidades", "Margen bruto": "margen_bruto"}[met]
    top5 = br.head(5).marca.tolist()
    ev = q(f"""SELECT periodo, CASE WHEN list_contains($top, marca) THEN marca ELSE 'OTRAS' END AS marca, SUM({col}) val
               FROM f_ventas JOIN dim_producto USING (sku) WHERE {w} GROUP BY 1,2 ORDER BY 1""", p | {"top": top5})
    ev["marca"] = ev.marca.map(ui.titulo_caso)
    orden = [ui.titulo_caso(m) for m in top5] + ["Otras"]
    fig = px.line(ev, x="periodo", y="val", color="marca", category_orders={"marca": orden},
                  color_discrete_sequence=ui.SERIE[:5] + [ui.GRIS], markers=True)
    fig.update_traces(line_width=2.4, marker_size=5)
    fig.update_layout(yaxis_title=met + (" (USD)" if col != "unidades" else ""), xaxis_title=None)
    if f.desde[:4] != f.hasta[:4]:
        fig.add_vline(x="2026-01", line_dash="dot", line_color="#D9C2CA")
    c2.plotly_chart(ui.plotly_base(fig, 380), use_container_width=True)
    mtot = ev.groupby("periodo").val.sum()
    if len(mtot) >= 3:
        pico = mtot.idxmax()
        c1.markdown(f'<div class="fi-note">Mes pico del periodo: <b>{pico}</b> con {ui.usd(mtot.max()) if col != "unidades" else ui.num(mtot.max()) + " un"} '
                    f'({ui.pct(mtot.max() / mtot.sum())} del total). Top 5 marcas por venta en el periodo filtrado.</div>',
                    unsafe_allow_html=True)
