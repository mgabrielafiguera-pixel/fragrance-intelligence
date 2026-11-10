-- =====================================================================
-- Fragrance Intelligence · Modelo de datos (DuckDB)
-- Ventas y compras forman un solo almacén. Alcance: SUBCATEGORIA = 'FRAGANCIA'.
-- Las tablas raw_* son copia 1:1 de las hojas del archivo de trabajo.
-- Las vistas de abajo solo renombran, filtran y derivan; no se imputan datos.
-- =====================================================================

-- Dimensión producto (solo fragancias). Jerarquía: Marca > Colección > Modelo > Versión > ml
CREATE OR REPLACE VIEW dim_producto AS
SELECT
    COD_SKU                                   AS sku,
    MARCA                                     AS marca,
    COALESCE(NULLIF(COLECCION,''),'(SIN COLECCIÓN)') AS coleccion,
    COALESCE(NULLIF(MODELO,''),'(SIN MODELO)')       AS modelo,
    COALESCE(NULLIF(VERSION,''),'(SIN VERSIÓN)')     AS version,
    TRY_CAST(TAMANO_ML AS DOUBLE)             AS tamano_ml,
    GENERO                                    AS genero,
    CONCENTRACION                             AS concentracion,
    NULLIF(FAMILIA_OLFATIVA,'')               AS familia_olfativa,
    NULLIF(NOMBRE_OFICIAL,'')                 AS nombre_oficial,
    NULLIF(NOTAS_CLAVE,'')                    AS notas_clave,
    NULLIF(IMAGEN_URL,'')                     AS imagen_url,
    NULLIF(FUENTE_IMAGEN_URL,'')              AS fuente_imagen_url,
    NULLIF(FUENTE_COLECCION,'')               AS fuente_coleccion,
    COD_PROVEEDOR                             AS cod_proveedor_maestro,
    TIPO_PROVEEDOR                            AS tipo_proveedor_maestro,
    ES_SET                                    AS es_set,
    DESCRIPCION                               AS descripcion,
    -- nombre corto: nombre oficial web solo si no trae concentración/tamaño (esos se toman del maestro por SKU)
    CASE WHEN regexp_matches(COALESCE(NOMBRE_OFICIAL,''), '(?i)(\d+ ?ml|eau de|\bedp\b|\bedt\b|parfum|cologne|elixir)')
         THEN NULL ELSE NULLIF(NOMBRE_OFICIAL,'') END AS nombre_corto,
    -- etiqueta legible del SKU: nombre corto (o versión del maestro) + concentración + ml
    COALESCE(CASE WHEN regexp_matches(COALESCE(NOMBRE_OFICIAL,''), '(?i)(\d+ ?ml|eau de|\bedp\b|\bedt\b|parfum|cologne|elixir)')
                  THEN NULL ELSE NULLIF(NOMBRE_OFICIAL,'') END, VERSION, MODELO)
        || COALESCE(' ' || CONCENTRACION, '')
        || COALESCE(' ' || CAST(CAST(TRY_CAST(TAMANO_ML AS DOUBLE) AS INTEGER) AS VARCHAR) || ' ml', '')
        || CASE WHEN UPPER(TRIM(ES_SET)) = 'SI' THEN ' (set)' ELSE '' END AS etiqueta
FROM raw_dim_producto
WHERE SUBCATEGORIA = 'FRAGANCIA';

CREATE OR REPLACE VIEW dim_marca AS
SELECT MARCA AS marca, COD_MARCA AS cod_marca,
       NULLIF(LOGO_URL,'') AS logo_url, NULLIF(FUENTE_LOGO_URL,'') AS fuente_logo_url
FROM raw_dim_marca;

-- Hechos de venta (línea de factura). Devoluciones N/CR vienen con signo negativo.
CREATE OR REPLACE VIEW f_ventas AS
SELECT
    v.NUM_FACTURA AS factura, v.MOV AS mov,
    CAST(v.FECHA AS DATE) AS fecha, CAST(v.ANIO AS INTEGER) AS anio, CAST(v.MES AS INTEGER) AS mes,
    strftime(CAST(v.FECHA AS DATE), '%Y-%m') AS periodo,
    v.COD_SKU AS sku, v.COD_PROVEEDOR AS cod_proveedor, v.TIPO_PROVEEDOR AS tipo_proveedor,
    v.COD_CLIENTE AS cod_cliente, v.CLIENTE_VIP AS cliente_vip,
    v.CONDICION_PAGO AS condicion_pago, CAST(v.FECHA_COBRO AS DATE) AS fecha_cobro, v.MEDIO_COBRO AS medio_cobro,
    CAST(v.COMISION_POS AS DOUBLE) AS comision_pos, CAST(v.COBRO_NETO AS DOUBLE) AS cobro_neto,
    v.COD_VENDEDOR AS cod_vendedor,
    CAST(v.UNIDADES AS DOUBLE) AS unidades,
    CAST(v.PRECIO_UNIT_FACTURADO AS DOUBLE) AS precio_unit,
    CAST(v.VENTA_NETA AS DOUBLE) AS venta_neta,
    CAST(v.COSTO_UNIT AS DOUBLE) AS costo_unit, v.ORIGEN_COSTO AS origen_costo,
    CAST(v.COSTO_TOTAL AS DOUBLE) AS costo_total,
    CAST(v.MARGEN_BRUTO AS DOUBLE) AS margen_bruto,
    CAST(v.PRECIO_LISTA AS DOUBLE) AS precio_lista,          -- costo de referencia x 2,5
    CAST(v.PRECIO_LISTA_CON_IVA AS DOUBLE) AS precio_lista_iva,
    v.COMPARACION_LISTA AS comparacion_lista,
    CAST(v.DESV_VS_LISTA_PCT AS DOUBLE) AS desv_vs_lista_pct,
    v.ALERTA_BAJO_COSTO AS alerta_bajo_costo
