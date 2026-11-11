"""Prueba de humo: cada pantalla se renderiza sin errores con distintos filtros.
Ejecutar: python tests/test_vistas.py"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.db import DB
from lib.plan import ERROR_MODELO, calcular
from streamlit.testing.v1 import AppTest

SCRIPT = str(ROOT / "tests" / "_pagina.py")
CASOS = [{}, {"marcas": ["MONTBLANC"]}, {"marcas": ["CREED", "DIOR"], "desde": "2026-01-01"},
         {"generos": ["DAMA"], "desde": "2025-05-01", "hasta": "2025-05-31"}, {"marcas": ["XERJOFF"], "tamanos": [100.0]}]
fallos = 0
for f in CASOS:
    for v in ["resumen", "ventas", "compras", "rentabilidad", "estadistica", "plan", "metodologia"]:
        at = AppTest.from_file(SCRIPT, default_timeout=90)
        at.session_state["cfg"] = {"vista": v, "filtros": f}
        at.run()
        estado = "ok" if not at.exception else "ERROR: " + at.exception[0].value[:300]
        fallos += bool(at.exception)
        print(f"{v:13s} {str(f):70s} {estado}")

marcas, mensual, _ = calcular(str(DB))
control_plan = {
    "Venta proyectada 2027": (int(marcas["proy_2027"].sum()), 2333),
    "Rango mínimo 2027": (
        round(marcas["proy_2027"].sum() * (1 - ERROR_MODELO)),
        1890,
    ),
    "Rango máximo 2027": (
        round(marcas["proy_2027"].sum() * (1 + ERROR_MODELO)),
        2776,
    ),
    "Stock dic-2026": (int(marcas["stock_dic_2026"].sum()), 1190),
    "Compras 2027": (int(marcas["compra_2027"].sum()), 1321),
    "Llegada en diciembre": (
        int(mensual.loc[mensual["mes"] == 12, "compra_llegada"].sum()),
        638,
    ),
}
compras_marca = marcas.set_index("grupo")["compra_2027"]
control_plan.update({
    "Creed": (int(compras_marca["CREED"]), 121),
    "Montblanc": (int(compras_marca["MONTBLANC"]), 23),
    "Bond No. 9": (int(compras_marca["BOND NO. 9"]), 183),
})
for nombre, (actual, esperado) in control_plan.items():
    correcto = actual == esperado
    fallos += not correcto
    estado = "ok" if correcto else f"ERROR: esperado {esperado}, recibido {actual}"
    print(f"plan {nombre:30s} {estado}")

print("FALLOS:", fallos)
