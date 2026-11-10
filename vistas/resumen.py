"""Resumen gerencial anual: indicadores, alertas, podio y plan de acción."""
import calendar

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import ui
from lib.db import comparacion_costos_abastecimiento, q


QUIEBRE_TOP_SKU = 50
QUIEBRE_MIN_SKU = 10
INVENTARIO_CAIDA_MIN = 0.30
LIDER_CAIDA_MIN = 0.10
BRECHA_PROVEEDOR_MIN = 0.20
DESCUENTO_MIN = 0.25
VIP_CLIENTES_MIN = 1
SELL_THROUGH_MIN_UNIDADES = 40

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def _anio_metricas(anio, sku_sql, params):
    return q(f"""
        SELECT COUNT(*) AS lineas,
               SUM(v.venta_neta) AS venta,
               SUM(v.margen_bruto) AS margen,
               SUM(v.unidades) AS unidades,
               COUNT(DISTINCT v.factura) FILTER (WHERE v.mov='FACT') AS facturas,
               COUNT(DISTINCT v.cod_cliente) AS clientes,
               COUNT(DISTINCT v.cod_cliente) FILTER (
                   WHERE v.mov='FACT' AND v.cliente_vip='SI'
               ) AS clientes_vip,
               SUM(v.venta_neta) FILTER (
                   WHERE v.mov='FACT' AND v.precio_lista > 0
               ) AS venta_con_lista,
               SUM(v.precio_lista * v.unidades) FILTER (
                   WHERE v.mov='FACT' AND v.precio_lista > 0
               ) AS valor_lista,
               SUM(v.venta_neta) FILTER (
                   WHERE v.mov='FACT' AND v.cliente_vip='SI'
               ) AS venta_vip
        FROM f_ventas v
        WHERE v.anio={int(anio)} AND {sku_sql}
    """, params).iloc[0].to_dict()


def _nuevos_clientes(anio, sku_sql, params):
    return int(q(f"""
        WITH primera AS (
            SELECT v.cod_cliente, MIN(v.anio) AS primer_anio
            FROM f_ventas v
            WHERE v.mov='FACT' AND v.cod_cliente IS NOT NULL AND {sku_sql}
            GROUP BY v.cod_cliente
        )
        SELECT COUNT(*) AS cantidad FROM primera WHERE primer_anio={int(anio)}
    """, params).iloc[0].cantidad)


def _delta(actual, anterior, tipo, direccion=1):
    if pd.isna(actual) or pd.isna(anterior) or anterior == 0:
        return "Sin base comparable", "neutral"
    if tipo == "pp":
        cambio = (actual - anterior) * 100
        sufijo = " pp"
    else:
        cambio = (actual - anterior) / abs(anterior)
        cambio *= 100
        sufijo = "%"
    signo = "+" if cambio > 0 else "−" if cambio < 0 else ""
    texto = f"{signo}{ui.num(abs(cambio), 1)}{sufijo}"
    estado = "good" if cambio * direccion > 0 else ("bad" if cambio * direccion < 0 else "neutral")
    return f"vs año anterior: {texto}", estado


def _kpis(actual, anterior, anio, nuevos):
    dias_actual = 366 if calendar.isleap(anio) else 365
    dias_anterior = 366 if calendar.isleap(anio - 1) else 365

    def ratio(a, b):
        return a / b if b and not pd.isna(a) and not pd.isna(b) else float("nan")

    metrics_actual = [
        actual["venta"],
        ratio(actual["margen"], actual["venta"]),
        ratio(actual["venta"], actual["facturas"]),
        ratio(actual["venta"], dias_actual),
        ratio(actual["unidades"], actual["facturas"]),
        actual["facturas"],
        actual["clientes"],
        1 - ratio(actual["venta_con_lista"], actual["valor_lista"]),
    ]
    metrics_anterior = [
        anterior["venta"],
        ratio(anterior["margen"], anterior["venta"]),
        ratio(anterior["venta"], anterior["facturas"]),
        ratio(anterior["venta"], dias_anterior),
        ratio(anterior["unidades"], anterior["facturas"]),
        anterior["facturas"],
        anterior["clientes"],
        1 - ratio(anterior["venta_con_lista"], anterior["valor_lista"]),
    ]
    labels = [
        "Venta neta", "Margen bruto %", "Ticket promedio", "Venta diaria promedio",
        "Unidades por factura", "Facturas", "Clientes activos", "Descuento vs lista",
    ]
    formats = ["money", "percent", "money", "money", "number", "number", "number", "percent"]
    delta_types = ["relative", "pp", "relative", "relative", "relative", "relative", "relative", "pp"]
    directions = [1, 1, 1, 1, 1, 1, 1, -1]
    cards = []
    summary = []
    for i, label in enumerate(labels):
        value = metrics_actual[i]
        previous = metrics_anterior[i]
        kind = formats[i]
        if pd.isna(value):
            shown = "—"
        elif kind == "money":
            shown = ui.usd(value)
        elif kind == "percent":
            shown = ui.pct(value)
        else:
            shown = ui.num(value, 2 if i == 4 else 0)
        change, state = _delta(value, previous, delta_types[i], directions[i])
        if anterior["lineas"] <= 0:
            change, state = "Sin datos del año anterior", "neutral"
        if i == 6:
            subtitle = f"{change} · {ui.num(nuevos)} compraron por primera vez en {anio}"
        else:
            subtitle = change
        cards.append(
            f'<div class="gm-kpi" translate="no"><div class="gm-kpi-label">{ui.esc(label)}</div>'
            f'<div class="gm-kpi-value">{ui.esc(shown)}</div>'
            f'<div class="gm-kpi-delta {state}">{ui.esc(subtitle)}</div></div>'
        )
        summary.append(f"- **{label}:** {shown} ({subtitle}).")
    st.markdown(
        '<style>.gm-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:12px 0 22px}'
        '.gm-kpi{background:#fff;border:1px solid #EAD7DD;border-radius:16px;padding:15px 17px}'
        '.gm-kpi-label{font-size:12px;color:#59414B;font-weight:600}'
        '.gm-kpi-value{font-family:"Cormorant Garamond",serif;font-size:28px;font-weight:700;color:#5E2139}'
        '.gm-kpi-delta{font-size:12px;font-weight:600}.gm-kpi-delta.good{color:#2F6B5A}'
        '.gm-kpi-delta.bad{color:#A3284F}.gm-kpi-delta.neutral{color:#59414B}</style>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="gm-kpis" translate="no">{"".join(cards)}</div>', unsafe_allow_html=True)
    return metrics_actual, metrics_anterior, summary