FROM raw_ventas v
JOIN dim_producto p ON p.sku = v.COD_SKU;

-- Hechos de compra (línea de recepción). Costo nacionalizado = costo de adquisición puesto en almacén.
CREATE OR REPLACE VIEW f_compras AS
SELECT
    c.DOC_RECEPCION AS documento, c.TIPO_MOVI AS tipo_movi,
    CAST(c.FECHA_RECEPCION AS DATE) AS fecha, CAST(c.FECHA_INVOICE AS DATE) AS fecha_invoice,
    CAST(c.ANIO AS INTEGER) AS anio, CAST(c.MES AS INTEGER) AS mes,
    strftime(CAST(c.FECHA_RECEPCION AS DATE), '%Y-%m') AS periodo,
    c.COD_SKU AS sku, c.COD_PROVEEDOR AS cod_proveedor, c.TIPO_PROVEEDOR AS tipo_proveedor,
    CAST(c.UNIDADES AS DOUBLE) AS unidades,
    CAST(c.COSTO_NAC_UNIT AS DOUBLE) AS costo_nac_unit,
    CAST(c.COSTO_EXW_UNIT AS DOUBLE) AS costo_exw_unit,
    CAST(c.FACTOR_NACIONALIZACION AS DOUBLE) AS factor_nacionalizacion,
    c.ALERTA_FACTOR AS alerta_factor,
    CAST(c.TOTAL_COSTO_NAC AS DOUBLE) AS total_costo_nac,
    CAST(c.TOTAL_COSTO_EXW AS DOUBLE) AS total_costo_exw
FROM raw_compras c
JOIN dim_producto p ON p.sku = c.COD_SKU;

-- Inventario mensual por SKU: final = inicial + compras - ventas (regla de la fase 2)
CREATE OR REPLACE VIEW f_inventario AS
SELECT
    i.COD_SKU AS sku, i.PERIODO AS periodo,
    CAST(i.INV_INICIAL_UN AS DOUBLE) AS inv_inicial_un,
    CAST(i.COMPRAS_UN AS DOUBLE) AS compras_un,
    CAST(i.VENTAS_UN AS DOUBLE) AS ventas_un,
    CAST(i.INV_FINAL_UN AS DOUBLE) AS inv_final_un,
    CAST(i.COSTO_REF AS DOUBLE) AS costo_ref,
    CAST(i.VALOR_INV_FINAL AS DOUBLE) AS valor_inv_final
FROM raw_inventario_mes i
JOIN dim_producto p ON p.sku = i.COD_SKU;

-- Pagos a proveedores: nacionales contra venta; internacionales de contado (fecha invoice)
CREATE OR REPLACE VIEW f_pagos AS
SELECT
    g.COD_PROVEEDOR AS cod_proveedor, g.TIPO_PROVEEDOR AS tipo_proveedor, g.ORIGEN AS origen,
    g.DOCUMENTO AS documento, g.COD_SKU AS sku, CAST(g.UNIDADES AS DOUBLE) AS unidades,
    CAST(g.MONTO AS DOUBLE) AS monto,
    CAST(g.FECHA_OBLIGACION AS DATE) AS fecha_obligacion, CAST(g.FECHA_PAGO AS DATE) AS fecha_pago,
    strftime(CAST(g.FECHA_PAGO AS DATE), '%Y-%m') AS periodo_pago
FROM raw_pagos_proveedor g
JOIN dim_producto p ON p.sku = g.COD_SKU;

CREATE OR REPLACE VIEW dim_proveedor AS
SELECT COD_PROVEEDOR AS cod_proveedor, TIPO_PROVEEDOR AS tipo_proveedor, CONDICION_PAGO AS condicion_pago
FROM raw_dim_proveedor;
