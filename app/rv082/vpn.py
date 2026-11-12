"""VPN de acceso remoto: SoftEther VPN Server + VPN Azure + cliente SSTP de Windows.

El panel descarga el instalador oficial (verificando la firma digital), lo abre,
y después configura todo con vpncmd (la herramienta de comandos de SoftEther):
contraseña de administración, VPN Azure, SSTP, puente al router y usuarios.
Se usa el Hub "DEFAULT" para que el usuario de Windows sea solo el nombre (sin @hub).
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import secrets
import string
import subprocess
import sys
import threading
import time
import urllib.request

VERSION = "v4.44-9807-rtm-2025.04.16"
# El instalador "x86_x64" sirve para Windows de 32 y de 64 bits.
# Fuentes en orden: sitio oficial (v4.44) y, si falla o está lento, GitHub (v4.41).
# Las dos están firmadas por SoftEther: se verifica la firma antes de usarlas.
FUENTES = [
    ("https://www.softether-download.com/files/softether/" + VERSION +
     "-tree/Windows/SoftEther_VPN_Server_and_VPN_Bridge/softether-vpnserver_vpnbridge-" +
     VERSION + "-windows-x86_x64-intel.exe"),
    ("https://github.com/SoftEtherVPN/SoftEtherVPN_Stable/releases/download/v4.41-9787-rtm/"
     "softether-vpnserver_vpnbridge-v4.41-9787-rtm-2023.03.14-windows-x86_x64-intel.exe"),
]
URL_INSTALADOR = FUENTES[0]
NOMBRE_INSTALADOR = "instalador-softether-vpnserver.exe"
HUB = "DEFAULT"
SERVICIO = "SEVPNSERVER"


def _carpetas_programas() -> list[str]:
    """Carpetas posibles de SoftEther. Si el panel corre como 32 bits en un Windows
    de 64, %ProgramFiles% apunta a "Program Files (x86)": por eso se mira también
    %ProgramW6432% (el "Program Files" real)."""
    vistas = []
    for var in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if base:
            ruta = os.path.join(base, "SoftEther VPN Server")
            if ruta not in vistas:
                vistas.append(ruta)
    return vistas


CARPETAS = _carpetas_programas()
SIN_VENTANA = 0x08000000  # CREATE_NO_WINDOW

# carpeta del programa: junto al .exe, o la carpeta app\ cuando se corre con Python
if getattr(sys, "frozen", False):
    BASE = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from . import datos  # noqa: E402  carpeta común a todas las versiones del panel
ARCHIVO_VPN = datos.ruta("vpn.json")                # contraseña de administración de SoftEther
CARPETA_DESCARGAS = datos.ruta("descargas")

_descarga = {"estado": "nada", "bytes": 0, "total": 0, "error": "", "archivo": ""}


class ErrorVPN(Exception):
    pass


def _err(msg):
    from . import funciones
    return funciones.ErrorValidacion(msg)


# ----------------------------------------------------------------------------
# utilidades del sistema
# ----------------------------------------------------------------------------
def _entorno_limpio() -> dict:
    """Entorno para procesos hijos. Se quita PSModulePath: si en la PC también está
    PowerShell 7, Windows PowerShell hereda su ruta de módulos y no puede cargar
    Microsoft.PowerShell.Security (Get-AuthenticodeSignature)."""
    return {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}


def _ejecutar(args, timeout=40, entrada=None) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=SIN_VENTANA, env=_entorno_limpio(),
                           input=(entrada or "").encode() if entrada is not None else None,
                           stdin=None if entrada is not None else subprocess.DEVNULL)
    except FileNotFoundError:
        raise ErrorVPN(f"No se encontró {args[0]}")
    except subprocess.TimeoutExpired as e:
        err = ErrorVPN("El comando tardó demasiado")
        err.salida = ((e.stdout or b"") + (e.stderr or b"")).decode("utf-8", "replace")
        raise err
    salida = (p.stdout or b"") + (p.stderr or b"")
    for cod in ("utf-8", "cp850", "latin-1"):
        try:
            return p.returncode, salida.decode(cod)
        except UnicodeDecodeError:
            continue
    return p.returncode, salida.decode("latin-1", "replace")


def _powershell(cmd: str, timeout=40) -> str:
    _, out = _ejecutar(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], timeout=timeout)
    return out.strip()


def _leer_cfg() -> dict:
    try:
        with open(ARCHIVO_VPN, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _guardar_cfg(cfg: dict) -> None:
    with open(ARCHIVO_VPN, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)


def _clave_aleatoria(n=20) -> str:
    abc = string.ascii_letters + string.digits
    return "".join(secrets.choice(abc) for _ in range(n))


def _vpncmd_ruta() -> str | None:
    for c in CARPETAS:
        for exe in ("vpncmd_x64.exe", "vpncmd.exe"):
            r = os.path.join(c, exe)
            if os.path.isfile(r):
                return r
    return None


def _servicio() -> str:
    """'corriendo' | 'detenido' | 'no_instalado'"""
    _, out = _ejecutar(["sc", "query", SERVICIO], timeout=15)
    if "RUNNING" in out:
        return "corriendo"
    if "STATE" in out or "ESTADO" in out:
        return "detenido"
    return "no_instalado"


HASH_CLAVE_VACIA = "+WzqGYrR3VYXrAhKPZLGEHcIwO8="  # cómo guarda SoftEther una contraseña vacía
MSJ_YA_TIENE_CLAVE = ("El servidor SoftEther ya tiene una contraseña de administración que el panel no conoce. "
                      "Si no pusiste ninguna, tocá \"Restablecer acceso\" (pide permiso de administrador); "
                      "si sí la pusiste, escribila abajo.")
_desinstalando = {"activo": False}  # solo se archiva vpn.json cuando el usuario pidió desinstalar


def _instalador_abierto() -> bool:
    """¿Sigue abierto el instalador/desinstalador de SoftEther? (no hay que configurar mientras tanto:
    el instalador arranca el servicio a mitad de camino y después lo reinicia)."""
    out = _powershell("Get-Process | Where-Object { $_.Name -match '^(vpnsetup|instalador-softether)' } | "
                      "Measure-Object | ForEach-Object { $_.Count }", timeout=20)
    return out.strip() not in ("", "0")


def _archivar_cfg() -> None:
    """Nunca se borra la contraseña guardada: se renombra con la fecha."""
    if os.path.exists(ARCHIVO_VPN):
        destino = datos.ruta(time.strftime("vpn-anterior-%Y%m%d-%H%M%S.json"))
        try:
            os.replace(ARCHIVO_VPN, destino)
        except OSError:
            pass


class ErrorPideClave(ErrorVPN):
    """vpncmd se quedó pidiendo 'Password:' (la contraseña falta o es incorrecta)."""


def _servidor_tiene_clave() -> bool | None:
    """Mira en vpn_server.config si el servidor tiene contraseña de administración.
    None si no se pudo leer el archivo."""
    for carpeta in CARPETAS:
        ruta = os.path.join(carpeta, "vpn_server.config")
        try:
            with open(ruta, encoding="utf-8", errors="replace") as f:
                texto = f.read()
        except OSError:
            continue
        bloque = texto.split("declare ServerConfiguration", 1)[-1]
        m = re.search(r"byte HashedPassword (\S+)", bloque)
        if m:
            return m.group(1) != HASH_CLAVE_VACIA
    return None


# Puertos para administrar SoftEther. El 5555 va último: adb (Android) sondea
# 127.0.0.1:5555 buscando emuladores y SoftEther lo toma como ataque DoS,
# bloqueando TODAS las conexiones locales (incluido este panel).
PUERTOS_ADMIN = ["443", "992", "5555"]
_puerto_ok = {"p": None}
_candado_vpncmd = threading.Lock()   # una conexión a la vez (evita ráfagas que disparan el anti-DoS)
_ultima_conexion = {"t": 0.0}


def _vpncmd(*comando: str, clave: str | None = None, hub: bool = False, csv_: bool = True, timeout=25) -> str:
    exe = _vpncmd_ruta()
    if not exe:
        raise ErrorVPN("SoftEther VPN Server no está instalado")
    if clave is None:
        clave = _leer_cfg().get("clave", "")
    puertos = ([_puerto_ok["p"]] if _puerto_ok["p"] else []) + [p for p in PUERTOS_ADMIN if p != _puerto_ok["p"]]
    ultimo_error = None
    with _candado_vpncmd:
        for puerto in puertos:
            espera = 0.35 - (time.time() - _ultima_conexion["t"])
            if espera > 0:
                time.sleep(espera)
            try:
                out = _vpncmd_puerto(exe, puerto, comando, clave, hub, csv_, timeout)
                _puerto_ok["p"] = puerto
                return out
            except _ErrorConexion as e:   # ese puerto no responde: probar el siguiente
                ultimo_error = e
            finally:
                _ultima_conexion["t"] = time.time()
    raise ErrorVPN("No se pudo conectar con SoftEther (puertos 443, 992 y 5555). "
                   "Si en esta PC se usa adb o un emulador de Android, esperá un minuto y volvé a intentar. "
                   f"({ultimo_error})")


class _ErrorConexion(ErrorVPN):
    pass


def _vpncmd_puerto(exe, puerto, comando, clave, hub, csv_, timeout) -> str:
    args = [exe, f"localhost:{puerto}", "/SERVER", f"/PASSWORD:{clave}"]
    if hub:
        # /ADMINHUB = administrar el Hub con la contraseña del SERVIDOR.
        # (/HUB: entraría como administrador del Hub y pediría la contraseña del Hub)
        args.append(f"/ADMINHUB:{HUB}")
    if csv_:
        args.append("/CSV")
    args += ["/CMD"] + list(comando)
    try:
        cod, out = _ejecutar(args, timeout=timeout)
    except ErrorVPN as e:
        if "Password:" in getattr(e, "salida", ""):
            raise ErrorPideClave("SoftEther pide una contraseña de administración distinta")
        raise
    if cod != 0:
        linea = next((l for l in out.splitlines() if "Error" in l or "error" in l), out.strip()[-200:])
        if "Access has been denied" in out or "password" in out.lower() and "incorrect" in out.lower():
            raise ErrorVPN("La contraseña de administración de SoftEther no coincide (archivo vpn.json)")
        # Error code 1 = puerto cerrado: se prueba el siguiente.
        # Error code 2 = SoftEther cortó la conexión (anti-DoS): reintentar en otro puerto lo empeora.
        if re.search(r"Error code: 1\)", out):
            raise _ErrorConexion(linea.strip())
        if re.search(r"Error code: 2\)", out):
            raise ErrorVPN("SoftEther está rechazando conexiones de esta PC por su protección anti-ataques "
                           "(suele pasar si se usa adb o un emulador de Android). Esperá 2 minutos y tocá Actualizar.")
        raise ErrorVPN(f"SoftEther respondió con error: {linea.strip()}")
    return out


def _csv(out: str) -> list[list[str]]:
    filas = list(csv.reader(io.StringIO(out)))
    return [f for f in filas if f and any(c.strip() for c in f)]


def _campo(d: dict, *claves: str) -> str:
    """Valor del primer campo cuyo nombre contiene todas las palabras clave (sin mayúsculas)."""
    for k, v in d.items():
        if all(c.lower() in k.lower() for c in claves):
            return v
    return ""


def _pares(out: str) -> dict:
    """Salida CSV de comandos 'Get' (Item,Value) -> dict."""
    d = {}
    for f in _csv(out):
        if len(f) >= 2 and f[0] not in ("Item",):
            d[f[0].strip()] = f[1].strip()
    return d


# ----------------------------------------------------------------------------
# descarga e instalación
# ----------------------------------------------------------------------------
class _Lenta(Exception):
    pass


def _bajar(url: str, temporal: str, minimo_kbs: int = 0) -> None:
    """Descarga con reanudación (Range). Si la conexión se corta o se queda quieta
    30 s, reintenta desde donde quedó (hasta 4 veces). Con minimo_kbs, si a los
    15 s la velocidad promedio es menor, abandona para probar otra fuente."""
    ultimo = None
    for intento in range(4):
        hecho = os.path.getsize(temporal) if os.path.exists(temporal) else 0
        cab = {"User-Agent": "Mozilla/5.0"}
        if hecho:
            cab["Range"] = f"bytes={hecho}-"
        try:
            req = urllib.request.Request(url, headers=cab)
            with urllib.request.urlopen(req, timeout=30) as r:
                if hecho and r.status != 206:      # el servidor no reanuda: empezar de cero
                    hecho = 0
                largo = int(r.headers.get("Content-Length") or 0)
                _descarga["total"] = hecho + largo if largo else 0
                _descarga["bytes"] = hecho
                inicio, base = time.time(), _descarga["bytes"]
                with open(temporal, "ab" if hecho else "wb") as f:
                    while True:
                        bloque = r.read(256 * 1024)
                        if not bloque:
                            break
                        f.write(bloque)
                        _descarga["bytes"] += len(bloque)
                        pasado = time.time() - inicio
                        _descarga["kbs"] = int((_descarga["bytes"] - base) / 1024 / max(pasado, 0.1))
                        if minimo_kbs and pasado > 15 and _descarga["kbs"] < minimo_kbs:
                            raise _Lenta(f"muy lenta ({_descarga['kbs']} KB/s)")
            if _descarga["total"] and _descarga["bytes"] < _descarga["total"]:
                raise ErrorVPN("descarga incompleta")
            return
        except _Lenta:
            raise
        except Exception as e:  # noqa: BLE001 — corte de red, timeout, etc.
            ultimo = e
            time.sleep(2 + intento * 2)
    raise ErrorVPN(f"No se pudo descargar ({ultimo})")


def _hilo_descarga():
    os.makedirs(CARPETA_DESCARGAS, exist_ok=True)
    destino = os.path.join(CARPETA_DESCARGAS, NOMBRE_INSTALADOR)
    errores = []
    for n, url in enumerate(FUENTES):
        temporal = destino + f".parcial{n}"
        _descarga.update(estado="descargando", fuente=url.split("/")[2], bytes=0, total=0)
        try:
            # en todas las fuentes menos la última se exige una velocidad mínima
            _bajar(url, temporal, minimo_kbs=150 if n < len(FUENTES) - 1 else 0)
            _descarga["estado"] = "verificando"
            firma = _verificar_firma(temporal)
            if not firma["valida"]:
                os.remove(temporal)
                raise ErrorVPN("la firma digital NO es válida (" + firma["detalle"] + ")")
            if os.path.exists(destino):
                os.remove(destino)
            os.replace(temporal, destino)
            _descarga.update(estado="listo", archivo=destino, firmante=firma["firmante"],
                             version=re.search(r"v4\.\d+-\d+", url).group(0))
            try:  # recordar de qué versión es el archivo descargado
                with open(destino + ".json", "w", encoding="utf-8") as fj:
                    json.dump({"version": _descarga["version"], "fuente": url}, fj)
            except OSError:
                pass
            for k in range(len(FUENTES)):  # borrar parciales de fuentes abandonadas
                try:
                    os.remove(destino + f".parcial{k}")
                except OSError:
                    pass
            return
        except Exception as e:  # noqa: BLE001
            errores.append(f"{url.split('/')[2]}: {e}")
    _descarga.update(estado="error", error="No se pudo obtener el instalador. " + " | ".join(errores))


def _verificar_firma(ruta: str) -> dict:
    cmd = ("$s=Get-AuthenticodeSignature -LiteralPath '" + ruta.replace("'", "''") + "';"
           "\"$($s.Status)|$($s.SignerCertificate.Subject)\"")
    out = _powershell(cmd, timeout=60)
    estado, _, firmante = out.partition("|")
    # firmante esperado: "CN=SOFTETHER CORPORATION, O=SOFTETHER CORPORATION, ..."
    valida = estado.strip() == "Valid" and "O=SOFTETHER CORPORATION" in firmante.upper()
    return {"valida": valida, "firmante": firmante.strip(), "detalle": f"Estado: {estado.strip()} · Firmante: {firmante.strip() or 'ninguno'}"}


def descargar(_cli, _d=None) -> dict:
    if _descarga["estado"] in ("descargando", "verificando"):
        return progreso()
    existente = os.path.join(CARPETA_DESCARGAS, NOMBRE_INSTALADOR)
    if os.path.isfile(existente):
        firma = _verificar_firma(existente)
        if firma["valida"]:
            try:
                with open(existente + ".json", encoding="utf-8") as fj:
                    _descarga["version"] = json.load(fj).get("version", "")
            except (OSError, ValueError):
                _descarga["version"] = ""
            _descarga.update(estado="listo", archivo=existente, firmante=firma["firmante"],
                             bytes=os.path.getsize(existente), total=os.path.getsize(existente))
            return progreso()
    _descarga.update(estado="descargando", bytes=0, total=0, error="", archivo="")
    threading.Thread(target=_hilo_descarga, daemon=True).start()
    return progreso()


def progreso(_cli=None, _d=None) -> dict:
    d = dict(_descarga)
    d["porcentaje"] = int(d["bytes"] * 100 / d["total"]) if d.get("total") else 0
    return d


def instalar(_cli, _d=None) -> dict:
    if _descarga.get("estado") != "listo" or not os.path.isfile(_descarga.get("archivo", "")):
        raise _err("Primero descargá el instalador")
    if not _verificar_firma(_descarga["archivo"])["valida"]:
        raise _err("La firma del instalador no es válida")
    os.startfile(_descarga["archivo"])  # Windows pide permiso de administrador (UAC)
    return {"mensaje": "Se abrió el instalador. Aceptá el permiso de administrador y seguí los pasos."}


# ----------------------------------------------------------------------------
# estado y configuración
# ----------------------------------------------------------------------------
def _adaptador_router() -> dict | None:
    """Placa de red de esta PC que está en la red del router (192.168.1.x por defecto)."""
    cfg_router = {}
    try:
        with open(datos.ruta("config.json"), encoding="utf-8") as f:
            cfg_router = json.load(f)
    except (OSError, ValueError):
        pass
    red = ".".join((cfg_router.get("ip") or "192.168.1.1").split(".")[:3]) + "."
    out = _powershell("Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { $a=Get-NetAdapter -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue; "
                      "if($a){ \"$($_.IPAddress)|$($a.Name)|$($a.InterfaceDescription)|$($a.Status)\" } }")
    for linea in out.splitlines():
        p = linea.split("|")
        if len(p) == 4 and p[0].startswith(red) and p[3] == "Up":
            return {"ip": p[0], "nombre": p[1], "descripcion": p[2]}
    return None


def estado_vpn(_cli=None, _d=None) -> dict:
    if _descarga["estado"] == "nada" and os.path.isfile(os.path.join(CARPETA_DESCARGAS, NOMBRE_INSTALADOR)):
        descargar(None)  # ya estaba bajado: verificar la firma y marcarlo listo
    servicio = _servicio()
    if _desinstalando["activo"] and servicio == "no_instalado" and not _vpncmd_ruta():
        _archivar_cfg()                       # desinstalación pedida por el usuario: terminó
        _desinstalando["activo"] = False
    instalador = _instalador_abierto()
    res = {"version": VERSION, "servicio": servicio, "instalado": bool(_vpncmd_ruta()),
           "configurado": bool(_leer_cfg().get("clave")), "descarga": progreso(),
           "instalador_abierto": instalador}
    if res["instalado"] and servicio == "corriendo" and not res["configurado"]:
        res["tiene_clave"] = bool(_servidor_tiene_clave())
    if res["servicio"] != "corriendo" or not res["configurado"]:
        res["adaptador"] = _adaptador_router()
        return res
    try:
        # nombres reales verificados con SoftEther 4.41 (se buscan por palabras clave)
        az = _pares(_vpncmd("VpnAzureGetStatus"))
        res["azure_activo"] = _campo(az, "azure", "enabled").lower() == "yes"
        res["azure_conectado"] = _campo(az, "established").lower() == "yes"
        res["direccion"] = _campo(az, "hostname")
        dd = _pares(_vpncmd("DynamicDnsGetStatus"))
        res["ip_publica"] = _campo(dd, "ipv4")
        res["nombre_ddns"] = _campo(dd, "hostname (hostname")
        sstp = _pares(_vpncmd("SstpGet"))
        res["sstp"] = _campo(sstp, "sstp", "enabled").lower() == "yes"
        puentes = _csv(_vpncmd("BridgeList"))
        res["puente"] = [{"hub": f[1], "adaptador": f[2], "estado": f[3]} for f in puentes[1:] if len(f) >= 4]
        res["usuarios"] = listar_usuarios()["usuarios"]
    except ErrorVPN as e:
        res["error"] = str(e)
    res["adaptador"] = _adaptador_router()
    return res


def configurar(_cli, d: dict) -> dict:
    """Deja el servidor listo: clave de admin, VPN Azure, SSTP, puente y nombre."""
    if _servicio() != "corriendo":
        raise _err("El servicio de SoftEther no está funcionando. Terminá la instalación primero.")
    if _instalador_abierto():
        raise _err("El instalador de SoftEther sigue abierto. Terminá la instalación (Finalizar) y después configurá.")
    nombre = re.sub(r"[^a-z0-9-]", "", (d.get("nombre") or "").lower())[:30]
    if d.get("nombre") and len(nombre) < 3:
        raise _err("El nombre debe tener al menos 3 letras o números (ej. oficina-perez)")
    cfg = _leer_cfg()
    pasos = []
    if not cfg.get("clave"):
        clave_admin = d.get("clave_admin") or ""
        if clave_admin:
            # el usuario ya le había puesto una contraseña (Server Manager): verificarla
            try:
                _vpncmd("ServerInfoGet", clave=clave_admin, timeout=8)
            except ErrorPideClave:
                raise _err("Esa contraseña de administración de SoftEther no es correcta. Probá de nuevo.")
            cfg["clave"] = clave_admin
            _guardar_cfg(cfg)
            pasos.append("Se usa la contraseña de administración que ya tenía el servidor (guardada en vpn.json)")
        elif _servidor_tiene_clave():
            raise _err(MSJ_YA_TIENE_CLAVE)
        else:
            # recién instalado: el servidor no tiene contraseña; el panel crea una al azar
            clave = _clave_aleatoria()
            try:
                _vpncmd("ServerPasswordSet", clave, clave="", csv_=False, timeout=15)
            except ErrorPideClave:
                raise _err(MSJ_YA_TIENE_CLAVE)
            cfg["clave"] = clave
            _guardar_cfg(cfg)
            pasos.append("Contraseña de administración creada (guardada en vpn.json)")
    # Hub DEFAULT: sin SecureNAT (usamos el DHCP del router a través del puente)
    try:
        _vpncmd("SecureNatDisable", hub=True)
    except ErrorVPN:
        pass
    pasos.append("Hub DEFAULT listo")
    _vpncmd("SstpEnable", "yes")
    pasos.append("SSTP activado (lo usa la VPN de Windows)")
    if nombre:
        try:
            _vpncmd("DynamicDnsSetHostname", nombre)
            pasos.append(f"Nombre elegido: {nombre}")
        except ErrorVPN as e:
            raise _err(f"El nombre '{nombre}' no está disponible o no es válido; probá otro. ({e})")
    _vpncmd("VpnAzureSetEnable", "yes")
    pasos.append("VPN Azure activado")
    try:  # 5555 no hace falta (VPN Azure y SSTP van por 443) y choca con adb/emuladores de Android
        listeners = _csv(_vpncmd("ListenerList"))
        if any(len(f) >= 1 and "5555" in f[0] for f in listeners[1:]):
            _vpncmd("ListenerDelete", "5555")
            pasos.append("Puerto 5555 desactivado (evita choques con adb y emuladores de Android)")
    except ErrorVPN:
        pass
    # puente al router
    ad = _adaptador_router()
    if ad:
        existentes = _csv(_vpncmd("BridgeList"))
        if not any(len(f) >= 3 and f[1] == HUB for f in existentes[1:]):
            disp = [f[0] for f in _csv(_vpncmd("BridgeDeviceList"))[1:] if f]
            elegido = next((x for x in disp if x.strip() == ad["descripcion"].strip()), None) or \
                next((x for x in disp if ad["descripcion"].split(" #")[0] in x), None)
            if not elegido:
                raise _err(f"No se encontró la placa '{ad['descripcion']}' en la lista de SoftEther: {disp}")
            _vpncmd("BridgeCreate", HUB, f"/DEVICE:{elegido}", "/TAP:no")
            pasos.append(f"Puente creado con la placa conectada al router ({elegido})")
        else:
            pasos.append("El puente al router ya existía")
    else:
        pasos.append("AVISO: no se encontró una placa de esta PC conectada al router; el puente no se creó")
    time.sleep(3)
    return {"mensaje": "VPN configurada", "pasos": pasos, "estado": estado_vpn()}


# ----------------------------------------------------------------------------
# usuarios
# ----------------------------------------------------------------------------
def listar_usuarios(_cli=None, _d=None) -> dict:
    filas = _csv(_vpncmd("UserList", hub=True))
    usuarios = []
    if not filas:
        return {"usuarios": usuarios}
    # columnas reales: User Name, Full Name, Group Name, Description, Auth Method, Num Logins, Last Login, ...
    cab = [c.strip().lower() for c in filas[0]]
    col = lambda *claves, defecto: next((i for i, c in enumerate(cab) if all(k in c for k in claves)), defecto)
    i_nom, i_acc, i_ult = col("user", "name", defecto=0), col("num", "login", defecto=5), col("last", "login", defecto=6)
    for f in filas[1:]:
        if len(f) > max(i_nom, i_acc, i_ult):
            ultimo = f[i_ult].strip()
            usuarios.append({"nombre": f[i_nom], "accesos": f[i_acc],
                             "ultimo_acceso": "Nunca" if ultimo in ("", "(None)", "None") else ultimo})
    return {"usuarios": usuarios}


def _validar_usuario(nombre: str) -> str:
    n = (nombre or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{2,32}", n):
        raise _err("Usuario: de 2 a 32 letras/números sin espacios ni acentos (ej. juan)")
    return n


def _validar_clave(clave: str) -> str:
    if len(clave or "") < 8 or not re.fullmatch(r"[\x21-\x7e]+", clave):
        raise _err("Contraseña: mínimo 8 caracteres, sin espacios ni acentos")
    return clave


def agregar_usuario(_cli, d: dict) -> dict:
    n = _validar_usuario(d.get("nombre"))
    c = _validar_clave(d.get("clave"))
    if any(u["nombre"] == n for u in listar_usuarios()["usuarios"]):
        raise _err("Ese usuario ya existe")
    _vpncmd("UserCreate", n, "/GROUP:none", "/REALNAME:none", "/NOTE:Panel del Router", hub=True)
    _vpncmd("UserPasswordSet", n, f"/PASSWORD:{c}", hub=True)
    return {"mensaje": f"Usuario {n} creado"}


def clave_usuario(_cli, d: dict) -> dict:
    n = _validar_usuario(d.get("nombre"))
    c = _validar_clave(d.get("clave"))
    _vpncmd("UserPasswordSet", n, f"/PASSWORD:{c}", hub=True)
    return {"mensaje": f"Contraseña de {n} cambiada"}


def borrar_usuario(_cli, d: dict) -> dict:
    n = _validar_usuario(d.get("nombre"))
    _vpncmd("UserDelete", n, hub=True)
    return {"mensaje": f"Usuario {n} borrado"}


def script_cliente(direccion: str, usuario: str) -> str:
    """Archivo .bat para la PC de afuera: crea la VPN SSTP de Windows y pide conectar."""
    direccion = re.sub(r"[^A-Za-z0-9.-]", "", direccion or "")
    usuario = re.sub(r"[^a-z0-9._-]", "", usuario or "")
    ps = (f"$n='Oficina'; Remove-VpnConnection -Name $n -Force -ErrorAction SilentlyContinue; "
          f"Add-VpnConnection -Name $n -ServerAddress '{direccion}' -TunnelType Sstp -EncryptionLevel Required "
          f"-AuthenticationMethod MSChapv2 -RememberCredential -Force; "
          f"Write-Host 'Listo: se creo la VPN Oficina' -ForegroundColor Green")
    return ("@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "echo ==============================================\r\n"
            "echo   Configurar VPN de la oficina (Windows 10)\r\n"
            "echo ==============================================\r\n"
            f"echo Servidor: {direccion}\r\n"
            f"echo Usuario:  {usuario}\r\n"
            "echo.\r\n"
            f"powershell -NoProfile -ExecutionPolicy Bypass -Command \"{ps}\"\r\n"
            "echo.\r\n"
            "echo Ahora se abre la conexion: escribi tu usuario y contrasena.\r\n"
            f"rasphone -d \"Oficina\"\r\n"
            "echo.\r\n"
            "echo Para conectarte otro dia: icono de red (abajo a la derecha) - Oficina - Conectar.\r\n"
            "pause\r\n")


# ----------------------------------------------------------------------------
# desinstalación (conserva el instalador descargado)
# ----------------------------------------------------------------------------
def _desinstalador() -> str | None:
    """Comando de desinstalación que SoftEther registra en Windows. Se buscan las dos
    vistas del registro (64 y 32 bits) para que funcione con el panel de 32 o 64 bits."""
    import winreg
    ruta = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    for vista in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            raiz = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta, 0, winreg.KEY_READ | vista)
        except OSError:
            continue
        with raiz:
            for i in range(winreg.QueryInfoKey(raiz)[0]):
                try:
                    with winreg.OpenKey(raiz, winreg.EnumKey(raiz, i)) as k:
                        nombre = winreg.QueryValueEx(k, "DisplayName")[0]
                        if "SoftEther VPN Server" in nombre:
                            return winreg.QueryValueEx(k, "UninstallString")[0]
                except OSError:
                    continue
    return None


def desinstalar(_cli, d: dict) -> dict:
    if not d.get("confirmo"):
        raise _err("Falta confirmar la desinstalación")
    cmd = _desinstalador()
    if not cmd:
        raise _err("No se encontró el desinstalador de SoftEther en Windows. "
                   "Desinstalalo desde Configuración > Aplicaciones > SoftEther VPN Server.")
    # separar ejecutable y argumentos:  "C:\...\vpnsetup.exe" /ARG
    m = re.match(r'\s*"([^"]+)"\s*(.*)$', cmd) or re.match(r"\s*(\S+)\s*(.*)$", cmd)
    exe, args = m.group(1), m.group(2)
    import ctypes
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args or None, os.path.dirname(exe), 1)
    if r <= 32:
        raise _err("No se pudo abrir el desinstalador (¿se rechazó el permiso de administrador?)")
    _desinstalando["activo"] = True
    return {"mensaje": "Se abrió el desinstalador de SoftEther. Aceptá el permiso y confirmá. "
                       "El instalador queda guardado para volver a instalar cuando quieras."}


def restablecer_acceso(_cli, d: dict) -> dict:
    """Deja en blanco la contraseña de administración de SoftEther (para cuando nadie la
    conoce). Con permiso de administrador: detiene el servicio, cambia el hash guardado
    en vpn_server.config por el de "contraseña vacía" y lo vuelve a iniciar.
    Solo toca esa línea (la del servidor); los usuarios y el resto quedan igual."""
    if not d.get("confirmo"):
        raise _err("Falta confirmar")
    config = next((os.path.join(c, "vpn_server.config") for c in CARPETAS
                   if os.path.isfile(os.path.join(c, "vpn_server.config"))), None)
    if not config:
        raise _err("No se encontró la configuración de SoftEther (vpn_server.config)")
    script = os.path.join(CARPETA_DESCARGAS, "restablecer-acceso-softether.ps1")
    os.makedirs(CARPETA_DESCARGAS, exist_ok=True)
    ruta_ps = config.replace("'", "''")
    contenido = (
        "$ErrorActionPreference = 'Stop'\r\n"
        f"$cfg = '{ruta_ps}'\r\n"
        "Stop-Service SEVPNSERVER -Force\r\n"
        "Start-Sleep -Seconds 2\r\n"
        "Copy-Item $cfg ($cfg + '.antes-de-restablecer') -Force\r\n"
        "$t = [IO.File]::ReadAllText($cfg)\r\n"
        "$i = $t.IndexOf('declare ServerConfiguration')\r\n"
        "if ($i -lt 0) { throw 'No se encontró ServerConfiguration' }\r\n"
        "$re = [regex]'byte HashedPassword \\S+'\r\n"
        f"$t = $t.Substring(0, $i) + $re.Replace($t.Substring($i), 'byte HashedPassword {HASH_CLAVE_VACIA}', 1)\r\n"
        "[IO.File]::WriteAllText($cfg, $t, (New-Object Text.UTF8Encoding($false)))\r\n"
        "Start-Service SEVPNSERVER\r\n")
    with open(script, "w", encoding="utf-8-sig") as f:
        f.write(contenido)
    import ctypes
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe",
                                            f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{script}"', None, 0)
    if r <= 32:
        raise _err("No se pudo restablecer (¿se rechazó el permiso de administrador?)")
    _archivar_cfg()
    return {"mensaje": "Restableciendo el acceso a SoftEther (unos segundos)…"}


ACCIONES = {
    ("GET", "vpn/estado"): estado_vpn,
    ("POST", "vpn/descargar"): descargar,
    ("GET", "vpn/progreso"): progreso,
    ("POST", "vpn/instalar"): instalar,
    ("POST", "vpn/configurar"): configurar,
    ("GET", "vpn/usuarios"): listar_usuarios,
    ("POST", "vpn/usuario/agregar"): agregar_usuario,
    ("POST", "vpn/usuario/clave"): clave_usuario,
    ("POST", "vpn/usuario/borrar"): borrar_usuario,
    ("POST", "vpn/desinstalar"): desinstalar,
    ("POST", "vpn/restablecer"): restablecer_acceso,
}