def _brandas_por_anio(anio, sku_sql, params):
    return q(f"""
        SELECT p.marca, SUM(v.venta_neta) AS venta, SUM(v.unidades) AS unidades,
               SUM(v.margen_bruto) AS margen,
               arg_max(p.imagen_url, v.venta_neta) FILTER (WHERE p.imagen_url IS NOT NULL) AS imagen_url
        FROM f_ventas v JOIN dim_producto p USING (sku)
        WHERE v.anio={int(anio)} AND {sku_sql}
        GROUP BY p.marca ORDER BY venta DESC
    """, params)


def _close_month(anio, sku_sql, params):
    row = q(f"""
        SELECT MAX(i.periodo) AS periodo
        FROM f_inventario i
        WHERE i.periodo BETWEEN '{int(anio)}-01' AND '{int(anio)}-12' AND {sku_sql}
    """, params).iloc[0]
    return row.periodo


def _insights(anio, anterior_disponible, actual, sku_sql, params, marca_actual, marcas):
    items = []
    cierre = _close_month(anio, sku_sql.replace("v.sku", "i.sku"), params)
    if cierre:
        top_quiebres = q(f"""
            WITH top_sku AS (
                SELECT v.sku, SUM(v.venta_neta) AS venta
                FROM f_ventas v WHERE v.anio={int(anio)} AND {sku_sql}
                GROUP BY v.sku ORDER BY venta DESC LIMIT {QUIEBRE_TOP_SKU}
            )
            SELECT COUNT(*) FILTER (WHERE i.inv_final_un <= 0) AS sku_agotados,
                   SUM(t.venta) FILTER (WHERE i.inv_final_un <= 0) AS venta_agotada
            FROM top_sku t JOIN f_inventario i ON i.sku=t.sku AND i.periodo=$cierre
        """, params | {"cierre": cierre}).iloc[0]
        agotados = int(top_quiebres.sku_agotados or 0)
        if agotados >= QUIEBRE_MIN_SKU:
            venta_agotada = float(top_quiebres.venta_agotada or 0)
            items.append({
                "tipo": "ALERTA", "area": "Inventario", "titulo": "Quiebre en productos líderes",
                "texto": f"{agotados} de los {QUIEBRE_TOP_SKU} SKU con más venta están agotados en {cierre}; "
                         f"representan {ui.usd(venta_agotada)} de venta del periodo.",
                "accion": "Priorizar reposición y revisar el stock de seguridad.",
                "responsable": "Abastecimiento",
                "dato": f"{agotados} SKU; {ui.usd(venta_agotada)}; cierre {cierre}.",
                "pantalla": "Rentabilidad e inventario",
            })

    cierre_anterior = None
    inventarios = None
    if cierre:
        mes = cierre[4:]
        cierre_anterior = f"{int(anio) - 1}{mes}"
        inventarios = q(f"""
            SELECT i.periodo, SUM(i.valor_inv_final) AS valor
            FROM f_inventario i
            WHERE i.periodo IN ($actual, $anterior) AND {sku_sql.replace("v.sku", "i.sku")}
            GROUP BY i.periodo
        """, params | {"actual": cierre, "anterior": cierre_anterior})
    if anterior_disponible and inventarios is not None and len(inventarios) == 2:
        inv_actual = inventarios.loc[inventarios.periodo == cierre, "valor"].iloc[0]
        inv_anterior = inventarios.loc[inventarios.periodo == cierre_anterior, "valor"].iloc[0]
        if pd.notna(inv_actual) and pd.notna(inv_anterior) and inv_anterior > 0:
            variacion_inv = inv_actual / inv_anterior - 1
            if variacion_inv < -INVENTARIO_CAIDA_MIN:
                items.append({
                    "tipo": "ALERTA", "area": "Inventario", "titulo": "Caída del valor de inventario",
                    "texto": f"El inventario cerró en {ui.usd(inv_actual)} en {cierre}, "
                             f"{ui.pct(variacion_inv)} frente a {ui.usd(inv_anterior)} en {cierre_anterior}.",
                    "accion": "Contrastar la caída con demanda, cobertura y órdenes en tránsito.",
                    "responsable": "Operaciones",
                    "dato": f"{ui.usd(inv_actual)} vs {ui.usd(inv_anterior)} ({ui.pct(variacion_inv)}).",
                    "pantalla": "Rentabilidad e inventario",
                })

    if anterior_disponible and marca_actual is not None:
        previo = marcas.loc[marcas.marca == marca_actual.marca, "venta_antes"]
        venta_previa = float(previo.iloc[0]) if len(previo) and pd.notna(previo.iloc[0]) else 0.0
        if venta_previa > 0:
            cambio_lider = float(marca_actual.venta) / venta_previa - 1
            if cambio_lider < -LIDER_CAIDA_MIN:
                crecimiento = marcas.sort_values("crecimiento_usd", ascending=False).iloc[0]
                items.append({
                    "tipo": "TENDENCIA", "area": "Ventas", "titulo": f"Baja la marca líder: {ui.titulo_caso(marca_actual.marca)}",
                    "texto": f"La marca líder cae {ui.pct(cambio_lider)} ({ui.usd(float(marca_actual.venta) - venta_previa)}). "
                             f"La que más crece en USD es {ui.titulo_caso(crecimiento.marca)} "
                             f"({ui.usd(crecimiento.crecimiento_usd)}).",
                    "accion": "Investigar disponibilidad y transferencia de demanda hacia marcas en crecimiento.",
                    "responsable": "Comercial",
                    "dato": f"{ui.titulo_caso(marca_actual.marca)}: {ui.pct(cambio_lider)}; "
                            f"{ui.titulo_caso(crecimiento.marca)}: +{ui.usd(crecimiento.crecimiento_usd)}.",
                    "pantalla": "Ventas",
                })

    compras_filtro, base_compras = comparacion_costos_abastecimiento(
        sku_sql, params, f"{int(anio)}-01-01", f"{int(anio)}-12-31"
    )
    comparaciones = compras_filtro.brecha.tolist()
    if comparaciones:
        mediana_brecha = float(pd.Series(comparaciones).median())
        if mediana_brecha > BRECHA_PROVEEDOR_MIN:
            items.append({
                "tipo": "OPORTUNIDAD", "area": "Compras", "titulo": "Costo Nacional vs Internacional",
                "texto": f"El costo unitario nacionalizado Nacional tiene una brecha mediana de "
                         f"{ui.pct(mediana_brecha)} frente a Internacional en {len(comparaciones)} SKU. "
                         f"Base: {base_compras}, {len(comparaciones)} SKU comparados.",
                "accion": "Revisar el costo nacionalizado de los SKU con ambas vías de abastecimiento.",
                "responsable": "Compras",
                "dato": f"Mediana {ui.pct(mediana_brecha)}; {len(comparaciones)} SKU; "
                        f"base: {base_compras}; Nacional vs Internacional.",
                "pantalla": "Compras y abastecimiento",
            })

    descuentos = q(f"""
        SELECT p.marca,
               SUM(v.venta_neta) AS venta,
               SUM(v.margen_bruto) / NULLIF(SUM(v.venta_neta), 0) AS margen,
               1 - SUM(v.venta_neta) FILTER (
                   WHERE v.mov='FACT' AND v.precio_lista > 0
               ) / NULLIF(SUM(v.precio_lista * v.unidades) FILTER (
                   WHERE v.mov='FACT' AND v.precio_lista > 0
               ), 0) AS descuento
        FROM f_ventas v JOIN dim_producto p USING (sku)
        WHERE v.anio={int(anio)} AND {sku_sql}
        GROUP BY p.marca
    """, params)
    margen_total = float(actual["margen"] / actual["venta"]) if actual["venta"] else float("nan")
    marcas_descuento = descuentos[
        (descuentos.descuento > DESCUENTO_MIN)
        & (descuentos.margen < margen_total)
        & descuentos.descuento.notna()
    ].sort_values("venta", ascending=False)
    if not marcas_descuento.empty:
        muestras = marcas_descuento.head(3)
        detalle = "; ".join(
            f"{ui.titulo_caso(row.marca)}: descuento {ui.pct(row.descuento)}, margen {ui.pct(row.margen)}"
            for row in muestras.itertuples()
        )
        items.append({
            "tipo": "ALERTA", "area": "Precio y margen", "titulo": "Descuento alto con margen bajo",
            "texto": f"{len(marcas_descuento)} marcas superan {ui.pct(DESCUENTO_MIN)} de descuento y quedan "
                     f"bajo el margen promedio ({ui.pct(margen_total)}). {detalle}.",
            "accion": "Revisar descuentos y excepciones de precio en las marcas señaladas.",
            "responsable": "Pricing y Comercial",
            "dato": f"{len(marcas_descuento)} marcas; margen promedio {ui.pct(margen_total)}; {detalle}.",
            "pantalla": "Rentabilidad e inventario",
        })

    vip_clientes = int(actual["clientes_vip"] or 0)
    venta_vip = float(actual["venta_vip"] or 0)
    if vip_clientes >= VIP_CLIENTES_MIN and actual["venta"]:
        items.append({
            "tipo": "OPORTUNIDAD", "area": "Clientes", "titulo": "Venta a clientes VIP",
            "texto": f"Clientes VIP generan {ui.pct(venta_vip / actual['venta'])} de la venta neta; "
                     f"hay {vip_clientes} clientes VIP activos.",
            "accion": "Proteger recurrencia VIP con seguimiento de disponibilidad y recompra.",
            "responsable": "CRM y Comercial",
            "dato": f"{ui.pct(venta_vip / actual['venta'])} de venta; {vip_clientes} clientes.",
            "pantalla": "Ventas",
        })
    return items, cierre, len(comparaciones)


