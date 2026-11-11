"""Fragrance Intelligence · App Streamlit (Belleza · Fragancias · 2025–2026)

Ejecutar:  streamlit run app.py
Requisito: data/fragancias.duckdb (python etl/construir_duckdb.py)
"""
import datetime as dt
import json
import streamlit as st
import streamlit.components.v1 as components
from lib.db import Filtros, q
from lib import ui

st.set_page_config(page_title="Fragrance Intelligence", page_icon="◆", layout="wide")
ui.estilos()


def _opciones(campo: str, f_previos: Filtros) -> list:
    w, p = f_previos.sku_sql()
    return q(f"SELECT DISTINCT {campo} AS v FROM dim_producto WHERE {w} AND {campo} IS NOT NULL ORDER BY 1", p).v.tolist()


def filtros_globales() -> Filtros:
    sb = st.sidebar
    sb.markdown("### Filtros")
    f = Filtros()
    # cascada: cada lista depende de lo elegido arriba
    f.marcas = sb.multiselect("Marca", _opciones("marca", f), key="f_marca", placeholder="Todas")
    f.colecciones = sb.multiselect("Colección", _opciones("coleccion", f), key="f_col", placeholder="Todas")
    f.modelos = sb.multiselect("Modelo", _opciones("modelo", f), key="f_mod", placeholder="Todos")
    f.versiones = sb.multiselect("Versión", _opciones("version", f), key="f_ver", placeholder="Todas")
    f.tamanos = sb.multiselect("Tamaño (ml)", _opciones("tamano_ml", f), key="f_ml", placeholder="Todos",
                               format_func=lambda x: f"{x:g} ml")
    f.generos = sb.multiselect("Género", _opciones("genero", f), key="f_gen", placeholder="Todos")
    per = sb.date_input("Periodo", value=(dt.date(2025, 1, 1), dt.date(2026, 12, 31)),
                        min_value=dt.date(2025, 1, 1), max_value=dt.date(2026, 12, 31), key="f_per", format="DD/MM/YYYY")
    if isinstance(per, (list, tuple)) and len(per) == 2:
        f.desde, f.hasta = per[0].isoformat(), per[1].isoformat()
    sb.markdown(
        '<div class="fi-sidebar-note" translate="no">'
        'Los modelos se calculan en R (tidyverse, rstatix, forecast) y se exportan como tablas que Streamlit muestra.'
        '<br><br>Datos ficticios con fines de portafolio.</div>',
        unsafe_allow_html=True,
    )
    return f


from vistas import resumen, ventas, compras, rentabilidad, estadistica, metodologia  # noqa: E402

paginas = [
    st.Page(resumen.render, title="Resumen gerencial", url_path="resumen", default=True),
    st.Page(ventas.render, title="Ventas", url_path="ventas"),
    st.Page(compras.render, title="Compras y abastecimiento", url_path="compras"),
    st.Page(rentabilidad.render, title="Rentabilidad e inventario", url_path="rentabilidad"),
    st.Page(estadistica.render, title="Estadística (R)", url_path="estadistica"),
    st.Page(metodologia.render, title="Metodología y controles", url_path="metodologia"),
]
nav = st.navigation(paginas, position="hidden")
sidebar = st.sidebar
sidebar.markdown(
    '<div class="fi-sidebar-logo" translate="no">'
    '<div class="fi-sidebar-logo-main">FRAGRANCE</div>'
    '<div class="fi-sidebar-logo-sub">INTELLIGENCE</div>'
    '</div>',
    unsafe_allow_html=True,
)
for pagina in paginas:
    sidebar.page_link(pagina, label=pagina.title)
script = """
<script>
  const parentDocument = window.parent.document;
  const root = parentDocument.documentElement;
  root.lang = 'es';
  root.setAttribute('translate', 'no');
  if (!parentDocument.querySelector('meta[name="google"][content="notranslate"]')) {
    const meta = parentDocument.createElement('meta');
    meta.name = 'google';
    meta.content = 'notranslate';
    parentDocument.head.appendChild(meta);
  }
  const activePagePath = __ACTIVE_PAGE_PATH__;
  const markActivePage = () => {
    parentDocument.querySelectorAll(
      'section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]'
    ).forEach((link) => {
      const active = link.getAttribute('href') === activePagePath;
      if (active && link.getAttribute('aria-current') !== 'page') {
        link.setAttribute('aria-current', 'page');
      } else if (!active && link.hasAttribute('aria-current')) {
        link.removeAttribute('aria-current');
      }
    });
  };
  markActivePage();
  new MutationObserver(markActivePage).observe(parentDocument.body, {
    childList: true,
    subtree: true
  });
</script>
""".replace("__ACTIVE_PAGE_PATH__", json.dumps(nav.url_path))
components.html(script, height=0)
sidebar.markdown('<hr class="fi-sidebar-divider">', unsafe_allow_html=True)
st.session_state["filtros"] = filtros_globales()
nav.run()
