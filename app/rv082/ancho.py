"""Control de ancho de banda (QoS, modo "Rate Control") — qos.htm.
Ver investigacion/spec_sistema.md §7. Formato de regla:
  <svcID>{<l1>.<l2>.<l3>.<ipIni>;<ipFin>(0.0.0.0)<dir>;<min>;<max>;<activa>;<wans>}
  dir: 2 = subida (Upstream), 1 = bajada (Downstream). min/max en kbit/s (0 = sin valor).
"""
from __future__ import annotations

import re

from .cliente import ClienteRV082, ErrorRouter, Formulario

_RX_OPC = re.compile(r'<option value="([^"]*)">([^<]*)</option>')
_RX_REGLA = re.compile(r"^(-?\d+)\{(\d+)\.(\d+)\.(\d+)\.(\d+);(\d+)\(([\d.]+)\)([12]);(\d+);(\d+);([01]);(\d*)\}$")


def _fn():
    from . import funciones
    return funciones


def _err(msg):
    return _fn().ErrorValidacion(msg)


def _valor_crudo(html: str, nombre: str):
    m = re.search(r"name=\"?" + re.escape(nombre) + r"\"?\s+value='([^']*)'", html)
    return m.group(1) if m else None


def _opciones_rc(menu: str) -> list[tuple[str, str]]:
    """Replica el document.write que arma RC_protocol: 1.ª opción, luego
    'Not Check Port' y después el resto sin repetir 16777235."""
    opciones = _RX_OPC.findall(menu or "")
    if not opciones:
        return []
    res = [opciones[0], ("16777235", "Not Check Port[TCP&UDP/0~0]")]
    res += [o for o in opciones[1:] if o[0] != "16777235"]
    return res


def _form_qos(cli: ClienteRV082, html: str | None = None):
    html = html if html is not None else cli.html("qos.htm")
    f = cli.formulario("qos.htm", "formQOS", html=html)
    menu = _valor_crudo(html, "service_menu1")
    return f, html, menu


def _reglas(f: Formulario) -> list[str] | None:
    cs = [c for c in f.controles if c["name"] == "qosRateList" and c["tag"] == "select"]
    if not cs:
        return None
    return [o["value"] for o in cs[0]["opciones"]]


def _preparar_envio(f: Formulario, menu: str, reglas: list[str]) -> None:
    """Lo que hace chSubmit(): clearContent + Percent=0 + selAll (invierte la lista)."""
    f.poner("submitStatus", "1")
    f.poner("service_menu1", menu)
    rc = _opciones_rc(menu)
    if len(rc) > 12:
        f.poner("RC_protocol", rc[12][0])   # clearRateContent: options[12]
    for n in ("IPbegin", "IPend", "Addr1", "Addr2", "Addr3", "Addr4"):
        f.poner(n, "0")
    f.poner("Percent", "0")
    f.poner("Maxrate", "")
    f.poner("RC_valid", False)
    for c in f.controles:
        if c["name"] == "wanEnable":
            c["checked"] = False
    for c in f.controles:
        if c["name"] == "qosRateList" and c["tag"] == "select":
            c["opciones"] = [{"value": v, "texto": v, "selected": True} for v in reversed(reglas)]


def leer_ancho(cli: ClienteRV082, _d=None) -> dict:
    f, html, menu = _form_qos(cli)
    nombres = {v: re.sub(r"\s*\[.*$", "", t).replace("All Traffic", "Todo el tráfico") for v, t in _RX_OPC.findall(menu or "")}
    reglas = []
    for v in _reglas(f) or []:
        m = _RX_REGLA.match(v)
        if not m:
            continue
        red = f"{m.group(2)}.{m.group(3)}.{m.group(4)}"
        ini, fin = m.group(5), m.group(6)
        if ini == "0" and fin == "0":
            equipos = "Todos"
        elif ini == fin:
            equipos = f"{red}.{ini}"
        else:
            equipos = f"{red}.{ini} a .{fin}"
        reglas.append({"valor": v, "servicio": nombres.get(m.group(1), m.group(1)), "servicio_id": m.group(1), "equipos": equipos,
                       "direccion": "Subida" if m.group(8) == "2" else "Bajada", "minimo": int(m.group(9)), "maximo": int(m.group(10)),
                       "activa": m.group(11) == "1"})
    servicios = [{"id": v, "texto": t.replace("All Traffic", "Todo el tráfico")} for v, t in _RX_OPC.findall(menu or "") if v != "16777235"]
    red = ".".join(f.valor(f"lanIP{i}", "") for i in (1, 2, 3))
    return {"modo_rate": _reglas(f) is not None, "subida": f.valor("ibwuWAN1", ""), "bajada": f.valor("ibwWAN1", ""),
            "reglas": reglas, "servicios": servicios, "red": red}


