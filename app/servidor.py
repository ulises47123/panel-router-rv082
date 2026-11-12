"""Panel RV082 — servidor local (intermediario entre el usuario y el router).

Sirve la interfaz web en http://127.0.0.1:8095 y expone una API JSON que
traduce cada acción a los formularios del router. Solo librería estándar.
"""
from __future__ import annotations

import json
import re
import os
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
RECURSOS = getattr(sys, "_MEIPASS", BASE)
sys.path.insert(0, RECURSOS)

from rv082.cliente import ClienteRV082, ErrorRouter  # noqa: E402
from rv082 import funciones  # noqa: E402
from rv082 import vpn  # noqa: E402

PUERTO = 8095
CARPETA_WEB = os.path.join(RECURSOS, "web")
ARCHIVO_CONFIG = os.path.join(BASE, "config.json")
CARPETA_RESPALDOS = os.path.join(BASE, "respaldos")

TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}

_bloqueo = threading.Lock()  # el router es lento: una operación a la vez
_ultimo_latido = [0.0]  # la ventana avisa cada 20 s que sigue abierta


def leer_config() -> dict:
    cfg = {"ip": "192.168.1.1", "usuario": "admin", "clave": "admin"}
    try:
        with open(ARCHIVO_CONFIG, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def guardar_config(cfg: dict) -> None:
    with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)


def cliente() -> ClienteRV082:
    c = leer_config()
    return ClienteRV082(c["ip"], c["usuario"], c["clave"], carpeta_respaldos=CARPETA_RESPALDOS)


class Manejador(BaseHTTPRequestHandler):
    server_version = "PanelRV082/1.0"

    def log_message(self, fmt, *args):  # silencioso
        pass

    def _json(self, codigo: int, datos) -> None:
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _estatico(self, ruta: str) -> None:
        if ruta in ("", "/"):
            ruta = "/index.html"
        archivo = os.path.normpath(os.path.join(CARPETA_WEB, ruta.lstrip("/")))
        if not archivo.startswith(CARPETA_WEB) or not os.path.isfile(archivo):
            self.send_error(404)
            return
        with open(archivo, "rb") as f:
            cuerpo = f.read()
        self.send_response(200)
        self.send_header("Content-Type", TIPOS.get(os.path.splitext(archivo)[1], "application/octet-stream"))
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _origen_valido(self) -> bool:
        # protección básica contra sitios externos que intenten usar la API
        origen = self.headers.get("Origin") or self.headers.get("Referer") or ""
        return origen == "" or origen.startswith((f"http://127.0.0.1:{PUERTO}", f"http://localhost:{PUERTO}"))

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/api/"):
            self._api(u.path[5:], {k: v[0] for k, v in parse_qs(u.query).items()}, metodo="GET")
        else:
            self._estatico(u.path)

    def do_POST(self):
        u = urlparse(self.path)
        if not u.path.startswith("/api/") or not self._origen_valido():
            self.send_error(403)
            return
        largo = int(self.headers.get("Content-Length") or 0)
        try:
            datos = json.loads(self.rfile.read(largo) or b"{}")
        except ValueError:
            self._json(400, {"ok": False, "error": "Datos inválidos"})
            return
        self._api(u.path[5:], datos, metodo="POST")

    def _api(self, accion: str, datos: dict, metodo: str) -> None:
        import time as _t
        _ultimo_latido[0] = _t.time()
        if accion == "latido":
            self._json(200, {"ok": True, "datos": {}})
            return
        if accion == "mostrar":  # otra instancia pidió mostrar la ventana
            threading.Thread(target=abrir_ventana, daemon=True).start()
            self._json(200, {"ok": True, "datos": {}})
            return
        if accion == "salir" and metodo == "POST":  # botón "Cerrar panel" de la interfaz
            self._json(200, {"ok": True, "datos": {"mensaje": "Cerrando"}})
            threading.Timer(0.5, cerrar_todo).start()
            return
        try:
            if accion == "config" and metodo == "GET":
                c = leer_config()
                self._json(200, {"ok": True, "datos": {"ip": c["ip"], "usuario": c["usuario"]}})
                return
            if accion == "config" and metodo == "POST":
                c = leer_config()
                for k in ("ip", "usuario", "clave"):
                    if datos.get(k):
                        c[k] = str(datos[k]).strip()
                prueba = ClienteRV082(c["ip"], c["usuario"], c["clave"])
                prueba.probar()
                guardar_config(c)
                self._json(200, {"ok": True})
                return
            if accion == "respaldo":
                with _bloqueo:
                    contenido, nombre = funciones.descargar_respaldo(cliente())
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{nombre}"')
                self.send_header("Content-Length", str(len(contenido)))
                self.end_headers()
                self.wfile.write(contenido)
                return
            if accion == "vpn/script":  # archivo .bat para la PC de afuera
                est = vpn.estado_vpn()
                if not est.get("direccion"):
                    self._json(200, {"ok": False, "error": "La VPN todavía no tiene dirección (configurala primero)"})
                    return
                cuerpo = vpn.script_cliente(est["direccion"], datos.get("usuario", "")).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", 'attachment; filename="Conectar-VPN-Oficina.bat"')
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
                return
            fn_vpn = vpn.ACCIONES.get((metodo, accion))
            if fn_vpn is not None:  # la VPN no usa el router: no espera el bloqueo
                self._json(200, {"ok": True, "datos": fn_vpn(None, datos)})
                return
            fn = funciones.ACCIONES.get((metodo, accion))
            if fn is None:
                self._json(404, {"ok": False, "error": f"Acción desconocida: {accion}"})
                return
            with _bloqueo:
                resultado = fn(cliente(), datos)
                if accion == "clave":  # el router ya usa la clave nueva: actualizarla aquí
                    c = leer_config()
                    c["clave"] = resultado.pop("clave")
                    c["usuario"] = resultado.pop("usuario") or c["usuario"]
                    guardar_config(c)
                if accion == "fabrica":  # el router vuelve a sus valores de fábrica
                    c = leer_config(); c.update(ip="192.168.1.1", usuario="admin", clave="admin"); guardar_config(c)
                if accion == "lan" and resultado.get("nueva_ip"):
                    c = leer_config(); c["ip"] = resultado["nueva_ip"]; guardar_config(c)
            self._json(200, {"ok": True, "datos": resultado})
        except ErrorRouter as e:
            self._json(200, {"ok": False, "error": str(e)})
        except funciones.ErrorValidacion as e:
            self._json(200, {"ok": False, "error": str(e)})
        except vpn.ErrorVPN as e:
            self._json(200, {"ok": False, "error": str(e)})
        except Exception as e:  # error inesperado: se registra
            traceback.print_exc()
            self._json(500, {"ok": False, "error": f"Error interno: {e}"})


