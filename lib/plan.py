"""Plan de compras 2027 por marca y por mes (referencia del cálculo usado en el artículo).

Lee data/fragancias.duckdb (vistas f_ventas, f_compras, f_inventario, dim_producto) en modo solo lectura.
Resultados de control con la base pública actual:
  venta proyectada 2027 = 2.333 un · stock dic-2026 = 1.190 un · compras 2027 = 1.321 un · llegada en diciembre = 638 un
"""
import math
import duckdb
import numpy as np
import pandas as pd

COLCHON = 0.30          # stock de seguridad: 30% de la venta proyectada del mes
ERROR_MODELO = 0.19     # MAPE del modelo ingenuo estacional (R/forecast_modelos.csv, serie TOTAL)
TOP_MARCAS = 10         # marcas con mayor venta neta 2026; el resto se agrupa en "OTRAS MARCAS"


def calcular(ruta_db="data/fragancias.duckdb"):
    c = duckdb.connect(ruta_db, read_only=True)
    v = c.sql("""SELECT p.marca, anio, mes, SUM(unidades) u, SUM(venta_neta) vn
                 FROM f_ventas v JOIN dim_producto p USING (sku) GROUP BY ALL""").df()
    inv = c.sql("""SELECT p.marca, SUM(inv_final_un) inv FROM f_inventario i JOIN dim_producto p USING (sku)
                   WHERE periodo = '2026-12' GROUP BY 1""").df().set_index("marca").inv
    tp = c.sql("""SELECT p.marca, c.tipo_proveedor t, SUM(c.unidades) u FROM f_compras c
                  JOIN dim_producto p USING (sku) GROUP BY ALL""").df() \
        .pivot_table(index="marca", columns="t", values="u", fill_value=0)

    # 1) índice estacional en unidades: promedio de los índices 2025 y 2026, normalizado a media 1
    tot = v.groupby(["anio", "mes"]).u.sum().unstack(0)
    idx = (tot / tot.mean()).mean(axis=1)
    idx = idx / idx.mean()

    # 2) agrupar marcas
    top = v[v.anio == 2026].groupby("marca").vn.sum().sort_values(ascending=False).head(TOP_MARCAS).index
    grp = lambda s: np.where(s.isin(top), s, "OTRAS MARCAS")
    v["grupo"] = grp(v.marca)
    u26 = v[v.anio == 2026].groupby("grupo").u.sum()
    inv_g = inv.groupby(grp(inv.index)).sum()
    tp_g = tp.groupby(grp(tp.index)).sum()

    filas, meses = [], []
    for g in list(top) + ["OTRAS MARCAS"]:
        anual = float(u26.get(g, 0))
        stock = float(inv_g.get(g, 0))
        total_compra = 0
        for m in range(1, 13):
            venta = anual * idx[m] / 12                      # 3) reparto mensual
            objetivo = math.ceil(venta * (1 + COLCHON))      # 4) stock objetivo al inicio del mes
            compra = max(0, objetivo - stock)                # 5) compra que debe llegar al inicio del mes
            stock = stock + compra - venta
            total_compra += compra
            meses.append(dict(grupo=g, mes=m, venta_proy=round(venta), stock_objetivo=objetivo,
                              compra_llegada=round(compra), stock_fin=round(stock)))
        pct_imp = tp_g.loc[g].get("INTERNACIONAL", 0) / tp_g.loc[g].sum() if g in tp_g.index else 0
        filas.append(dict(grupo=g, proy_2027=round(anual), rango_min=round(anual * (1 - ERROR_MODELO)),
                          rango_max=round(anual * (1 + ERROR_MODELO)), stock_dic_2026=int(inv_g.get(g, 0)),
                          compra_2027=round(total_compra), pct_importado=round(pct_imp * 100)))
    return pd.DataFrame(filas), pd.DataFrame(meses), idx


if __name__ == "__main__":
    marcas, mensual, idx = calcular()
    print(marcas.to_string(index=False))
    print(mensual.groupby("mes")[["venta_proy", "stock_objetivo", "compra_llegada"]].sum().T.to_string())