def _guardar(cli: ClienteRV082, transformar, subida=None, bajada=None) -> None:
    fn = _fn()
    f, html, menu = _form_qos(cli)
    if menu is None:
        raise ErrorRouter("No se pudo leer el catálogo de servicios de QoS")
    if _reglas(f) is None:
        # está en modo "Priority": pasar a "Rate Control" como el navegador (falseSubmit)
        f.poner("qosType", "1")
        f.poner("submitStatus", "0")
        html = cli.enviar(f)
        f, html, menu = _form_qos(cli, html)
        if _reglas(f) is None:
            f, html, menu = _form_qos(cli)
        if _reglas(f) is None:
            raise ErrorRouter("No se pudo pasar el control de ancho de banda a modo 'por velocidad'")
    actuales = _reglas(f)
    nuevas = transformar(list(actuales), f, menu)
    if subida is not None:
        f.poner("ibwuWAN1", str(fn.entero(subida, "Velocidad de subida", 1, 100000)))
    if bajada is not None:
        f.poner("ibwWAN1", str(fn.entero(bajada, "Velocidad de bajada", 1, 100000)))
    _preparar_envio(f, menu, nuevas)
    cli.enviar(f)


def guardar_velocidad(cli: ClienteRV082, d: dict) -> dict:
    _guardar(cli, lambda r, f, m: r, subida=d.get("subida"), bajada=d.get("bajada"))
    return {"mensaje": "Velocidad de la conexión guardada"}


def agregar_ancho(cli: ClienteRV082, d: dict) -> dict:
    fn = _fn()
    servicio = str(d.get("servicio", "16777216"))
    tipo = d.get("equipos_tipo", "una")  # una | rango | todos
    direcciones = {"subida": ["2"], "bajada": ["1"], "ambas": ["2", "1"]}.get(d.get("direccion", "ambas"))
    if not direcciones:
        raise _err("Dirección no válida")
    minimo = d.get("minimo") or ""
    maximo = d.get("maximo") or ""
    if str(minimo).strip() == "" and str(maximo).strip() == "":
        raise _err("Indicá una velocidad mínima garantizada o una máxima")
    mn = fn.entero(minimo, "Mínimo", 1, 99999) if str(minimo).strip() else 0
    mx = fn.entero(maximo, "Máximo", 1, 99999) if str(maximo).strip() else 0
    if mn and mx and mn > mx:
        raise _err("El mínimo no puede ser mayor que el máximo")

    def transformar(reglas, f, menu):
        red = [f.valor(f"lanIP{i}") for i in (1, 2, 3)]
        menu_ids = {v for v, _ in _RX_OPC.findall(menu or "")}
        if servicio not in menu_ids:
            raise _err("Servicio no válido")
        if tipo == "todos":
            ini, fin = 0, 0
        else:
            ip = fn.ip_valida(d.get("desde"), "IP del equipo")
            if ip[:3] != red:
                raise _err(f"La IP debe estar en la red {'.'.join(red)}.x")
            ini = int(ip[3])
            fin = ini
            if tipo == "rango":
                ip2 = fn.ip_valida(d.get("hasta"), "IP final")
                if ip2[:3] != red:
                    raise _err(f"La IP final debe estar en la red {'.'.join(red)}.x")
                fin = int(ip2[3])
                if fin < ini:
                    ini, fin = fin, ini
        capacidad = {"2": int(f.valor("ibwuWAN1") or 0), "1": int(f.valor("ibwWAN1") or 0)}
        for dr in direcciones:
            nombre = "subida" if dr == "2" else "bajada"
            if capacidad[dr] and (mx > capacidad[dr] or mn > capacidad[dr]):
                raise _err(f"La velocidad pedida supera la de {nombre} de tu conexión ({capacidad[dr]} kbit/s). "
                           "Corregí primero la velocidad de la conexión arriba.")
        nuevas = list(reglas)
        f.poner("RC_link", direcciones[-1])  # el navegador deja el combo en la última dirección usada
        for dr in direcciones:
            v = f"{servicio}{{{'.'.join(red)}.{ini};{fin}(0.0.0.0){dr};{mn};{mx};{1 if d.get('activa', True) else 0};1}}"
            clave = v.split(")")[0] + ")" + dr
            if any(x.split(")")[0] + ")" + x.split(")")[1][:1] == clave for x in nuevas if ")" in x):
                raise _err("Ya hay una regla para ese servicio, equipos y dirección")
            nuevas.append(v)
        if len(nuevas) > 100:
            raise _err("Máximo 100 reglas")
        return nuevas

    _guardar(cli, transformar)
    return {"mensaje": "Regla de ancho de banda agregada"}


def borrar_ancho(cli: ClienteRV082, d: dict) -> dict:
    valor = d.get("valor")

    def t(reglas, f, menu):
        if valor not in reglas:
            raise _err("Esa regla ya no existe (recargá la página)")
        return [v for v in reglas if v != valor]
    _guardar(cli, t)
    return {"mensaje": "Regla borrada"}


def activar_ancho(cli: ClienteRV082, d: dict) -> dict:
    valor, activa = d.get("valor"), bool(d.get("activa"))

    def t(reglas, f, menu):
        if valor not in reglas:
            raise _err("Esa regla ya no existe (recargá la página)")
        return [re.sub(r";([01]);(\d*)\}$", lambda m: f";{1 if activa else 0};{m.group(2)}}}", v) if v == valor else v for v in reglas]
    _guardar(cli, t)
    return {"mensaje": "Regla " + ("activada" if activa else "desactivada")}


ACCIONES = {
    ("GET", "ancho"): leer_ancho,
    ("POST", "ancho/velocidad"): guardar_velocidad,
    ("POST", "ancho/agregar"): agregar_ancho,
    ("POST", "ancho/borrar"): borrar_ancho,
    ("POST", "ancho/activar"): activar_ancho,
}