def _sell_through(anio, sku_sql, params):
    return q(f"""
        WITH ventas AS (
            SELECT p.marca, SUM(v.unidades) AS unidades
            FROM f_ventas v JOIN dim_producto p USING (sku)
            WHERE v.anio={int(anio)} AND {sku_sql}
            GROUP BY p.marca
        ), inicial AS (
            SELECT p.marca, SUM(i.inv_inicial_un) AS unidades_iniciales
            FROM f_inventario i JOIN dim_producto p USING (sku)
            WHERE i.periodo='{int(anio)}-01' AND {sku_sql.replace("v.sku", "i.sku")}
            GROUP BY p.marca
        ), compras AS (
            SELECT p.marca, SUM(c.unidades) AS unidades_compradas
            FROM f_compras c JOIN dim_producto p USING (sku)
            WHERE c.anio={int(anio)} AND {sku_sql.replace("v.sku", "c.sku")}
            GROUP BY p.marca
        )
        SELECT v.marca, v.unidades, COALESCE(c.unidades_compradas, 0) AS unidades_compradas,
               v.unidades / NULLIF(COALESCE(i.unidades_iniciales, 0) + COALESCE(c.unidades_compradas, 0), 0) AS sell_through
        FROM ventas v LEFT JOIN inicial i USING (marca) LEFT JOIN compras c USING (marca)
        WHERE v.unidades >= {SELL_THROUGH_MIN_UNIDADES}
          AND COALESCE(i.unidades_iniciales, 0) + COALESCE(c.unidades_compradas, 0) > 0
        ORDER BY sell_through DESC
    """, params)