CARPETA_PERFIL = os.path.join(BASE, ".perfil-ventana")  # perfil propio: no toca el navegador del usuario
_estado_app = {"srv": None, "url": "", "bandeja": None, "ventanas": [], "cerrando": False}


CHROMIUM = ("msedge.exe", "chrome.exe", "brave.exe", "vivaldi.exe", "opera.exe", "browser.exe", "chromium.exe")
FIREFOX = ("firefox.exe",)


def _exe_predeterminado() -> str | None:
    """Ejecutable del navegador predeterminado de Windows (el que eligió el usuario)."""
    try:
        import winreg
        clave = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
            progid = winreg.QueryValueEx(k, "ProgId")[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid + r"\shell\open\command") as k:
            comando = winreg.QueryValueEx(k, "")[0]
        m = re.match(r'\s*"([^"]+)"', comando) or re.match(r"\s*(\S+)", comando)
        exe = m.group(1) if m else None
        return exe if exe and os.path.isfile(exe) else None
    except OSError:
        return None


def _exe_app_paths(nombre: str) -> str | None:
    """Ruta registrada en "App Paths" (sirve para instalaciones en carpetas no estándar
    o por usuario). Se miran HKCU y HKLM en las vistas de 64 y 32 bits."""
    try:
        import winreg
    except ImportError:
        return None
    sub = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths" + "\\" + nombre
    for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for vista in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(raiz, sub, 0, winreg.KEY_READ | vista) as k:
                    exe = winreg.QueryValueEx(k, "")[0].strip('"')
                    if os.path.isfile(exe):
                        return exe
            except OSError:
                continue
    return None


def _navegador() -> tuple[str, str] | None:
    """Devuelve (ejecutable, tipo) con tipo "chromium" o "firefox".
    Orden: navegador predeterminado (si es compatible) > Edge > Chrome > Brave >
    Vivaldi > Opera > Yandex > Chromium > Firefox. Busca en las carpetas típicas y en
    el registro (App Paths), así funciona aunque solo esté instalado uno de ellos."""
    pred = _exe_predeterminado()
    if pred:
        nombre = os.path.basename(pred).lower()
        if nombre in CHROMIUM:
            return pred, "chromium"
        if nombre in FIREFOX:
            return pred, "firefox"
    # %ProgramW6432% = "Program Files" real aunque el panel corra como 32 bits en Windows de 64
    raices = [os.environ.get(v) for v in ("ProgramFiles(x86)", "ProgramW6432", "ProgramFiles", "LocalAppData")]
    raices += [os.path.join(os.environ.get("LocalAppData", ""), "Programs")]
    conocidos = [
        ("msedge.exe", r"Microsoft\Edge\Application\msedge.exe", "chromium"),
        ("chrome.exe", r"Google\Chrome\Application\chrome.exe", "chromium"),
        ("brave.exe", r"BraveSoftware\Brave-Browser\Application\brave.exe", "chromium"),
        ("vivaldi.exe", r"Vivaldi\Application\vivaldi.exe", "chromium"),
        ("opera.exe", r"Opera\opera.exe", "chromium"),
        ("browser.exe", r"Yandex\YandexBrowser\Application\browser.exe", "chromium"),
        ("chrome.exe", r"Chromium\Application\chrome.exe", "chromium"),
        ("firefox.exe", r"Mozilla Firefox\firefox.exe", "firefox"),
    ]
    for nombre, relativo, tipo in conocidos:
        for r in raices:
            if r and os.path.isfile(os.path.join(r, relativo)):
                return os.path.join(r, relativo), tipo
        exe = _exe_app_paths(nombre)
        if exe:
            return exe, tipo
    return None


