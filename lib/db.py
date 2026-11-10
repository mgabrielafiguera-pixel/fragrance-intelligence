"""Acceso a datos: conexión DuckDB de solo lectura + filtros globales traducidos a SQL."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
import duckdb
import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parents[1]
DB = BASE / "data" / "fragancias.duckdb"


@st.cache_resource
def conexion():
    if not DB.exists():
        st.error("No existe data/fragancias.duckdb. Ejecuta primero: python etl/construir_duckdb.py")
        st.stop()
    return duckdb.connect(str(DB), read_only=True)


def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Ejecuta SQL con parámetros nombrados ($x). Cursor propio por llamada (seguro entre sesiones)."""
    return _q(sql, json.dumps(params or {}, default=str))


@st.cache_data(show_spinner=False)
def _q(sql: str, params_json: str) -> pd.DataFrame:
    params = json.loads(params_json)
    return conexion().cursor().execute(sql, params).df()


def meta() -> dict:
    return json.loads(q("SELECT json FROM meta").iloc[0, 0])


def comparacion_costos_abastecimiento(
    sku_sql: str,
    params: dict,
    desde: str | None = None,
    hasta: str | None = None,
    minimo_sku: int = 5,
) -> tuple[pd.DataFrame, str]:
    filtro_sku = sku_sql.replace("v.sku", "c.sku")

    def consultar(fecha_desde: str | None, fecha_hasta: str | None) -> pd.DataFrame:
        filtro_fecha = ""
        parametros = dict(params)
        if fecha_desde and fecha_hasta:
            filtro_fecha = "AND c.fecha BETWEEN CAST($f_desde AS DATE) AND CAST($f_hasta AS DATE)"
            parametros.update({"f_desde": fecha_desde, "f_hasta": fecha_hasta})
        return q(f"""
            WITH costos AS (
                SELECT c.sku, UPPER(TRIM(c.tipo_proveedor)) AS tipo,
                       SUM(c.total_costo_nac) / NULLIF(SUM(c.unidades), 0) AS costo_unit
                FROM f_compras c
                WHERE c.unidades > 0 AND {filtro_sku} {filtro_fecha}
                  AND UPPER(TRIM(c.tipo_proveedor)) IN ('NACIONAL', 'INTERNACIONAL')
                GROUP BY c.sku, tipo
                HAVING SUM(c.unidades) > 0 AND SUM(c.total_costo_nac) > 0
            )
            SELECT sku,
                   MAX(costo_unit) FILTER (WHERE tipo='NACIONAL') AS costo_nacional,
                   MAX(costo_unit) FILTER (WHERE tipo='INTERNACIONAL') AS costo_internacional,
                   MAX(costo_unit) FILTER (WHERE tipo='NACIONAL')
                       / NULLIF(MAX(costo_unit) FILTER (WHERE tipo='INTERNACIONAL'), 0) - 1 AS brecha
            FROM costos
            GROUP BY sku
            HAVING COUNT(DISTINCT tipo) = 2
               AND MAX(costo_unit) FILTER (WHERE tipo='NACIONAL') > 0
               AND MAX(costo_unit) FILTER (WHERE tipo='INTERNACIONAL') > 0
            ORDER BY brecha DESC
        """, parametros)

    comparacion = consultar(desde, hasta)
    if desde and hasta and len(comparacion) < minimo_sku:
        comparacion = consultar(None, None)
        rango = q(f"""
            SELECT MIN(c.anio) AS desde, MAX(c.anio) AS hasta
            FROM f_compras c
            WHERE c.unidades > 0 AND {filtro_sku}
        """, params).iloc[0]
        base = (
            f"historial {int(rango.desde)}–{int(rango.hasta)}"
            if pd.notna(rango.desde) and pd.notna(rango.hasta)
            else "historial disponible"
        )
    elif desde and hasta:
        base = f"periodo {desde[:7]}–{hasta[:7]}"
    else:
        base = "historial completo"
    return comparacion, base