def _podium(anio, anterior_disponible, marcas, sku_sql, params):
    actuales = _brandas_por_anio(anio, sku_sql, params)
    logo_urls = q("SELECT marca, logo_url FROM dim_marca WHERE logo_url IS NOT NULL")
    logos = dict(logo_urls.values)
    filas = []

    if not actuales.empty:
        lider = actuales.iloc[0]
        filas.append({
            "titulo": "Marca más vendida",
            "marca": lider.marca,
            "nombre": ui.titulo_caso(lider.marca),
            "venta": lider.venta,
            "variacion": (
                marcas.loc[marcas.marca == lider.marca, "crecimiento_usd"].iloc[0]
                if anterior_disponible else None
            ),
            "imagen": lider.imagen_url,
            "sub": f"Venta neta: {ui.usd(lider.venta)}",
        })
        if anterior_disponible:
            fila_lider = marcas.loc[marcas.marca == lider.marca].iloc[0]
            tasa_lider = (
                fila_lider.crecimiento_usd / fila_lider.venta_antes
                if fila_lider.venta_antes > 0 else float("nan")
            )
            filas[-1]["sub"] += (
                f" · Variación: {ui.usd(fila_lider.crecimiento_usd)} "
                f"({ui.pct(tasa_lider, signo=True)})"
            )
        if anterior_disponible and not marcas.empty:
            mayor_crecimiento = marcas.sort_values("crecimiento_usd", ascending=False).iloc[0]
            imagen = actuales.loc[actuales.marca == mayor_crecimiento.marca, "imagen_url"]
            filas.append({
                "titulo": "Mayor crecimiento en USD",
                "marca": mayor_crecimiento.marca,
                "nombre": ui.titulo_caso(mayor_crecimiento.marca),
                "venta": mayor_crecimiento.venta_ahora,
                "variacion": mayor_crecimiento.crecimiento_usd,
                "imagen": imagen.iloc[0] if len(imagen) else None,
                "sub": f"Cambio anual: +{ui.usd(mayor_crecimiento.crecimiento_usd)}",
            })

    sell = _sell_through(anio, sku_sql, params)
    if not sell.empty:
        rapido = sell.iloc[0]
        tops = sell.head(3)
        detalle_top = " · ".join(
            f"{ui.titulo_caso(row.marca)} {ui.pct(row.sell_through)} "
            f"({ui.num(row.unidades_compradas)} compradas)"
            for row in tops.itertuples()
        )
        marca_rapida = actuales.loc[actuales.marca == rapido.marca]
        filas.append({
            "titulo": "Sell-through más alto",
            "marca": rapido.marca,
            "nombre": ui.titulo_caso(rapido.marca),
            "venta": rapido.sell_through,
            "variacion": None,
            "imagen": marca_rapida.imagen_url.iloc[0] if len(marca_rapida) else None,
            "sub": f"{ui.pct(rapido.sell_through)} · {ui.num(rapido.unidades)} unidades vendidas",
            "detalle": detalle_top,
        })

    sku_top = q(f"""
        SELECT p.sku, p.marca, p.etiqueta, p.imagen_url, SUM(v.unidades) AS unidades,
               SUM(v.venta_neta) AS venta
        FROM f_ventas v JOIN dim_producto p USING (sku)
        WHERE v.anio={int(anio)} AND {sku_sql}
        GROUP BY p.sku, p.marca, p.etiqueta, p.imagen_url
        ORDER BY unidades DESC, venta DESC LIMIT 1
    """, params)
    if not sku_top.empty:
        sku = sku_top.iloc[0]
        filas.append({
            "titulo": "Perfume más vendido por unidades",
            "marca": sku.marca,
            "nombre": ui.titulo_caso(sku.etiqueta),
            "venta": sku.unidades,
            "variacion": None,
            "imagen": sku.imagen_url,
            "sub": f"{ui.num(sku.unidades)} unidades · {ui.usd(sku.venta)}",
        })

    cols = st.columns(2)
    for i, card in enumerate(filas):
        with cols[i % 2]:
            logo = ui.logo_html(logos.get(card["marca"]), card["marca"])
            imagen = ui.foto(card["imagen"], card["marca"], card["nombre"])
            extra = f'<div class="gm-podium-extra" translate="no">{ui.esc(card["detalle"])}</div>' if card.get("detalle") else ""
            st.markdown(
                f'<div class="gm-podium" translate="no"><div class="gm-podium-image">{imagen}</div>'
                f'<div class="gm-podium-copy"><div class="gm-podium-label">{ui.esc(card["titulo"])}</div>'
                f'{logo}<div class="gm-podium-name">{ui.esc(card["nombre"])}</div>'
                f'<div class="gm-podium-sub">{ui.esc(card["sub"])}</div>{extra}</div></div>',
                unsafe_allow_html=True,
            )
    return filas, sell


