# Script auxiliar de pruebas: renderiza una vista con filtros dados (lo usa tests/test_vistas.py)
import sys, json, importlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st
from lib.db import Filtros
from lib import ui
ui.estilos()
cfg = st.session_state.get("cfg", {"vista": "ventas", "filtros": {}})
st.session_state["filtros"] = Filtros(**cfg["filtros"])
importlib.import_module(f"vistas.{cfg['vista']}").render()