def _tamano_ventana() -> tuple[int, int, int, int]:
    """Tamaño de ventana que entra en la pantalla (deja lugar para la barra de tareas)."""
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)  # SPI_GETWORKAREA
        sw, sh = r.right - r.left, r.bottom - r.top
        ancho, alto = min(1200, sw - 40), min(820, sh - 30)
        return ancho, alto, r.left + (sw - ancho) // 2, r.top + (sh - alto) // 2
    except Exception:  # noqa: BLE001
        return 1100, 680, 40, 20


def abrir_ventana(url: str | None = None) -> None:
    """Abre la interfaz en una ventana propia con un perfil separado del navegador del
    usuario, así "Cerrar todo" puede cerrarla sin tocar sus pestañas.
    - Chromium (Chrome, Edge, Brave...): modo aplicación (--app), sin barra de direcciones.
    - Firefox: instancia aparte con perfil propio (-no-remote -profile)."""
    import subprocess
    url = url or _estado_app["url"]
    nav = _navegador()
    if not nav:
        webbrowser.open(url)  # último recurso: el navegador que haya (no se podrá cerrar solo)
        return
    exe, tipo = nav
    ancho, alto, x, y = _tamano_ventana()
    if tipo == "chromium":
        args = [exe, f"--app={url}", f"--window-size={ancho},{alto}", f"--window-position={x},{y}",
                f"--user-data-dir={CARPETA_PERFIL}", "--no-first-run", "--no-default-browser-check",
                "--disable-features=Translate"]
    else:
        perfil = CARPETA_PERFIL + "-firefox"
        os.makedirs(perfil, exist_ok=True)
        args = [exe, "-no-remote", "-profile", perfil, "-width", str(ancho), "-height", str(alto), "-new-window", url]
    p = subprocess.Popen(args)
    _estado_app["ventanas"].append(p.pid)


def _cerrar_ventanas() -> None:
    """Cierra solo las ventanas del panel: cualquier proceso (de cualquier navegador)
    que use la carpeta de perfil propia del panel."""
    import subprocess
    sin_ventana = 0x08000000
    for pid in _estado_app["ventanas"]:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=sin_ventana)
    marca = CARPETA_PERFIL.replace("'", "''")
    cmd = ("Get-CimInstance Win32_Process | "
           f"Where-Object {{ $_.CommandLine -like '*{marca}*' -and $_.ProcessId -ne $PID }} | "
           "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True,
                   creationflags=sin_ventana, env=env, timeout=30)


def cerrar_todo() -> None:
    """Cierra la ventana, el ícono de la bandeja y el servidor."""
    if _estado_app["cerrando"]:
        return
    _estado_app["cerrando"] = True
    try:
        _cerrar_ventanas()
    except Exception:  # noqa: BLE001
        pass
    if _estado_app["bandeja"]:
        _estado_app["bandeja"].cerrar()
    if _estado_app["srv"]:
        _estado_app["srv"].shutdown()


def _vigilar_ventana(srv) -> None:
    """Si la ventana lleva 10 minutos cerrada (sin latidos), el programa se cierra solo."""
    import time as _t
    _ultimo_latido[0] = _t.time()
    while not _estado_app["cerrando"]:
        _t.sleep(15)
        if _t.time() - _ultimo_latido[0] > 600:
            cerrar_todo()
            return


def main():
    global PUERTO
    sin_ventana = "--sin-ventana" in sys.argv
    for a in sys.argv[1:]:  # --puerto=8097 (para usar otro puerto)
        if a.startswith("--puerto="):
            PUERTO = int(a.split("=", 1)[1])
    url = f"http://127.0.0.1:{PUERTO}/"
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    except OSError:
        # ya hay un panel abierto: pedirle que muestre su ventana
        if not sin_ventana:
            import urllib.request
            try:
                urllib.request.urlopen(url + "api/mostrar", timeout=5).read()
            except OSError:
                abrir_ventana(url)
        return
    _estado_app.update(srv=srv, url=url)
    print(f"Panel RV082 funcionando en {url}  (Ctrl+C para cerrar)")
    if not sin_ventana:
        try:
            from rv082.bandeja import Bandeja
            icono = os.path.join(RECURSOS, "recursos", "logo.ico")
            b = Bandeja("Panel del Router", icono if os.path.isfile(icono) else None, abrir_ventana, cerrar_todo,
                        aviso="El panel está abierto. Para cerrarlo: clic derecho en este ícono → Cerrar todo.")
            b.iniciar()
            _estado_app["bandeja"] = b
        except Exception:  # noqa: BLE001 — sin bandeja el panel igual funciona
            traceback.print_exc()
        threading.Timer(0.6, abrir_ventana, args=(url,)).start()
        threading.Thread(target=_vigilar_ventana, args=(srv,), daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if _estado_app["bandeja"]:
            _estado_app["bandeja"].cerrar()


if __name__ == "__main__":
    main()