def render():
    filtros = st.session_state["filtros"]
    anio = int(filtros.hasta[:4])
    anio_anterior = anio - 1
    sku_sql, params = filtros.sku_sql("v.sku")
    actual = _anio_metricas(anio, sku_sql, params)
    anterior = _anio_metricas(anio_anterior, sku_sql, params)
    if actual["lineas"] == 0:
        ui.titulo("Dirección · visión anual", "Resumen gerencial", filtros.descripcion)
        st.info(f"No hay datos de {anio} con los filtros seleccionados.")
        return

    anterior_disponible = anterior["lineas"] > 0
    nuevos = _nuevos_clientes(anio, sku_sql, params)
    ui.titulo("Dirección · visión anual", f"Resumen gerencial · {anio}", filtros.descripcion)
    st.caption(
        f"Periodo actual: año calendario {anio}; comparación con {anio_anterior} cuando hay datos. "
        "Se respetan los filtros de producto y el año se toma de la fecha final seleccionada."
    )
    metrics_actual, metrics_anterior, kpi_text = _kpis(actual, anterior, anio, nuevos)

    actuales = _brandas_por_anio(anio, sku_sql, params)
    previas = _brandas_por_anio(anio_anterior, sku_sql, params) if anterior_disponible else pd.DataFrame()
    marcas = actuales[["marca", "venta"]].rename(columns={"venta": "venta_ahora"})
    marcas["venta_antes"] = marcas.marca.map(
        previas.set_index("marca").venta if not previas.empty else pd.Series(dtype=float)
    )
    marcas["venta_antes"] = marcas.venta_antes.fillna(0)
    marcas["crecimiento_usd"] = marcas.venta_ahora - marcas.venta_antes
    marca_actual = actuales.iloc[0] if not actuales.empty else None

    st.markdown("## Lo que hay que saber")
    insights, cierre, sku_comparables = _insights(
        anio, anterior_disponible, actual, sku_sql, params, marca_actual, marcas
    )
    if insights:
        for start in range(0, len(insights), 2):
            columnas = st.columns(2)
            for offset, insight in enumerate(insights[start:start + 2]):
                etiqueta = insight["tipo"]
                stilo = "alerta" if etiqueta == "ALERTA" else "oportunidad"
                with columnas[offset]:
                    st.markdown(
                        f'<div class="gm-insight {stilo}" translate="no">'
                        f'<div class="gm-insight-tag">{ui.esc(etiqueta)} · {ui.esc(insight["area"])}</div>'
                        f'<h3>{ui.esc(insight["titulo"])}</h3><p>{ui.esc(insight["texto"])}</p>'
                        f'<p class="gm-action">→ {ui.esc(insight["accion"])}</p></div>',
                        unsafe_allow_html=True,
                    )
    else:
        st.info("No se activaron alertas u oportunidades con los umbrales definidos y los filtros actuales.")

    st.markdown("## Podio del periodo")
    podium, sell = _podium(anio, anterior_disponible, marcas, sku_sql, params)
    st.markdown(
        '<style>.gm-insight{background:#fff;border:1px solid #EAD7DD;border-left:5px solid #8E3B5A;'
        'border-radius:16px;padding:16px 18px;margin:4px 0 14px;color:#2A1520}'
        '.gm-insight.oportunidad{border-left-color:#8E3B5A}.gm-insight h3{margin:4px 0 8px;font-size:22px}'
        '.gm-insight p{margin:4px 0;color:#59414B;font-size:13px}.gm-insight-tag{font-size:11px;'
        'font-weight:700;letter-spacing:1px;color:#5E2139}.gm-action{font-weight:600}'
        '.gm-podium{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid #EAD7DD;'
        'border-radius:18px;padding:14px;margin:5px 0 14px;min-height:188px;color:#2A1520}'
        '.gm-podium-image{flex:0 0 112px;height:150px;position:relative;overflow:hidden;border-radius:12px;background:#F3E3E8}'
        '.gm-podium-image .fi-ph-ini{border-radius:12px}.gm-podium-copy{min-width:0}'
        '.gm-podium-label{font-size:11px;font-weight:700;letter-spacing:1px;color:#6B4E5A;text-transform:uppercase}'
        '.gm-podium-name{font-family:"Cormorant Garamond",serif;font-size:25px;font-weight:700;color:#5E2139}'
        '.gm-podium-sub,.gm-podium-extra{font-size:12px;color:#59414B;margin-top:3px}'
        '.gm-podium-extra{font-weight:600}</style>',
        unsafe_allow_html=True,
    )
    if podium:
        st.caption("Sell-through alto con pocas compras puede indicar que la marca se está agotando, no solo que vende rápido.")
    if anterior_disponible:
        lider = marcas.sort_values("venta_ahora", ascending=False).iloc[0]
        crecimiento = marcas.sort_values("crecimiento_usd", ascending=False).iloc[0]
        podio_text = [
            f"Marca más vendida: {ui.titulo_caso(lider.marca)} ({ui.usd(lider.venta_ahora)}).",
            f"Mayor crecimiento: {ui.titulo_caso(crecimiento.marca)} (+{ui.usd(crecimiento.crecimiento_usd)}).",
        ]
    else:
        podio_text = [f"Marca más vendida: {ui.titulo_caso(actuales.iloc[0].marca)} ({ui.usd(actuales.iloc[0].venta)})."]
    if not sell.empty:
        podio_text.append("Sell-through top 3: " + " · ".join(
            f"{ui.titulo_caso(row.marca)} {ui.pct(row.sell_through)} ({ui.num(row.unidades_compradas)} compradas)"
            for row in sell.head(3).itertuples()
        ) + ".")
    if podium and podium[-1]["titulo"] == "Perfume más vendido por unidades":
        podio_text.append(f"SKU líder: {podium[-1]['nombre']} ({podium[-1]['sub']}).")
    acciones_texto = [
        f"- **{('Alta' if item['tipo'] == 'ALERTA' else 'Media')} · {item['area']}** "
        f"{item['accion']} Responsable: {item['responsable']}. "
        f"Dato: {item['dato']} Auditar en: {item['pantalla']}."
        for item in insights
    ] if insights else ["- Sin acciones activas para los umbrales actuales."]

    st.markdown("## Ritmo de venta")
    semanal = q(f"""
        SELECT CAST(strftime(v.fecha, '%w') AS INTEGER) AS dia_semana, SUM(v.venta_neta) AS venta
        FROM f_ventas v WHERE v.anio={int(anio)} AND {sku_sql}
        GROUP BY dia_semana ORDER BY dia_semana
    """, params)
    ventas_dia = {int(row.dia_semana): float(row.venta) for row in semanal.itertuples()}
    # DuckDB %w: domingo=0; se reordena a lunes-domingo.
    ventas_ordenadas = [ventas_dia.get(dia, 0.0) for dia in [1, 2, 3, 4, 5, 6, 0]]
    suma_semanal = sum(ventas_ordenadas)
    porcentajes_dia = [venta / suma_semanal * 100 if suma_semanal else 0 for venta in ventas_ordenadas]
    max_dia = max(range(7), key=lambda index: ventas_ordenadas[index])
    dia_record = q(f"""
        SELECT v.fecha, SUM(v.venta_neta) AS venta
        FROM f_ventas v WHERE v.anio={int(anio)} AND {sku_sql}
        GROUP BY v.fecha ORDER BY venta DESC, v.fecha LIMIT 1
    """, params)
    colores_dia = [ui.ORO if index == max_dia else ui.ROSA_CL for index in range(7)]
    fig = go.Figure(go.Bar(
        x=DIAS, y=porcentajes_dia, marker_color=colores_dia,
        customdata=ventas_ordenadas,
        text=[f"{valor:.1f}%" for valor in porcentajes_dia], textposition="outside",
        hovertemplate="%{x}: %{y:.1f}% · $%{customdata:,.0f}<extra></extra>",
    ))
    fig.update_layout(yaxis_title="% de venta neta", xaxis_title=None, showlegend=False)
    st.plotly_chart(ui.plotly_base(fig, 320, False), use_container_width=True)
    st.markdown(
        f"El {['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'][max_dia]} "
        f"es el día de la semana con más venta ({ui.pct(porcentajes_dia[max_dia] / 100)})."
    )
    if not dia_record.empty:
        fecha_record = pd.Timestamp(dia_record.iloc[0].fecha).strftime("%d-%m-%Y")
        st.markdown(
            f"El día récord del periodo fue **{fecha_record}**, con "
            f"**{ui.usd(float(dia_record.iloc[0].venta))}** en ventas."
        )

    st.markdown("## Mezcla de portafolio")
    genero = q(f"""
        SELECT COALESCE(NULLIF(TRIM(p.genero), ''), 'Sin dato') AS genero,
               SUM(v.venta_neta) AS venta, SUM(v.margen_bruto) AS margen,
               SUM(v.margen_bruto) / NULLIF(SUM(v.venta_neta), 0) AS margen_pct
        FROM f_ventas v JOIN dim_producto p USING (sku)
        WHERE v.anio={int(anio)} AND {sku_sql}
        GROUP BY 1 ORDER BY venta DESC
    """, params)
    if not genero.empty:
        total_genero = genero.venta.sum()
        fig_genero = go.Figure()
        for row in genero.itertuples():
            share = row.venta / total_genero * 100 if total_genero else 0
            fig_genero.add_bar(
                y=["Venta neta"], x=[share], name=ui.titulo_caso(row.genero), orientation="h",
                marker_color=ui.SERIE[len(fig_genero.data) % len(ui.SERIE)],
                text=[f"{ui.titulo_caso(row.genero)} {share:.0f}%"], textposition="inside",
                customdata=[[row.venta, row.margen_pct * 100 if pd.notna(row.margen_pct) else float("nan")]],
                hovertemplate="%{fullData.name}<br>Venta: $%{customdata[0]:,.0f}<br>"
                "Margen: %{customdata[1]:.1f}%<extra></extra>",
            )
        fig_genero.update_layout(barmode="stack", xaxis_title="% de venta neta", yaxis_title=None, showlegend=False)
        st.plotly_chart(ui.plotly_base(fig_genero, 200, False), use_container_width=True)
        st.caption("Cada segmento es la participación de un género; al pasar el cursor se ve el margen bruto de ese género.")

    familia = q(f"""
        SELECT p.familia_olfativa AS familia, SUM(v.venta_neta) AS venta
        FROM f_ventas v JOIN dim_producto p USING (sku)
        WHERE v.anio={int(anio)} AND {sku_sql}
          AND p.familia_olfativa IS NOT NULL AND TRIM(p.familia_olfativa) <> ''
        GROUP BY p.familia_olfativa ORDER BY venta DESC
    """, params)
    venta_total = float(actual["venta"] or 0)
    venta_familias = float(familia.venta.sum()) if not familia.empty else 0.0
    sin_familia = max(0.0, venta_total - venta_familias)
    share_sin_familia = sin_familia / venta_total if venta_total else 0.0
    if not familia.empty:
        fig_familia = go.Figure(go.Bar(
            x=familia.venta, y=familia.familia, orientation="h",
            marker_color=[ui.SERIE[index % len(ui.SERIE)] for index in range(len(familia))],
            customdata=familia.venta / venta_total * 100 if venta_total else familia.venta * 0,
            hovertemplate="%{y}<br>Venta verificada: $%{x:,.0f}<br>% del total: %{customdata:.1f}%<extra></extra>",
        ))
        fig_familia.update_layout(
            title="Venta por familia olfativa verificada",
            xaxis_title="Venta neta (USD)", yaxis_title=None,
            yaxis={"autorange": "reversed"},
        )
        st.plotly_chart(ui.plotly_base(fig_familia, max(300, len(familia) * 26), False), use_container_width=True)
    st.caption(
        f"Las familias mostradas usan solo registros verificados. Venta sin familia verificada: "
        f"{ui.pct(share_sin_familia)} ({ui.usd(sin_familia)})."
    )

    st.markdown("## Plan de acción")
    if insights:
        plan = pd.DataFrame([{
            "Prioridad": "Alta" if item["tipo"] == "ALERTA" else "Media",
            "Área": item["area"],
            "Acción": item["accion"],
            "Responsable": item["responsable"],
            "Dato de respaldo": item["dato"],
            "Auditar en": item["pantalla"],
        } for item in insights])
        st.dataframe(plan, hide_index=True, width="stretch")
    else:
        st.info("No hay acciones activas para los umbrales actuales.")

    informe = [
        f"# Resumen gerencial {anio}",
        "",
        "## Indicadores",
        *kpi_text,
        "",
        "## Lo que hay que saber",
    ]
    if insights:
        for item in insights:
            informe.append(
                f"- **{item['tipo']} · {item['area']} — {item['titulo']}:** {item['texto']} "
                f"→ Acción sugerida: {item['accion']}"
            )
    else:
        informe.append("- No se activaron alertas u oportunidades con los umbrales definidos.")
    informe.extend(["", "## Podio", *[f"- {line}" for line in podio_text]])
    informe.extend([
        "",
        "## Ritmo de venta",
        f"- {DIAS[max_dia]} es el día récord: {ui.usd(ventas_ordenadas[max_dia])} "
        f"({ui.pct(porcentajes_dia[max_dia] / 100)}).",
        "",
        "## Mezcla",
        f"- Venta sin familia olfativa verificada: {ui.pct(share_sin_familia)} ({ui.usd(sin_familia)}).",
        "- Venta y margen bruto por género:",
        *[
            f"  - {ui.titulo_caso(row.genero)}: {ui.usd(row.venta)}; margen {ui.pct(row.margen_pct)}."
            for row in genero.itertuples()
        ],
        "- Venta por familia olfativa verificada:",
        *[
            f"  - {ui.titulo_caso(row.familia)}: {ui.usd(row.venta)}."
            for row in familia.itertuples()
        ],
        "",
        "## Plan de acción",
        *acciones_texto,
        "",
        "## Umbrales y advertencias",
        f"- Quiebre: top {QUIEBRE_TOP_SKU} por venta; alerta desde {QUIEBRE_MIN_SKU} SKU agotados.",
        f"- Caída de inventario: >{ui.pct(INVENTARIO_CAIDA_MIN)}; caída de marca líder: >{ui.pct(LIDER_CAIDA_MIN)}.",
        f"- Oportunidad de proveedor: mediana de brecha >{ui.pct(BRECHA_PROVEEDOR_MIN)}.",
        f"- Descuento alto: >{ui.pct(DESCUENTO_MIN)} con margen inferior al promedio.",
        f"- VIP: al menos {VIP_CLIENTES_MIN} cliente activo; sell-through: ≥{SELL_THROUGH_MIN_UNIDADES} unidades.",
        "- Fechas redistribuidas 2025–2026; las comparaciones de proveedores se basan en SKU con compras a 2 o más proveedores.",
        f"- Se compararon {sku_comparables} SKU para la oportunidad de proveedores.",
        "- Sell-through alto con pocas compras puede indicar que la marca se está agotando, no solo que vende rápido.",
    ])
    texto_informe = "\n".join(informe)
    st.download_button(
        "Descargar resumen (.md)", data=texto_informe, file_name=f"resumen_gerencial_{anio}.md",
        mime="text/markdown",
    )
    crecimiento_venta = (
        ui.pct(actual["venta"] / anterior["venta"] - 1, signo=True)
        if anterior_disponible and anterior["venta"] else "sin base comparable"
    )
    cambio_margen = (
        (actual["margen"] / actual["venta"] - anterior["margen"] / anterior["venta"]) * 100
        if anterior_disponible and actual["venta"] and anterior["venta"] else "sin base comparable"
    )
    if isinstance(cambio_margen, (int, float)):
        signo_margen = "+" if cambio_margen > 0 else "−" if cambio_margen < 0 else ""
        cambio_margen = f"{signo_margen}{ui.num(abs(cambio_margen), 1)} pp"
    alerta_quiebre = next(
        (item for item in insights if item["titulo"] == "Quiebre en productos líderes"),
        None,
    )
    alerta_correo = alerta_quiebre["texto"] if alerta_quiebre else "Sin alerta activa de quiebre en productos líderes."
    marca_lider = marcas.sort_values("venta_ahora", ascending=False).iloc[0]
    marca_crece = marcas.sort_values("crecimiento_usd", ascending=False).iloc[0]
    accion_prioritaria = next(
        (item for item in insights if item["tipo"] == "ALERTA"),
        insights[0] if insights else None,
    )
    texto_accion = accion_prioritaria["accion"] if accion_prioritaria else "Sin acción prioritaria activa."
    correo = [
        f"Venta neta: {ui.usd(actual['venta'])}; crecimiento interanual: {crecimiento_venta}.",
        f"Margen bruto: {ui.pct(actual['margen'] / actual['venta'])}; variación: {cambio_margen}.",
        f"Alerta principal: {alerta_correo}",
        f"Marca líder: {ui.titulo_caso(marca_lider.marca)}; mayor crecimiento: {ui.titulo_caso(marca_crece.marca)} "
        f"({ui.usd(marca_crece.crecimiento_usd)}).",
        f"Acción prioritaria: {texto_accion}",
    ]
    st.markdown("### Resumen para correo")
    st.code("\n".join(correo), language="text")

    dias_anio = 366 if calendar.isleap(anio) else 365
    st.caption(
        "Reglas: quiebre en top 50 desde 10 SKU; inventario cae >30%; marca líder cae >10%; "
        "proveedor mediana de brecha >20%; descuento >25% con margen inferior al promedio; "
        "VIP con al menos un cliente; sell-through solo marcas con 40+ unidades. "
        f"Periodo anual con {dias_anio} días calendario. Fechas redistribuidas 2025–2026. "
        f"La comparación de proveedores se basa en {sku_comparables} SKU con compras de 2+ proveedores. "
        "La marca de mayor crecimiento se compara en USD contra el año anterior."
    )
