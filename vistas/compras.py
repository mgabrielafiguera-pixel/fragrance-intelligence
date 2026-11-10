"""Pantalla 2 · Compras y abastecimiento: volumen, costos por tipo, reposición y ciclo de caja."""
import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from lib.db import comparacion_costos_abastecimiento, q
from lib import ui


ESTACIONALIDAD = ui.BASE / "data" / "r_outputs" / "estacionalidad.csv"


def _indices_estacionales() -> tuple[dict[int, float], list[int]]:
    if not ESTACIONALIDAD.exists():
        return {mes: 1.0 for mes in range(1, 13)}, []

    datos = pd.read_csv(ESTACIONALIDAD)
    if not {"mes", "indice"}.issubset(datos.columns):
        st.error("data/r_outputs/estacionalidad.csv debe contener las columnas mes e indice.")
        st.stop()

    datos = datos[["mes", "indice"]].copy()
    datos["mes"] = pd.to_numeric(datos["mes"], errors="coerce")
    datos["indice"] = pd.to_numeric(datos["indice"], errors="coerce")
    validos = (
        datos["mes"].notna().all()
        and datos["indice"].notna().all()
        and datos["mes"].between(1, 12).all()
        and (datos["mes"] % 1 == 0).all()
        and datos["indice"].map(math.isfinite).all()
        and (datos["indice"] >= 0).all()
        and not datos["mes"].duplicated().any()
    )
    if not validos:
        st.error("data/r_outputs/estacionalidad.csv contiene meses o índices inválidos o duplicados.")
        st.stop()

    indices = dict(zip(datos["mes"].astype(int), datos["indice"].astype(float)))
    faltantes = sorted(set(range(1, 13)) - set(indices))
    indices.update({mes: 1.0 for mes in faltantes})
    return indices, faltantes


