# Fragrance Intelligence

Aplicación de inteligencia de negocios para analizar ventas, compras, inventario y rentabilidad de la categoría de fragancias. El proyecto transforma hojas de cálculo operativas en métricas auditables y una aplicación interactiva para apoyar decisiones comerciales y de abastecimiento.

## Problema de negocio

La información de ventas, compras, inventario y proveedores requiere un análisis conjunto para identificar productos líderes, oportunidades de margen y riesgos de disponibilidad. Fragrance Intelligence integra esas fuentes, aplica filtros de producto y periodo, y presenta indicadores y acciones sugeridas en un solo lugar.

## Hallazgos principales

Con los datos incluidos y sin filtros de producto, el resumen de 2026 muestra:

- Venta neta de aproximadamente **$585,7 mil**, con crecimiento interanual de **17,8%**.
- Margen bruto de **52,0%** y ticket promedio de **$380**.
- **1.541** facturas y **930** clientes activos.
- **BOND NO. 9** es la marca líder en venta; **Creed** presenta el mayor crecimiento absoluto en USD.
- El resumen señala quiebres entre los SKU de mayor venta y muestra la comparación de costos de proveedores basada en el historial disponible.

Las cifras responden a los filtros seleccionados en la app; la vista y el periodo de comparación se indican en pantalla.

## Arquitectura

**Excel → DuckDB/SQL → Python → R → Streamlit**

1. **Excel:** fuente operativa de ventas, compras, inventario y dimensiones. El proceso de construcción la lee sin modificarla.
2. **DuckDB y SQL:** `etl/construir_duckdb.py` carga tablas `raw_*`; `sql/modelo.sql` define vistas de hechos y dimensiones con las reglas de negocio.
3. **Python:** `lib/` centraliza acceso de solo lectura y filtros SQL; `vistas/` implementa indicadores, visualizaciones y simulaciones.
4. **R:** `R/estadistica_forecast.R` genera análisis estadísticos y pronósticos. Sus resultados CSV ya se incluyen en `data/r_outputs/`; ejecutar R no es necesario para iniciar la app.
5. **Streamlit:** `app.py` integra las pantallas y filtros globales.

## Capturas

<!-- Sustituir estos marcadores por capturas propias de la aplicación antes de publicar. -->

### Resumen gerencial

`[Marcador: captura de la pantalla Resumen gerencial]`

### Ventas y análisis estadístico

`[Marcador: captura de Ventas o Estadística]`

## Trazabilidad y controles

- DuckDB se consulta desde la app en modo de solo lectura.
- El ETL comprueba la huella SHA-256 del Excel antes y después de leerlo para verificar que la fuente no se alteró.
- Los controles de la fuente reproducen venta neta Belleza de **$1.116.355,49**, **5.066** unidades y costo de **$568.122,69**.
- Para Fragancias, los controles de referencia son **$1.082.810** en venta neta, **4.641** unidades y margen bruto de **49,4%**.
- El repositorio incluye la base DuckDB preparada y los resultados de R para que Streamlit Community Cloud pueda arrancar sin el Excel original ni R instalado.
- En la versión pública, las compras y pagos se agrupan por tipo de abastecimiento (Nacional / Internacional); los clientes se identifican con códigos.
- Fechas redistribuidas 2025–2026; proveedores agrupados por tipo; clientes codificados.
- Las imágenes usan enlaces del maestro o archivos de caché local. Verifica los derechos de uso de las imágenes antes de distribuirlas públicamente.

## Reglas de negocio

- El alcance de los hechos es la categoría Fragancias; las vistas de SQL conservan las hojas de origen y centralizan las reglas derivadas.
- La venta neta, las unidades, los costos y el margen se agregan desde los hechos; las devoluciones y notas de crédito conservan su signo en la fuente.
- Precio de lista = costo por **2,5**; precio de lista con IVA = precio de lista por **1,16**.
- Crédito a 30 días solo para clientes VIP/accionistas; ventas de contado: 30% efectivo y 70% punto de venta, con comisión de 2,5%.
- Proveedores nacionales se pagan contra venta; proveedores internacionales, de contado.
- Las alertas, variaciones y simulaciones están sujetas a los filtros que cada pantalla indica; las sugerencias de reposición no generan órdenes.

## Ejecutar localmente

Requiere Python 3.11 o superior para el entorno recomendado:

```bash
git clone https://github.com/<usuario>/fragrance-intelligence.git
cd fragrance-intelligence
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

La aplicación utiliza `data/fragancias.duckdb`, `static/img/` y `data/r_outputs/`. No requiere Excel ni ejecutar R durante el arranque.

## Pruebas

```bash
python tests/test_vistas.py
```

El resultado esperado al final es `FALLOS: 0`.

## Despliegue en Streamlit Community Cloud

1. Crea o selecciona el repositorio público `fragrance-intelligence` en GitHub.
2. En [share.streamlit.io](https://share.streamlit.io), elige ese repositorio y la rama `main`.
3. Indica `app.py` como archivo principal.
4. En **Advanced settings**, selecciona Python **3.11** y despliega.
