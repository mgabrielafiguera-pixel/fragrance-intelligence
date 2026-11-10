"""Fase 4 - Descarga (caché local) de imágenes de producto y logos citados en DIM_PRODUCTO / DIM_MARCA.

Uso:  python etl/descargar_imagenes.py
- Solo descarga URLs que ya están en la base (no busca imágenes nuevas).
- Guarda en static/img/<hash>.<ext> y registra el resultado en data/imagenes_manifest.csv
  (url, archivo, estado). Si un host bloquea la descarga (p. ej. dior.com → 403), la app
  intenta mostrar la URL original y, si tampoco carga, muestra las iniciales de la marca.
"""
import hashlib, io, mimetypes
from pathlib import Path
import duckdb, pandas as pd, requests
from PIL import Image

LADO_MAX = 640  # px: suficiente para tarjetas; reduce el peso del repositorio

BASE = Path(__file__).resolve().parents[1]
IMG = BASE / "static" / "img"
IMG.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (portfolio-analytics image cache)"}


def nombre(url: str, ctype: str) -> str:
    ext = mimetypes.guess_extension((ctype or "").split(";")[0].strip()) or Path(url.split("?")[0]).suffix or ".img"
    if ext == ".jpe": ext = ".jpg"
    return hashlib.sha1(url.encode()).hexdigest()[:16] + ext


def guardar(contenido: bytes, f: str) -> str:
    """Raster → WebP redimensionado (conserva transparencia). SVG se guarda tal cual."""
    if f.endswith(".svg"):
        (IMG / f).write_bytes(contenido); return f
    im = Image.open(io.BytesIO(contenido))
    im = im.convert("RGBA")
    im.thumbnail((LADO_MAX, LADO_MAX))
    f = Path(f).stem + ".webp"
    im.save(IMG / f, "WEBP", quality=85, method=6)
    return f


def main():
    con = duckdb.connect(str(BASE / "data" / "fragancias.duckdb"), read_only=True)
    urls = con.execute("""
        SELECT DISTINCT imagen_url AS url FROM dim_producto WHERE imagen_url IS NOT NULL
        UNION SELECT DISTINCT logo_url FROM dim_marca WHERE logo_url IS NOT NULL
    """).df().url.tolist()
    con.close()
    man_p = BASE / "data" / "imagenes_manifest.csv"
    previo = pd.read_csv(man_p) if man_p.exists() else pd.DataFrame(columns=["url", "archivo", "estado"])
    ok_prev = {r.url: r for r in previo.itertuples() if r.estado == "OK" and (IMG / str(r.archivo)).exists()}
    filas = []
    for u in urls:
        if u in ok_prev:
            filas.append({"url": u, "archivo": ok_prev[u].archivo, "estado": "OK"}); continue
        try:
            r = requests.get(u, headers=UA, timeout=25)
            if r.status_code == 200 and r.content:
                f = nombre(u, r.headers.get("content-type", ""))
                f = guardar(r.content, f)
                filas.append({"url": u, "archivo": f, "estado": "OK"})
            else:
                filas.append({"url": u, "archivo": "", "estado": f"HTTP {r.status_code}"})
        except Exception as e:  # red, timeout, TLS
            filas.append({"url": u, "archivo": "", "estado": f"ERROR {type(e).__name__}"})
    m = pd.DataFrame(filas)
    m.to_csv(man_p, index=False)
    print(m.estado.value_counts().to_string())


if __name__ == "__main__":
    main()
