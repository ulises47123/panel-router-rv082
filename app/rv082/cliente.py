"""Cliente HTTP de bajo nivel para el router Cisco/Linksys RV082.

Lee las páginas .htm de administración y reproduce exactamente lo que el
navegador enviaría al pulsar "Save Settings": toma TODOS los campos del
formulario con su valor actual, cambia solo los indicados y hace el POST.
Solo usa la librería estándar de Python.
"""
from __future__ import annotations

import base64
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

CODIFICACION = "iso-8859-1"  # las páginas declaran charset iso-8859-1


class ErrorRouter(Exception):
    """Error al hablar con el router (con mensaje en español)."""


# ----------------------------------------------------------------------------
# Parser de formularios
# ----------------------------------------------------------------------------
class _ParserFormularios(HTMLParser):
    """Recorre el HTML y arma la lista de controles de cada <form>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.formularios: dict[str, dict] = {}
        self._form = None
        self._select = None
        self._option = None
        self._textarea = None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        if tag == "form":
            nombre = a.get("name") or f"form{len(self.formularios)}"
            self._form = {"nombre": nombre, "action": a.get("action", ""),
                          "method": (a.get("method") or "get").lower(), "controles": []}
            self.formularios[nombre] = self._form
            return
        if self._form is None:
            return
        if tag == "input":
            tipo = (a.get("type") or "text").lower()
            if "name" not in a:
                return
            self._form["controles"].append({
                "tag": "input", "tipo": tipo, "name": a["name"], "value": a.get("value", "on" if tipo in ("checkbox", "radio") else ""),
                "checked": "checked" in a, "disabled": "disabled" in a})
        elif tag == "select" and "name" in a:
            self._select = {"tag": "select", "tipo": "select-multiple" if "multiple" in a else "select-one",
                            "name": a["name"], "opciones": [], "disabled": "disabled" in a}
            self._form["controles"].append(self._select)
        elif tag == "option" and self._select is not None:
            self._option = {"value": a.get("value"), "texto": "", "selected": "selected" in a}
            self._select["opciones"].append(self._option)
        elif tag == "textarea" and "name" in a:
            self._textarea = {"tag": "textarea", "tipo": "textarea", "name": a["name"], "value": "", "disabled": "disabled" in a}
            self._form["controles"].append(self._textarea)

    def handle_data(self, data):
        if self._option is not None:
            self._option["texto"] += data
        if self._textarea is not None:
            self._textarea["value"] += data

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None
        elif tag == "select":
            self._select = None
            self._option = None
        elif tag == "option":
            self._option = None
        elif tag == "textarea":
            self._textarea = None


class Formulario:
    """Formulario HTML con la misma semántica de envío que un navegador."""

    def __init__(self, datos: dict, pagina: str):
        self.nombre = datos["nombre"]
        self.action = datos["action"] or pagina
        self.method = datos["method"]
        self.controles = datos["controles"]
        self.pagina = pagina
        for c in self.controles:
            if c["tag"] == "select":
                for o in c["opciones"]:
                    if o["value"] is None:
                        o["value"] = o["texto"].strip()
                    o["texto"] = o["texto"].strip()

    # --- lectura -----------------------------------------------------------
    def valor(self, nombre: str, por_defecto=None):
        """Valor que enviaría el navegador para ese nombre (el primero)."""
        for n, v in self.serializar():
            if n == nombre:
                return v
        return por_defecto

    def valores(self, nombre: str) -> list[str]:
        return [v for n, v in self.serializar() if n == nombre]

    def tiene(self, nombre: str) -> bool:
        return any(c["name"] == nombre for c in self.controles)

    def opciones(self, nombre: str) -> list[tuple[str, str]]:
        for c in self.controles:
            if c["name"] == nombre and c["tag"] == "select":
                return [(o["value"], o["texto"]) for o in c["opciones"]]
        return []

    def como_dict(self) -> dict:
        d: dict = {}
        for n, v in self.serializar():
            d.setdefault(n, v)
        return d

    # --- escritura ---------------------------------------------------------
    def poner(self, nombre: str, valor) -> None:
        """Cambia un control. Para radios elige el value; para checkbox usa bool."""
        encontrados = [c for c in self.controles if c["name"] == nombre]
        if not encontrados:
            # campo que el JS crearía: se agrega como hidden
            self.controles.append({"tag": "input", "tipo": "hidden", "name": nombre,
                                   "value": str(valor), "checked": False, "disabled": False})
            return
        c0 = encontrados[0]
        if c0["tag"] == "input" and c0["tipo"] == "radio":
            for c in encontrados:
                c["checked"] = (str(c["value"]) == str(valor))
            if not any(c["checked"] for c in encontrados):
                raise ErrorRouter(f"Valor '{valor}' no válido para la opción {nombre}")
        elif c0["tag"] == "input" and c0["tipo"] == "checkbox":
            for c in encontrados:
                c["checked"] = bool(valor)
        elif c0["tag"] == "select":
            if c0["tipo"] == "select-multiple":
                vals = {str(x) for x in (valor if isinstance(valor, (list, tuple)) else [valor])}
                for o in c0["opciones"]:
                    o["selected"] = o["value"] in vals
            else:
                if not any(o["value"] == str(valor) for o in c0["opciones"]):
                    # el JS a veces carga opciones dinámicas: agregamos la opción
                    c0["opciones"].append({"value": str(valor), "texto": str(valor), "selected": False})
                for o in c0["opciones"]:
                    o["selected"] = (o["value"] == str(valor))
        else:
            # input de texto/hidden: si hay varios con el mismo nombre, se cambian todos
            for c in encontrados:
                c["value"] = str(valor)
                c["disabled"] = False

    def habilitar(self, nombre: str, habilitado: bool = True) -> None:
        for c in self.controles:
            if c["name"] == nombre:
                c["disabled"] = not habilitado

    def quitar(self, nombre: str) -> None:
        self.controles = [c for c in self.controles if c["name"] != nombre]

    def serializar(self) -> list[tuple[str, str]]:
        """Pares (nombre, valor) en el orden del documento, como un navegador."""
        pares = []
        for c in self.controles:
            if c.get("disabled"):
                continue
            if c["tag"] == "input":
                t = c["tipo"]
                if t in ("button", "submit", "reset", "image", "file"):
                    continue
                if t in ("checkbox", "radio") and not c["checked"]:
                    continue
                pares.append((c["name"], c["value"]))
            elif c["tag"] == "select":
                sel = [o for o in c["opciones"] if o["selected"]]
                if c["tipo"] == "select-one" and not sel and c["opciones"]:
                    sel = [c["opciones"][0]]
                for o in sel:
                    pares.append((c["name"], o["value"]))
            elif c["tag"] == "textarea":
                pares.append((c["name"], c["value"]))
        return pares


# ----------------------------------------------------------------------------
# Cliente
# ----------------------------------------------------------------------------
class ClienteRV082:
    def __init__(self, ip: str = "192.168.1.1", usuario: str = "admin", clave: str = "admin",
                 tiempo_espera: float = 15.0, carpeta_respaldos: str | None = None):
        self.ip = ip
        self.usuario = usuario
        self.clave = clave
        self.tiempo_espera = tiempo_espera
        self.carpeta_respaldos = carpeta_respaldos
        self.ultimo_html: dict[str, str] = {}

    @property
    def base(self) -> str:
        return f"http://{self.ip}/"

    def _cabeceras(self) -> dict:
        token = base64.b64encode(f"{self.usuario}:{self.clave}".encode(CODIFICACION)).decode()
        return {"Authorization": f"Basic {token}", "User-Agent": "Mozilla/5.0 (Panel RV082)",
                "Referer": self.base}

    def _pedir(self, ruta: str, datos: list[tuple[str, str]] | None = None, binario=False):
        url = urllib.parse.urljoin(self.base, ruta.lstrip("/"))
        cuerpo = None
        cab = self._cabeceras()
        if datos is not None:
            cuerpo = urllib.parse.urlencode(datos, encoding=CODIFICACION).encode("ascii")
            cab["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=cuerpo, headers=cab, method="POST" if datos is not None else "GET")
        try:
            with urllib.request.urlopen(req, timeout=self.tiempo_espera) as r:
                contenido = r.read()
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ErrorRouter("Usuario o contraseña del router incorrectos") from e
            raise ErrorRouter(f"El router respondió con error {e.code} en {ruta}") from e
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
            raise ErrorRouter(f"No se pudo conectar con el router en {self.ip} ({getattr(e, 'reason', e)})") from e
        return contenido if binario else contenido.decode(CODIFICACION, errors="replace")

    # --- API pública -------------------------------------------------------
    def probar(self) -> bool:
        self._pedir("home.htm")
        return True

    def html(self, pagina: str) -> str:
        texto = self._pedir(pagina)
        self.ultimo_html[pagina] = texto
        return texto

    def formulario(self, pagina: str, nombre: str | None = None, html: str | None = None) -> Formulario:
        texto = html if html is not None else self.html(pagina)
        # el router comenta (<!-- -->) los bloques que no aplican y dentro repite
        # nombres de campos: el navegador los ignora, así que hay que quitarlos.
        texto = re.sub(r"<!--.*?-->", "", texto, flags=re.S)
        p = _ParserFormularios()
        p.feed(texto)
        forms = p.formularios
        if nombre is None:
            # el formulario principal es el que no es "formdualwan"
            candidatos = [f for f in forms if f != "formdualwan"]
            if not candidatos:
                raise ErrorRouter(f"No se encontró formulario en {pagina}")
            nombre = candidatos[-1]
        if nombre not in forms:
            raise ErrorRouter(f"No se encontró el formulario {nombre} en {pagina}")
        return Formulario(forms[nombre], pagina)

    def enviar(self, form: Formulario, extra: list[tuple[str, str]] | None = None, respaldo=True) -> str:
        """Hace el POST del formulario (con respaldo previo de la página)."""
        if respaldo:
            self._respaldar(form.pagina)
        pares = form.serializar() + (extra or [])
        destino = form.action or form.pagina
        respuesta = self._pedir(destino, pares)
        # el firmware suele tardar en aplicar cambios
        time.sleep(0.5)
        return respuesta

    def post(self, pagina: str, pares: list[tuple[str, str]], respaldo=True) -> str:
        if respaldo:
            self._respaldar(pagina)
        return self._pedir(pagina, pares)

    def descargar(self, ruta: str) -> bytes:
        return self._pedir(ruta, binario=True)

    def _respaldar(self, pagina: str) -> None:
        """Guarda los valores actuales de la página antes de modificarla."""
        if not self.carpeta_respaldos:
            return
        try:
            os.makedirs(self.carpeta_respaldos, exist_ok=True)
            f = self.formulario(pagina)
            nombre = time.strftime("%Y%m%d-%H%M%S") + "_" + re.sub(r"\W", "_", pagina) + ".json"
            with open(os.path.join(self.carpeta_respaldos, nombre), "w", encoding="utf-8") as fh:
                json.dump({"pagina": pagina, "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
                           "campos": f.serializar()}, fh, ensure_ascii=False, indent=1)
        except ErrorRouter:
            pass


# ----------------------------------------------------------------------------
# Utilidades para leer variables JS embebidas en las páginas
# ----------------------------------------------------------------------------
def variable_js(html: str, nombre: str, por_defecto=None):
    m = re.search(r"\bvar\s+" + re.escape(nombre) + r"\s*=\s*(['\"])(.*?)\1", html, re.S)
    if m:
        return m.group(2)
    m = re.search(r"\b" + re.escape(nombre) + r"\s*=\s*([-\d.]+)\s*;", html)
    if m:
        return m.group(1)
    return por_defecto


def texto_plano(html: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()