@dataclass
class Filtros:
    marcas: list[str] = field(default_factory=list)
    colecciones: list[str] = field(default_factory=list)
    modelos: list[str] = field(default_factory=list)
    versiones: list[str] = field(default_factory=list)
    tamanos: list[float] = field(default_factory=list)
    generos: list[str] = field(default_factory=list)
    desde: str = "2025-01-01"
    hasta: str = "2026-12-31"

    # --- filtro de producto (sobre dim_producto) ---
    def sku_sql(self, col: str = "sku") -> tuple[str, dict]:
        cond, p = [], {}
        for nombre, campo, valores in [("f_marca", "marca", self.marcas), ("f_col", "coleccion", self.colecciones),
                                       ("f_mod", "modelo", self.modelos), ("f_ver", "version", self.versiones),
                                       ("f_ml", "tamano_ml", self.tamanos), ("f_gen", "genero", self.generos)]:
            if valores:
                cond.append(f"list_contains(${nombre}, {campo})")
                p[nombre] = list(valores)
        if not cond:
            return "TRUE", {}
        return f"{col} IN (SELECT sku FROM dim_producto WHERE {' AND '.join(cond)})", p

    def where(self, fecha_col: str | None = "fecha", sku_col: str = "sku") -> tuple[str, dict]:
        s, p = self.sku_sql(sku_col)
        if fecha_col:
            s += f" AND {fecha_col} BETWEEN CAST($f_desde AS DATE) AND CAST($f_hasta AS DATE)"
            p |= {"f_desde": self.desde, "f_hasta": self.hasta}
        return s, p

    def where_periodo(self, periodo_col: str = "periodo") -> tuple[str, dict]:
        """Para tablas mensuales con periodo 'YYYY-MM' (inventario)."""
        s, p = self.sku_sql()
        s += f" AND {periodo_col} BETWEEN $f_pd AND $f_ph"
        p |= {"f_pd": self.desde[:7], "f_ph": self.hasta[:7]}
        return s, p

    @property
    def descripcion(self) -> str:
        partes = []
        for et, v in [("Marca", self.marcas), ("Colección", self.colecciones), ("Modelo", self.modelos),
                      ("Versión", self.versiones), ("ml", self.tamanos), ("Género", self.generos)]:
            if v:
                partes.append(f"{et}: {', '.join(map(lambda x: str(int(x)) if isinstance(x, float) else str(x), v[:3]))}{'…' if len(v) > 3 else ''}")
        return " · ".join(partes) or "Todas las fragancias"


# Niveles de agregación para rankings (Marca > Colección > Modelo > Versión > SKU)
NIVELES = {
    "Marca / diseñador": ("p.marca", "p.marca"),
    "Colección": ("p.marca || ' · ' || p.coleccion", "p.coleccion"),
    "Modelo": ("p.marca || ' · ' || p.modelo", "p.modelo"),
    "Fragancia (versión)": ("p.marca || ' · ' || p.version", "COALESCE(p.nombre_corto, p.version)"),
    "Perfume (SKU: versión + ml)": ("p.sku", "p.etiqueta"),
}


def ranking(f: Filtros, nivel: str, orden: str = "venta", n: int = 10, min_un: float = 0) -> pd.DataFrame:
    """Ranking por nivel. orden ∈ {venta, unidades, margen, margen_pct}. Imagen = la del SKU con más venta del grupo."""
    clave, nombre = NIVELES[nivel]
    w, p = f.where("v.fecha", "v.sku")
    sql = f"""
    WITH base AS (
        SELECT {clave} AS clave, any_value({nombre}) AS nombre, p.marca, p.sku, p.imagen_url,
               SUM(v.venta_neta) AS venta, SUM(v.unidades) AS unidades, SUM(v.margen_bruto) AS margen,
               SUM(v.costo_total) AS costo
        FROM f_ventas v JOIN dim_producto p USING (sku)
        WHERE {w}
        GROUP BY 1, p.marca, p.sku, p.imagen_url
    )
    SELECT clave, any_value(nombre) AS nombre, any_value(marca) AS marca,
           SUM(venta) AS venta, SUM(unidades) AS unidades, SUM(margen) AS margen, SUM(costo) AS costo,
           SUM(margen) / NULLIF(SUM(venta), 0) AS margen_pct,
           SUM(venta) / NULLIF(SUM(unidades), 0) AS precio_prom,
           arg_max(imagen_url, venta) FILTER (WHERE imagen_url IS NOT NULL) AS imagen_url,
           count(DISTINCT sku) AS n_sku,
           CASE WHEN count(DISTINCT sku) = 1 THEN any_value(sku) END AS sku
    FROM base GROUP BY clave
    HAVING SUM(unidades) >= $min_un
    ORDER BY {orden} DESC NULLS LAST
    LIMIT {int(n)}
    """
    return q(sql, p | {"min_un": min_un})
