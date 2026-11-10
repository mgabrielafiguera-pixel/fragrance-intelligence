"""Fase 4 - Construye la base DuckDB de la app a partir del archivo de trabajo (solo lectura).

Uso:  python etl/construir_duckdb.py [ruta_archivo_trabajo.xlsx]

Fuente por defecto (en orden):
  1) ../fase3_enriquecimiento_web/archivo_trabajo_belleza_2025_2026_v2_web.xlsx  (con colección, familia e imagen)
  2) ../fase2_limpieza/archivo_trabajo_belleza_2025_2026.xlsx                     (archivo oficial)

El Excel NO se modifica: se lee con pandas y se copia tal cual a tablas DuckDB (prefijo raw_).
Las reglas de negocio viven en sql/modelo.sql (vistas), para que cada cálculo sea trazable.
Cuando el enriquecimiento web crezca, basta con volver a ejecutar este script.
"""
import os, sys, hashlib, json, datetime as dt
from pathlib import Path
import pandas as pd
import duckdb

BASE = Path(__file__).resolve().parents[1]
PROY = Path(os.environ.get("FRAG_PROYECTO", BASE.parent))  # carpeta raíz del proyecto
CANDIDATOS = [
    PROY / "fase3_enriquecimiento_web" / "archivo_trabajo_belleza_2025_2026_v2_web.xlsx",
    PROY / "fase2_limpieza" / "archivo_trabajo_belleza_2025_2026.xlsx",
]
HOJAS = ["VENTAS", "COMPRAS", "INVENTARIO_MES", "PAGOS_PROVEEDOR", "COBROS_CLIENTES",
         "DIM_PRODUCTO", "DIM_MARCA", "DIM_PROVEEDOR", "DIM_CLIENTE", "REGLAS", "CONTROLES", "DICCIONARIO"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def controlar_cuadre(con):
    return con.execute("""
        SELECT ROUND(SUM(VENTA_NETA), 2), SUM(UNIDADES), ROUND(SUM(COSTO_TOTAL), 2)
        FROM raw_ventas
    """).fetchone()


def anonimizar_por_tipo(con):
    for tabla in ["raw_compras", "raw_ventas", "raw_pagos_proveedor", "raw_dim_producto"]:
        columnas = {fila[0].upper() for fila in con.execute(f"DESCRIBE {tabla}").fetchall()}
        if not {"COD_PROVEEDOR", "TIPO_PROVEEDOR"}.issubset(columnas):
            continue
        tipos_invalidos = con.execute(f"""
            SELECT COUNT(*) FROM {tabla}
            WHERE COD_PROVEEDOR IS NOT NULL
              AND UPPER(TRIM(TIPO_PROVEEDOR)) NOT IN ('NACIONAL', 'INTERNACIONAL')
        """).fetchone()[0]
        if tipos_invalidos:
            raise ValueError(
                f"{tabla} tiene {tipos_invalidos} filas con tipo de abastecimiento inválido."
            )

    condiciones_conflictivas = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT UPPER(TRIM(TIPO_PROVEEDOR)) tipo
            FROM raw_dim_proveedor
            GROUP BY 1
            HAVING COUNT(DISTINCT CONDICION_PAGO) > 1
        )
    """).fetchone()[0]
    if condiciones_conflictivas:
        raise ValueError("Un tipo de abastecimiento tiene condiciones de pago contradictorias.")

    for tabla in ["raw_compras", "raw_ventas", "raw_pagos_proveedor", "raw_dim_producto"]:
        columnas = {fila[0].upper() for fila in con.execute(f"DESCRIBE {tabla}").fetchall()}
        if {"COD_PROVEEDOR", "TIPO_PROVEEDOR"}.issubset(columnas):
            con.execute(f"""
                UPDATE {tabla}
                SET COD_PROVEEDOR = UPPER(TRIM(TIPO_PROVEEDOR))
                WHERE COD_PROVEEDOR IS NOT NULL
            """)

    referencias_invalidas = con.execute("""
        SELECT COUNT(*)
        FROM raw_dim_producto
        WHERE REFERENCIA_PROVEEDOR IS NOT NULL
          AND (
              NOT regexp_matches(TRIM(REFERENCIA_PROVEEDOR), '^[A-Za-z0-9._/-]+( [A-Za-z0-9._/-]+)*$')
              OR NOT regexp_matches(TRIM(REFERENCIA_PROVEEDOR), '[0-9]')
          )
    """).fetchone()[0]
    if referencias_invalidas:
        con.execute("""
            UPDATE raw_dim_producto SET REFERENCIA_PROVEEDOR = NULL
            WHERE REFERENCIA_PROVEEDOR IS NOT NULL
              AND (
                  NOT regexp_matches(TRIM(REFERENCIA_PROVEEDOR), '^[A-Za-z0-9._/-]+( [A-Za-z0-9._/-]+)*$')
                  OR NOT regexp_matches(TRIM(REFERENCIA_PROVEEDOR), '[0-9]')
              )
        """)
        print(
            f"AVISO: se vaciaron {referencias_invalidas} referencias de producto "
            "que no parecían códigos."
        )

    con.execute("""
        CREATE OR REPLACE TABLE raw_dim_proveedor_publica AS
        SELECT UPPER(TRIM(d.TIPO_PROVEEDOR)) AS COD_PROVEEDOR,
               UPPER(TRIM(d.TIPO_PROVEEDOR)) AS TIPO_PROVEEDOR,
               ANY_VALUE(d.CONDICION_PAGO) AS CONDICION_PAGO
        FROM raw_dim_proveedor d
        GROUP BY 1
    """)
    con.execute("DROP TABLE raw_dim_proveedor")
    con.execute("ALTER TABLE raw_dim_proveedor_publica RENAME TO raw_dim_proveedor")
    con.execute("""
        UPDATE raw_dim_proveedor
        SET COD_PROVEEDOR = UPPER(TRIM(TIPO_PROVEEDOR))
    """)

    filas = con.execute("SELECT COUNT(*) FROM raw_dim_proveedor").fetchone()[0]
    if filas != 2:
        raise ValueError(f"Se esperaban 2 tipos de abastecimiento y se obtuvieron {filas}.")


def preparar_tabla_publica(nombre, df):
    if "COD_PROVEEDOR" in df.columns and "TIPO_PROVEEDOR" in df.columns:
        df["COD_PROVEEDOR"] = df["TIPO_PROVEEDOR"].str.strip().str.upper()
    if nombre == "DIM_PROVEEDOR":
        df["TIPO_PROVEEDOR"] = df["TIPO_PROVEEDOR"].str.strip().str.upper()
        df["COD_PROVEEDOR"] = df["TIPO_PROVEEDOR"]
        df = (
            df.groupby("TIPO_PROVEEDOR", as_index=False)
            .agg(COD_PROVEEDOR=("COD_PROVEEDOR", "first"),
                 CONDICION_PAGO=("CONDICION_PAGO", "first"))
        )
    return df


def main():
    publico = os.environ.get("FRAG_PUBLICO", "1").strip() == "1"
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else next((p for p in CANDIDATOS if p.exists()), None)
    out = BASE / "data" / "fragancias.duckdb"
    out.parent.mkdir(exist_ok=True)
    tmp = out.with_suffix(".tmp.duckdb")
    tmp.unlink(missing_ok=True)

    con = duckdb.connect(str(tmp))
    filas = {}
    if src is not None:
        hash_antes = sha256(src)
        xl = pd.read_excel(src, sheet_name=None)
        for h in HOJAS:
            if h not in xl:
                print(f"  (hoja {h} no existe en la fuente, se omite)")
                continue
            df = xl[h]
            for c in df.columns:
                if df[c].dtype == object:
                    df[c] = df[c].where(df[c].isna(), df[c].astype(str))
            if publico and h in {
                "COMPRAS", "VENTAS", "PAGOS_PROVEEDOR", "DIM_PRODUCTO", "DIM_PROVEEDOR",
            }:
                df = preparar_tabla_publica(h, df)
            con.register("df_tmp", df)
            con.execute(f'CREATE TABLE raw_{h.lower()} AS SELECT * FROM df_tmp')
            con.unregister("df_tmp")
            filas[h] = len(df)
            print(f"  raw_{h.lower():18s} {len(df):>6} filas")
        fuente_meta = str(src.relative_to(PROY)) if src.is_relative_to(PROY) else str(src)
    elif out.exists():
        origen = duckdb.connect(str(out), read_only=True)
        tablas = [fila[0] for fila in origen.execute("SHOW TABLES").fetchall()]
        for tabla in tablas:
            if not tabla.startswith("raw_"):
                continue
            df = origen.execute(f'SELECT * FROM "{tabla}"').df()
            if publico:
                nombre = tabla[4:].upper()
                if nombre == "DIM_PROVEEDOR":
                    columnas = set(df.columns)
                    if "TIPO_PROVEEDOR" in columnas and "CONDICION_PAGO" in columnas:
                        df = preparar_tabla_publica(nombre, df)
                elif {"COD_PROVEEDOR", "TIPO_PROVEEDOR"}.issubset(df.columns):
                    df = preparar_tabla_publica(nombre, df)
            con.register("df_tmp", df)
            con.execute(f'CREATE TABLE "{tabla}" AS SELECT * FROM df_tmp')
            con.unregister("df_tmp")
            filas[tabla[4:].upper()] = len(df)
            print(f"  {tabla:24s} {len(df):>6} filas (DuckDB existente)")
        meta_anterior = json.loads(origen.execute("SELECT json FROM meta").fetchone()[0])
        origen.close()
        hash_antes = meta_anterior.get("sha256_fuente", "")
        fuente_meta = meta_anterior.get("fuente", "DuckDB existente")
    else:
        con.close()
        tmp.unlink(missing_ok=True)
        raise FileNotFoundError(
            "No se encontró el Excel fuente ni una base DuckDB existente para reconstruir."
        )

    # columnas de enriquecimiento que pueden no existir en el archivo oficial
    cols_prod = {r[0] for r in con.execute("DESCRIBE raw_dim_producto").fetchall()}
    for c in [
        "NOMBRE_OFICIAL", "FAMILIA_OLFATIVA", "NOTAS_CLAVE", "IMAGEN_URL",
        "FUENTE_IMAGEN_URL", "FUENTE_COLECCION", "COLECCION", "MODELO",
    ]:
        if c not in cols_prod:
            con.execute(f'ALTER TABLE raw_dim_producto ADD COLUMN {c} VARCHAR')
    cols_m = {r[0] for r in con.execute("DESCRIBE raw_dim_marca").fetchall()}
    for c in ["LOGO_URL", "FUENTE_LOGO_URL"]:
        if c not in cols_m:
            con.execute(f'ALTER TABLE raw_dim_marca ADD COLUMN {c} VARCHAR')

    cuadre_antes = controlar_cuadre(con)
    if publico:
        anonimizar_por_tipo(con)

    con.execute((BASE / "sql" / "modelo.sql").read_text(encoding="utf-8"))

    cuadre_despues = controlar_cuadre(con)
    print(
        "  Cuadre antes de anonimizar: venta neta "
        f"{cuadre_antes[0]:,.2f} | unidades {cuadre_antes[1]:,.0f} | costo {cuadre_antes[2]:,.2f}"
    )
    print(
        "  Cuadre después de anonimizar: venta neta "
        f"{cuadre_despues[0]:,.2f} | unidades {cuadre_despues[1]:,.0f} | costo {cuadre_despues[2]:,.2f}"
    )
    if cuadre_antes != cuadre_despues:
        raise AssertionError("El cuadre cambió al anonimizar los proveedores.")
    fr = con.execute("SELECT ROUND(SUM(venta_neta),2), SUM(unidades), ROUND(SUM(margen_bruto),2) FROM f_ventas").fetchone()
    print(f"  Fragancias: venta neta {fr[0]:,.2f} | unidades {fr[1]} | margen {fr[2]:,.2f}")

    meta = {"fuente": fuente_meta, "sha256_fuente": hash_antes,
            "modo": "publico" if publico else "privado",
            "construido": dt.datetime.now().isoformat(timespec="seconds"),
            "filas": filas}
    con.execute("CREATE TABLE meta AS SELECT ? AS json", [json.dumps(meta)])
    con.close()
    tmp.replace(out)

    if src is not None:
        assert sha256(src) == hash_antes, "El archivo fuente cambió durante la lectura"
        print(f"Fuente intacta, sha256 {hash_antes[:12]}…")
    print(f"Modo de construcción: {'público' if publico else 'privado'}")
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
