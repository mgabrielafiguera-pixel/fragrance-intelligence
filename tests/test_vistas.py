"""Prueba de humo: cada pantalla se renderiza sin errores con distintos filtros.
Ejecutar: python tests/test_vistas.py"""
from pathlib import Path
from streamlit.testing.v1 import AppTest

SCRIPT = str(Path(__file__).with_name("_pagina.py"))
CASOS = [{}, {"marcas": ["MONTBLANC"]}, {"marcas": ["CREED", "DIOR"], "desde": "2026-01-01"},
         {"generos": ["DAMA"], "desde": "2025-05-01", "hasta": "2025-05-31"}, {"marcas": ["XERJOFF"], "tamanos": [100.0]}]
fallos = 0
for f in CASOS:
    for v in ["resumen", "ventas", "compras", "rentabilidad", "estadistica", "metodologia"]:
        at = AppTest.from_file(SCRIPT, default_timeout=90)
        at.session_state["cfg"] = {"vista": v, "filtros": f}
        at.run()
        estado = "ok" if not at.exception else "ERROR: " + at.exception[0].value[:300]
        fallos += bool(at.exception)
        print(f"{v:13s} {str(f):70s} {estado}")
print("FALLOS:", fallos)
