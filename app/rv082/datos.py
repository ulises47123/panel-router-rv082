"""Carpeta de datos compartida por todas las versiones del panel (32 bits, 64 bits y
código fuente): %LOCALAPPDATA%\\PanelRouter

Ahí van config.json (router), vpn.json (contraseña de SoftEther), respaldos/,
descargas/ y el perfil de la ventana. Antes se guardaban junto a cada .exe, y al
cambiar de versión se "perdía" la contraseña de SoftEther.
"""
from __future__ import annotations

import os
import shutil
import sys

CARPETA_DATOS = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "PanelRouter")


def _carpeta_programa() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ruta(*partes: str) -> str:
    return os.path.join(CARPETA_DATOS, *partes)


def migrar() -> None:
    """Copia (sin pisar) lo que hubiera junto al programa de versiones anteriores."""
    os.makedirs(CARPETA_DATOS, exist_ok=True)
    origen = _carpeta_programa()
    for nombre in ("config.json", "vpn.json"):
        a, b = os.path.join(origen, nombre), ruta(nombre)
        if os.path.isfile(a) and not os.path.exists(b):
            shutil.copy2(a, b)
    for carpeta in ("respaldos", "descargas"):
        a = os.path.join(origen, carpeta)
        if os.path.isdir(a):
            for archivo in os.listdir(a):
                src, dst = os.path.join(a, archivo), ruta(carpeta, archivo)
                if os.path.isfile(src) and not os.path.exists(dst) and ".parcial" not in archivo:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)


migrar()