def render():
    f = st.session_state["filtros"]
    w, p = f.where()
    ui.titulo(f"Costo nacionalizado · {f.desde[:7]} a {f.hasta[:7]}", "Compras y abastecimiento", f.descripcion)

    k = q(f"""SELECT SUM(total_costo_nac) compras, SUM(unidades) un, SUM(total_costo_exw) exw,
                     count(DISTINCT tipo_proveedor) tipos, count(DISTINCT documento) docs,
                     SUM(total_costo_nac) FILTER (WHERE tipo_proveedor='INTERNACIONAL') intl
              FROM f_compras WHERE {w}""", p).iloc[0]
    if pd.isna(k.compras):
        st.warning("No hay compras con los filtros seleccionados."); return
    pv = q(f"""SELECT c.tipo_proveedor, any_value(d.condicion_pago) condicion_pago,
                      SUM(total_costo_nac) compras, SUM(unidades) un, SUM(total_costo_nac)/NULLIF(SUM(unidades),0) cpu,
                      count(DISTINCT p.marca) marcas, count(DISTINCT c.sku) skus,
                      AVG(factor_nacionalizacion) FILTER (WHERE c.tipo_proveedor='INTERNACIONAL') factor
               FROM f_compras c JOIN dim_producto p USING (sku)
               LEFT JOIN dim_proveedor d ON c.tipo_proveedor = d.tipo_proveedor
               WHERE {w.replace('fecha', 'c.fecha')} GROUP BY c.tipo_proveedor ORDER BY compras DESC""", p)
    pv["share"] = pv.compras / pv.compras.sum()
    vend = q(f"SELECT SUM(unidades) un FROM f_ventas WHERE {w}", p).un.iloc[0]
    ui.kpis([
        ("Compras totales", ui.usd(k.compras), "a costo nacionalizado"),
        ("Unidades compradas", ui.num(k.un), f"vs {ui.num(vend)} vendidas"),
        ("Costo promedio", ui.usd(k.compras / k.un, 1), "por unidad adquirida"),
        ("Tipos de abastecimiento", ui.num(k.tipos), "Nacional e Internacional"),
        ("Mayor participación", ui.pct(pv.share.iloc[0]), pv.tipo_proveedor.iloc[0].title()),
        ("Compras internacionales", ui.pct((k.intl or 0) / k.compras), "pagadas de contado"),
    ])

    st.markdown("### Volumen de compras por tipo de abastecimiento")
    tabla = pv.assign(Tipo=pv.tipo_proveedor.str.title())[
        ["Tipo", "condicion_pago", "compras", "share", "un", "cpu", "factor", "marcas", "skus"]]
    st.dataframe(tabla, hide_index=True, width="stretch", column_config={
        "Tipo": "Tipo de abastecimiento", "condicion_pago": "Condición de pago",
        "compras": st.column_config.NumberColumn("Compras", format="$%.0f"),
        "share": st.column_config.ProgressColumn("Participación", format="%.3f", min_value=0, max_value=1),
        "un": st.column_config.NumberColumn("Unidades", format="%.0f"),
        "cpu": st.column_config.NumberColumn("Costo prom./un", format="$%.1f"),
        "factor": st.column_config.NumberColumn("Factor nacionalización", format="%.3f", help="Costo nacionalizado ÷ Ex Works (solo internacionales)"),
        "marcas": "N.º de marcas", "skus": "SKU"})
    if pv.share.iloc[0] > 0.5:
        st.markdown(
            f'<div class="fi-alert" translate="no">Concentración por tipo: '
            f'{pv.tipo_proveedor.iloc[0].title()} representa {ui.pct(pv.share.iloc[0])} de las compras del periodo.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Simulación de acción · dependencia y quiebre de stock")
    meses_objetivo = st.slider("Cobertura objetivo para la simulación (meses)", 1, 6, 2, key="reposicion_meses")
    ajustar_estacionalidad = st.toggle("Ajustar por estacionalidad", value=True, key="reposicion_estacionalidad")
    indices, meses_indice_faltantes = _indices_estacionales()
    if not ESTACIONALIDAD.exists():
        st.caption("No existe data/r_outputs/estacionalidad.csv; se usa índice estacional 1 para todos los meses.")
    elif meses_indice_faltantes:
        st.caption(
            "Faltan índices para los meses "
            + ", ".join(map(str, meses_indice_faltantes))
            + "; para esos meses se usa índice 1."
        )
    wv, pvta = f.where("v.fecha", "v.sku")
    wi, pi = f.where_periodo()
    wc, pc = f.where("c.fecha", "c.sku")
    meses_periodo = (pd.Period(f.hasta[:7], freq="M") - pd.Period(f.desde[:7], freq="M")).n + 1
    primer_mes_demanda = pd.Period(f.hasta[:7], freq="M") + 1
    meses_demanda = [primer_mes_demanda + offset for offset in range(meses_objetivo)]
    indice_objetivo = sum(indices[mes.month] for mes in meses_demanda)
    plan = q(f"""WITH inventario AS (
                    SELECT sku, arg_max(inv_final_un, periodo) AS stock, max(periodo) AS periodo_stock
                    FROM f_inventario WHERE {wi} GROUP BY sku
                 ), ventas AS (
                    SELECT v.sku, SUM(v.unidades) AS unidades, SUM(v.venta_neta) AS venta
                    FROM f_ventas v WHERE {wv} GROUP BY v.sku
                 ), compras_sku AS (
                    SELECT c.sku, c.tipo_proveedor, SUM(c.total_costo_nac) AS importe,
                           MAX(c.fecha) AS ultima_compra
                    FROM f_compras c WHERE {wc} GROUP BY c.sku, c.tipo_proveedor
                 ), tipo_sku AS (
                    SELECT *, ROW_NUMBER() OVER (
                               PARTITION BY sku ORDER BY importe DESC, ultima_compra DESC, tipo_proveedor
                           ) AS rn,
                           SUM(importe) OVER (PARTITION BY sku) AS total_sku
                    FROM compras_sku
                 )
                 SELECT p.sku, p.marca, p.etiqueta, v.unidades, v.venta, i.stock, i.periodo_stock,
                        ps.tipo_proveedor AS tipo_abastecimiento,
                        ps.importe / NULLIF(ps.total_sku, 0) AS share_tipo
                 FROM ventas v JOIN dim_producto p USING (sku)
                 JOIN inventario i USING (sku)
                 LEFT JOIN tipo_sku ps ON ps.sku = p.sku AND ps.rn = 1
                 WHERE i.stock <= 0 AND v.unidades > 0
                 ORDER BY v.venta DESC""", pvta | pi | pc)
    if plan.empty:
        st.info("No hay fragancias con ventas y stock agotado en el periodo y filtros seleccionados.")
    else:
        plan = plan.head(10).copy()
        plan["un_mes"] = plan.unidades / max(meses_periodo, 1)
        plan["reponer_sin_ajuste"] = (
            plan.un_mes * meses_objetivo - plan.stock
        ).apply(lambda x: max(0, math.ceil(x)))
        plan["reponer_ajustado"] = (
            plan.un_mes * indice_objetivo - plan.stock
        ).apply(lambda x: max(0, math.ceil(x)))
        plan["reponer_sugerido"] = (
            plan["reponer_ajustado"] if ajustar_estacionalidad else plan["reponer_sin_ajuste"]
        )
        plan["share_tipo_texto"] = plan.share_tipo.map(ui.pct)
        tipo_mayor = pv.tipo_proveedor.iloc[0]
        plan["accion"] = plan.apply(
            lambda r: "Validar tipo de abastecimiento" if pd.isna(r.tipo_abastecimiento)
            else (f"Revisar concentración en {r.tipo_abastecimiento.title()}"
                  if r.tipo_abastecimiento == tipo_mayor and r.share_tipo >= 0.999
                  else f"Evaluar reposición por vía {r.tipo_abastecimiento.title()}"),
            axis=1)
        unidades_sugeridas = plan.reponer_sugerido.sum()
        sku_dependientes = (plan.tipo_abastecimiento == tipo_mayor).sum()
        st.markdown(
            f"**{ui.num(unidades_sugeridas)} unidades en {len(plan)} SKU; "
            f"{ui.num(sku_dependientes)} se abastecen principalmente por vía {tipo_mayor.title()}, "
            f"que representa {ui.pct(pv.share.iloc[0])} de las compras filtradas.**"
        )
        tabla_plan = plan[["sku", "marca", "etiqueta", "unidades", "stock", "un_mes",
                           "reponer_ajustado", "reponer_sin_ajuste",
                           "tipo_abastecimiento", "share_tipo_texto", "accion"]]
        st.dataframe(tabla_plan, hide_index=True, width="stretch", column_config={
            "sku": "SKU", "marca": "Marca", "etiqueta": "Fragancia",
            "unidades": st.column_config.NumberColumn("Unidades vendidas", format="%.0f"),
            "stock": st.column_config.NumberColumn("Stock al cierre", format="%.0f"),
            "un_mes": st.column_config.NumberColumn("Venta mensual prom.", format="%.1f"),
            "reponer_ajustado": st.column_config.NumberColumn("Reposición con estacionalidad", format="%.0f"),
            "reponer_sin_ajuste": st.column_config.NumberColumn("Reposición sin estacionalidad", format="%.0f"),
            "tipo_abastecimiento": "Tipo predominante",
            "share_tipo_texto": "Participación de ese tipo",
            "accion": "Acción sugerida",
        })
        st.caption(
            f"Estimación: ventas netas de unidades divididas entre los {meses_periodo} meses calendario incluidos; "
            f"objetivo de {meses_objetivo} meses desde {meses_demanda[0]} hasta {meses_demanda[-1]}, "
            f"considerando el stock de cierre de {plan.periodo_stock.max()}. "
            "El tipo predominante es el de mayor monto total comprado para ese SKU (Σ costo nacionalizado) "
            "en el periodo filtrado; si hay empate, se elige la compra más reciente. "
            f"El interruptor define la sugerencia activa; se muestran ambos escenarios. "
            "No incluye tiempos de entrega ni órdenes en tránsito y no crea pedidos.")

    c1, c2 = st.columns(2)
    # --- compras mensuales por tipo de abastecimiento ---
    with c1:
        m = q(f"""SELECT periodo, (upper(tipo_proveedor[1]) || lower(tipo_proveedor[2:])) tipo, SUM(total_costo_nac) v FROM f_compras WHERE {w}
                  GROUP BY 1,2 ORDER BY 1""", p)
        fig = px.bar(m, x="periodo", y="v", color="tipo", color_discrete_map={"Nacional": ui.VINO, "Internacional": ui.AZUL})
        fig.update_layout(title=dict(text="Compras mensuales (USD, costo nacionalizado)", font=dict(family="Cormorant Garamond", size=22)),
                          xaxis_title=None, yaxis_title=None, barmode="stack")
        st.plotly_chart(ui.plotly_base(fig, 360), use_container_width=True)
    # --- concentración por marca y tipo de abastecimiento ---
    with c2:
        dep = q(f"""WITH t AS (
                        SELECT p.marca, c.tipo_proveedor, SUM(total_costo_nac) v
                        FROM f_compras c JOIN dim_producto p USING (sku)
                        WHERE {w.replace('fecha', 'c.fecha')} GROUP BY 1,2
                    )
                    SELECT marca, SUM(v) compras, MAX(v)/SUM(v) share_tipo,
                           arg_max(tipo_proveedor, v) tipo_principal, count(*) n_tipos
                    FROM t GROUP BY 1 ORDER BY compras DESC LIMIT 12""", p)
        fig = go.Figure(go.Bar(
            y=[ui.titulo_caso(x) for x in dep.marca][::-1],
            x=(dep.share_tipo * 100)[::-1],
            orientation="h",
            marker_color=[ui.VINO_OSC if share >= .999 else ui.ROSA for share in dep.share_tipo][::-1],
            customdata=dep[["tipo_principal", "n_tipos", "compras"]].values[::-1],
            hovertemplate="%{y}: %{x:.0f}% por vía %{customdata[0]} (%{customdata[1]} tipos)<extra></extra>",
        ))
        fig.update_layout(title=dict(text="Concentración por tipo de abastecimiento para cada marca",
                                     font=dict(family="Cormorant Garamond", size=20)), xaxis=dict(range=[0, 105], ticksuffix="%"))
        st.plotly_chart(ui.plotly_base(fig, 360, False), use_container_width=True)
        st.markdown('<div class="fi-note">Muestra la proporción comprada por el tipo principal de abastecimiento. Top 12 marcas por compras.</div>',
                    unsafe_allow_html=True)

    st.markdown("### Comparación del mismo SKU · Nacional vs Internacional")
    sku_sql, params_sku = f.sku_sql("v.sku")
    comparacion, base_comparacion = comparacion_costos_abastecimiento(
        sku_sql, params_sku, f.desde, f.hasta
    )
    if comparacion.empty:
        st.info("No hay SKU comprados por ambas vías con los filtros y el historial disponibles.")
    else:
        mediana = float(comparacion.brecha.median())
        cA, cB = st.columns([1, 2])
        cA.markdown(
            f'<div class="fi-panel" translate="no"><div style="font-size:12px;color:#59414B;font-weight:600">'
            f'Brecha mediana (Nacional / Internacional − 1)</div>'
            f'<div style="font-family:Cormorant Garamond,serif;font-size:30px;font-weight:700;color:#5E2139">'
            f'{ui.pct(mediana, signo=True)}</div>'
            f'<div class="fi-note">Base: {base_comparacion}; {len(comparacion)} SKU comparados. '
            'Una brecha positiva indica mayor costo nacionalizado por vía Nacional.</div></div>',
            unsafe_allow_html=True,
        )
        fig = go.Figure(go.Bar(
            x=comparacion.brecha * 100,
            y=comparacion.sku,
            orientation="h",
            marker_color=ui.ROSA,
            customdata=comparacion[["costo_nacional", "costo_internacional"]].values,
            hovertemplate="SKU %{y}<br>Brecha: %{x:.1f}%<br>Nacional: $%{customdata[0]:.2f}"
            "<br>Internacional: $%{customdata[1]:.2f}<extra></extra>",
        ))
        fig.update_layout(
            title=dict(text="Brecha de costo nacionalizado por SKU", font=dict(family="Cormorant Garamond", size=20)),
            xaxis_title="Nacional vs Internacional (%)",
            yaxis_title=None,
        )
        cB.plotly_chart(ui.plotly_base(fig, max(320, len(comparacion) * 28), False), use_container_width=True)

    # --- ciclo de caja: cobros de clientes y pagos por tipo ---
    st.markdown("### Ciclo de caja: cobros de clientes y pagos por tipo de abastecimiento")
    ws, ps = f.sku_sql()
    pag = q(f"""SELECT strftime(fecha_pago,'%Y-%m') periodo, (upper(tipo_proveedor[1]) || lower(tipo_proveedor[2:])) tipo, SUM(monto) v
                FROM f_pagos WHERE {ws} AND fecha_pago BETWEEN CAST($d AS DATE) AND CAST($h AS DATE) GROUP BY 1,2""",
            ps | {"d": f.desde, "h": f.hasta})
    cob = q(f"""SELECT strftime(fecha_cobro,'%Y-%m') periodo, SUM(cobro_neto) v, SUM(comision_pos) com FROM f_ventas
                WHERE {ws} AND fecha_cobro BETWEEN CAST($d AS DATE) AND CAST($h AS DATE) GROUP BY 1""", ps | {"d": f.desde, "h": f.hasta})
    fig = go.Figure()
    fig.add_bar(x=cob.periodo, y=cob.v, name="Cobros netos de clientes", marker_color=ui.AZUL)
    for t, col in [("Nacional", ui.VINO), ("Internacional", ui.AZUL)]:
        d = pag[pag.tipo == t]
        fig.add_bar(x=d.periodo, y=-d.v, name=f"Pagos vía {t.lower()}", marker_color=col)
    fig.update_layout(barmode="relative", yaxis_title="USD (pagos en negativo)")
    st.plotly_chart(ui.plotly_base(fig, 380), use_container_width=True)

    cc1, cc2 = st.columns(2)
    cond = q(f"""SELECT condicion_pago, medio_cobro, SUM(venta_neta) venta, SUM(comision_pos) comision, SUM(cobro_neto) neto
                 FROM f_ventas WHERE {w} GROUP BY ALL ORDER BY venta DESC""", p)
    tot = cond.venta.sum()
    contado = cond[cond.condicion_pago == "CONTADO"].venta.sum()
    cc1.markdown(f'''<div class="fi-panel"><h3 style="margin:0;font-size:22px">Cobro de ventas: contado vs crédito</h3>
        <div style="display:flex;height:30px;border-radius:10px;overflow:hidden;margin:10px 0">
        <div style="width:{contado / tot * 100:.1f}%;background:#8E3B5A"></div><div style="flex:1;background:#E8A0B4"></div></div>
        <div style="display:flex;justify-content:space-between;font-size:13px"><span><b>Contado {ui.pct(contado / tot)}</b> · {ui.usd(contado)}</span>
        <span><b>Crédito 30 días (VIP/accionistas) {ui.pct(1 - contado / tot)}</b> · {ui.usd(tot - contado)}</span></div>
        <div class="fi-note" style="margin-top:8px">Comisión de punto de venta (2,5%): <b>{ui.usd(cond.comision.sum())}</b>.
        Contado: 30% efectivo y 70% punto de venta por factura (supuesto documentado en REGLAS).</div></div>''', unsafe_allow_html=True)
    pg = q(f"""SELECT (upper(tipo_proveedor[1]) || lower(tipo_proveedor[2:])) tipo, origen, SUM(monto) monto FROM f_pagos
               WHERE {ws} AND fecha_pago BETWEEN CAST($d AS DATE) AND CAST($h AS DATE) GROUP BY ALL ORDER BY monto DESC""",
           ps | {"d": f.desde, "h": f.hasta})
    cc2.markdown('<div class="fi-panel"><h3 style="margin:0 0 6px;font-size:22px">Pagos por tipo de abastecimiento</h3>'
                 '<div class="fi-note">Nacional: crédito contra venta (la obligación nace al vender). '
                 'Internacional: contado antes del despacho (fecha de invoice).</div></div>', unsafe_allow_html=True)
    cc2.dataframe(pg, hide_index=True, width="stretch",
                  column_config={"monto": st.column_config.NumberColumn("Monto", format="$%.0f")})
