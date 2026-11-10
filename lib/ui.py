"""Estilos y componentes visuales (paleta de la maqueta aprobada)."""
from __future__ import annotations
import base64
import html
from pathlib import Path
import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parents[1]
VINO, VINO_OSC, ROSA, ROSA_CL, ORO, TINTA = "#8E3B5A", "#5E2139", "#B8587A", "#E8A0B4", "#C9A46A", "#2A1520"
VERDE, ROJO, AZUL, OLIVA, GRIS = "#2F6B5A", "#A3284F", "#3E6E8E", "#7A8F5C", "#D9C9CF"
SERIE = [VINO_OSC, ROSA, "#CDB3BD", AZUL, OLIVA, "#6B4E5A", "#9FB7C9"]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');
html, body, [data-testid="stAppViewContainer"], .stApp, .stMarkdown, p, label {
  font-family: Inter, system-ui, sans-serif; background-color: #FCF8F9;
}
.block-container { padding-top: 1.6rem; max-width: 1280px; }
section[data-testid="stSidebar"] { background: #2A1520; }
section[data-testid="stSidebar"] * { color: #E9D6DD; }
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div { background: transparent; }
section[data-testid="stSidebar"] [data-baseweb="select"] > div { background: #3A1F2C; border-color: #5A3546; }
section[data-testid="stSidebar"] [data-baseweb="tag"] { background: #8E3B5A; }
section[data-testid="stSidebar"] [data-testid="stPageLink"] a {
  display: block; padding: 10px 14px; border-radius: 12px; font-size: 17px;
  color: #E9D6DD; text-decoration: none; background: transparent;
}
section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover { background: #3A1F2C; }
section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"]:hover {
  background: #8E3B5A; color: #fff; font-weight: 700;
}
.fi-sidebar-logo { margin: 4px 0 20px; }
section[data-testid="stSidebar"] .fi-sidebar-logo-main {
  font-family: 'Cormorant Garamond', serif; font-size: 34px; line-height: 1;
  color: #E6C99A !important; background: transparent;
}
section[data-testid="stSidebar"] .fi-sidebar-logo-sub {
  margin-top: 5px; font-size: 12px; letter-spacing: 6px; line-height: 1.2;
  color: #E8A0B4 !important; background: transparent;
}
.fi-sidebar-divider { border: 0; border-top: 1px solid #4A2A38; margin: 18px 0; }
.fi-sidebar-note { margin-top: 12px; font-size: 13px; line-height: 1.5; color: #C9A9B6 !important; }
section[data-testid="stSidebar"] [data-testid="stPageLink"] a[href=""] {
  background: #8E3B5A; color: #fff; font-weight: 700;
}
::selection { background: #E8A0B4; color: #2A1520; }
h1, h2, h3 { font-family: 'Cormorant Garamond', serif !important; color: #2A1520; }
.fi-eyebrow { font-size: 12px; letter-spacing: 3px; color: #8E3B5A; font-weight: 600; text-transform: uppercase; }
.fi-h1 { font-family: 'Cormorant Garamond', serif; font-size: 44px; font-weight: 600; margin: 2px 0 6px; line-height: 1.05; }
.fi-filtro { font-size: 13px; color: #6B4E5A; background: #fff; border: 1px solid #EAD7DD; border-radius: 999px; padding: 6px 14px; display: inline-block; }
.fi-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 14px; margin: 8px 0 18px; }
.fi-kpi { background: #fff; border: 1px solid #EAD7DD; border-radius: 16px; padding: 16px 18px; }
.fi-kpi .l { font-size: 12px; color: #6B4E5A; font-weight: 500; }
.fi-kpi .v { font-family: 'Cormorant Garamond', serif; font-size: 31px; font-weight: 700; color: #5E2139; line-height: 1.1; }
.fi-kpi .v.t { font-size: 22px; line-height: 1.15; }
.fi-kpi .s { font-size: 12px; color: #8E3B5A; }
.fi-hero { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; margin-bottom: 18px; }
.fi-hcard { border-radius: 24px; padding: 24px; display: flex; gap: 22px; align-items: center; flex-wrap: wrap; }
.fi-hcard.dark { background: #4A1F33; color: #F8EAF0; }
.fi-hcard.light { background: #fff; border: 1px solid #EAD7DD; }
.fi-hcard .ph { flex: 0 0 190px; height: 240px; border-radius: 18px; background: #fff; position: relative; overflow: hidden; }
.fi-hcard .tag { font-size: 12px; letter-spacing: 2px; font-weight: 600; }
.fi-hcard.dark .tag { color: #E8A0B4; } .fi-hcard.light .tag { color: #8E3B5A; }
.fi-hcard .nm { font-family: 'Cormorant Garamond', serif; font-size: 32px; font-weight: 600; line-height: 1.05; margin: 4px 0; }
.fi-hcard .sb { font-size: 13px; opacity: .85; }
.fi-hcard .nums { display: flex; gap: 26px; margin-top: 10px; flex-wrap: wrap; }
.fi-hcard .nums b { display: block; font-size: 27px; }
.fi-hcard .nums span { font-size: 12px; opacity: .8; }
.fi-logo { height: 30px; max-width: 140px; object-fit: contain; object-position: left; display: block; margin-bottom: 6px; }
.fi-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(168px, 1fr)); gap: 14px; }
.fi-card { background: #FBF6F7; border-radius: 18px; padding: 12px; position: relative; display: flex; flex-direction: column; gap: 6px; }
.fi-card .rk { position: absolute; top: 10px; left: 10px; z-index: 3; background: #5E2139; color: #fff; border-radius: 999px; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; }
.fi-card .ph { height: 170px; border-radius: 12px; background: #fff; position: relative; overflow: hidden; }
.fi-ph-ini { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #F3E3E8; color: #5E2139; }
.fi-ph-ini b { font-family: 'Cormorant Garamond', serif; font-size: 64px; font-weight: 600; }
.fi-ph-ini small { font-size: 10px; color: #5E2139; text-transform: uppercase; text-align: center; }
.fi-ph-img { position: absolute; inset: 6px; width: calc(100% - 12px); height: calc(100% - 12px); object-fit: contain; background: #fff; z-index: 2; color: transparent; font-size: 0; }
.fi-card .br { font-size: 11px; letter-spacing: 1px; color: #8E3B5A; font-weight: 600; }
.fi-card .nm { font-size: 14px; font-weight: 600; line-height: 1.2; min-height: 34px; color: #2A1520; }
.fi-card .row { display: flex; justify-content: space-between; align-items: baseline; }
.fi-card .big { font-size: 20px; font-weight: 700; color: #5E2139; }
.fi-card .sm { font-size: 12px; color: #6B4E5A; }
.fi-bar { background: #EFE1E6; border-radius: 6px; height: 6px; } .fi-bar > div { height: 6px; border-radius: 6px; background: #8E3B5A; }
.fi-panel { background: #fff; border: 1px solid #EAD7DD; border-radius: 20px; padding: 18px 20px; margin-bottom: 14px; }
.fi-note { font-size: 12px; color: #6B4E5A; line-height: 1.5; }
.fi-alert { font-size: 13px; color: #8E3B5A; font-weight: 500; }
.fi-brandrow { display: grid; grid-template-columns: 96px 1fr 78px; gap: 10px; align-items: center; font-size: 13px; margin: 6px 0; }
.fi-brandrow img { width: 90px; height: 28px; object-fit: contain; object-position: left; }
.fi-brandrow .b { background: #F3E3E8; border-radius: 6px; height: 16px; } .fi-brandrow .b > div { height: 16px; border-radius: 6px; background: #8E3B5A; }
div[data-testid="stTabs"] button p { font-weight: 600; }
</style>
"""


def estilos():
    st.markdown(CSS, unsafe_allow_html=True)


# ---------- formato (es: coma decimal, punto de miles) ----------
def _es(s: str) -> str:
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def usd(x, dec=0) -> str:
    if x is None or pd.isna(x): return "—"
    a = abs(x)
    if a >= 1e6: return _es(f"${x/1e6:,.2f} M")
    if a >= 1e4: return _es(f"${x/1e3:,.1f} k")
    return _es(f"${x:,.{dec}f}")


def num(x, dec=0) -> str:
    return "—" if x is None or pd.isna(x) else _es(f"{x:,.{dec}f}")


def pct(x, dec=1, signo=False) -> str:
    if x is None or pd.isna(x): return "—"
    return _es(f"{x*100:{'+' if signo else ''}.{dec}f}%")


def esc(s) -> str:
    return html.escape("" if s is None or (isinstance(s, float) and pd.isna(s)) else str(s))


def titulo(eyebrow: str, h1: str, filtros_desc: str | None = None):
    extra = f'<span class="fi-filtro" translate="no">{esc(filtros_desc)}</span>' if filtros_desc else ""
    st.markdown(f'<div class="fi-eyebrow" translate="no">{esc(eyebrow)}</div>'
                f'<div class="fi-h1" translate="no">{esc(h1)}</div>{extra}',
                unsafe_allow_html=True)


def kpis(items: list[tuple[str, str, str]]):
    cards = "".join(f'<div class="fi-kpi" translate="no"><div class="l">{esc(l)}</div><div class="v{" t" if len(str(v)) > 12 else ""}">{esc(v)}</div>'
                    f'<div class="s">{esc(s)}</div></div>' for l, v, s in items)
    st.markdown(f'<div class="fi-kpis" translate="no">{cards}</div>', unsafe_allow_html=True)


def iniciales(marca: str) -> str:
    return "".join(w[0] for w in str(marca or "?").replace("&", " ").split() if w[0].isalnum())[:2].upper()


def corto(texto: str) -> str:
    texto = str(texto)
    return texto if len(texto) <= 28 else texto[:28] + "…"


# ---------- imágenes: caché local (static/img) o URL oficial ----------
@st.cache_data
def _manifest() -> dict:
    p = BASE / "data" / "imagenes_manifest.csv"
    if not p.exists(): return {}
    m = pd.read_csv(p).fillna("")
    return {r.url: r.archivo for r in m.itertuples() if r.estado == "OK" and (BASE / "static" / "img" / r.archivo).exists()}


def img_src(url) -> str | None:
    if url is None or (isinstance(url, float) and pd.isna(url)) or not str(url).strip():
        return None
    f = _manifest().get(url)
    return f"app/static/img/{f}" if f else str(url)


def foto(url, marca, alt="") -> str:
    """Monograma de respaldo con la imagen encima cuando está disponible."""
    src = img_src(url)
    ini = (f'<div class="fi-ph-ini" translate="no"><b>{esc(iniciales(marca))}</b>'
           f'<small>{esc(str(marca).upper())}</small></div>')
    im = (f'<img class="fi-ph-img" src="{esc(src)}" alt="{esc(alt)}" loading="lazy" '
          'onerror="this.style.display=\'none\'" translate="no">') if src else ""
    return ini + im


def logo_html(url, marca, clase="fi-logo") -> str:
    """Usa la caché local cuando existe y la URL oficial como alternativa."""
    f = _manifest().get(url) if isinstance(url, str) else None
    if f:
        image = BASE / "static" / "img" / f
        if image.suffix.lower() == ".svg":
            src = "data:image/svg+xml;base64," + base64.b64encode(image.read_bytes()).decode("ascii")
        else:
            src = f"app/static/img/{esc(f)}"
    elif isinstance(url, str) and url.strip():
        src = esc(url)
    else:
        return ""
    return f'<img class="{esc(clase)}" src="{src}" alt="Logo {esc(marca)}" translate="no">'


def tarjetas(df: pd.DataFrame, valor: str, etiqueta_valor: str, logos: dict):
    """Grilla Top N con imagen. df: salida de lib.db.ranking."""
    if df.empty:
        st.info("Sin ventas para los filtros seleccionados."); return
    mx = df[valor].max() or 1
    out = []
    for i, r in enumerate(df.itertuples(), 1):
        if valor == "venta": big = usd(r.venta)
        elif valor == "unidades": big = f"{num(r.unidades)} un"
        elif valor == "margen": big = usd(r.margen)
        else: big = pct(r.margen_pct)
        sub = f"{num(r.unidades)} un · {pct(r.margen_pct, 0)} mg" if valor != "unidades" else f"{usd(r.venta)} · {pct(r.margen_pct, 0)} mg"
        w = max(2, min(100, (getattr(r, valor) or 0) / mx * 100))
        out.append(f'''<div class="fi-card" translate="no"><div class="rk">{i}</div>
          <div class="ph">{foto(r.imagen_url, r.marca, f"Frasco {r.marca} {r.nombre}")}</div>
          <div class="br" translate="no">{esc(r.marca)}</div><div class="nm" translate="no">{esc(str(r.nombre).title() if str(r.nombre).isupper() else r.nombre)}</div>
          <div class="row"><span class="big">{esc(big)}</span></div><div class="sm">{esc(sub)}</div>
          <div class="fi-bar"><div style="width:{w:.0f}%"></div></div></div>''')
    st.markdown(f'<div class="fi-grid" translate="no">{"".join(out)}</div>', unsafe_allow_html=True)


def plotly_base(fig, h=360, leyenda=True):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                      font=dict(family="Inter, sans-serif", color=TINTA, size=12), showlegend=leyenda,
                      legend=dict(orientation="h", yanchor="top", y=-0.12, x=0, title=None),
                      separators=",.", hoverlabel=dict(bgcolor="#fff"))
    fig.update_xaxes(showgrid=False, linecolor="#EAD7DD")
    fig.update_yaxes(gridcolor="#F3E6EA", zeroline=False)
    return fig


def titulo_caso(s: str) -> str:
    return s.title() if isinstance(s, str) and s.isupper() else s
