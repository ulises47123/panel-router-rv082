"""Funciones de alto nivel del Panel RV082 (lectura y guardado por sección).

Cada guardado reproduce lo que hace el JavaScript de la página original
(onLoad + "Save Settings") sobre el formulario leído del router, para que
el POST sea idéntico al del navegador. Ver investigacion/spec_*.md.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import time

from .cliente import ClienteRV082, ErrorRouter, Formulario, texto_plano

try:  # parte de firewall / reenvío (módulo aparte)
    from . import seguridad as _seg
except ImportError:  # pragma: no cover
    _seg = None


class ErrorValidacion(Exception):
    """Dato ingresado por el usuario que no es válido (mensaje en español)."""


# ============================================================================
# Utilidades de validación
# ============================================================================
def ip_valida(texto: str, nombre="IP", permitir_cero=False) -> list[str]:
    texto = (texto or "").strip()
    try:
        ip = ipaddress.IPv4Address(texto)
    except ValueError:
        raise ErrorValidacion(f"{nombre}: '{texto}' no es una dirección IP válida (ej. 192.168.1.10)")
    if not permitir_cero and str(ip) == "0.0.0.0":
        raise ErrorValidacion(f"{nombre}: no puede ser 0.0.0.0")
    return str(ip).split(".")


def ip_o_vacia(texto: str, nombre="IP") -> list[str]:
    texto = (texto or "").strip()
    if not texto:
        return ["0", "0", "0", "0"]
    return ip_valida(texto, nombre, permitir_cero=True)


def mac_valida(texto: str) -> str:
    partes = re.split(r"[-:.\s]", (texto or "").strip())
    if len(partes) == 1 and len(partes[0]) == 12:
        partes = [partes[0][i:i + 2] for i in range(0, 12, 2)]
    if len(partes) != 6 or not all(re.fullmatch(r"[0-9a-fA-F]{1,2}", p) for p in partes):
        raise ErrorValidacion(f"MAC '{texto}' no válida (ej. aa-bb-cc-dd-ee-ff)")
    return "-".join(p.lower().zfill(2) for p in partes)


def entero(valor, nombre, minimo, maximo) -> int:
    try:
        n = int(str(valor).strip())
    except ValueError:
        raise ErrorValidacion(f"{nombre}: debe ser un número")
    if not minimo <= n <= maximo:
        raise ErrorValidacion(f"{nombre}: debe estar entre {minimo} y {maximo}")
    return n


def texto_seguro(valor, nombre, largo, vacio_ok=True, sin_espacios=False) -> str:
    v = (valor or "").strip()
    if not v and not vacio_ok:
        raise ErrorValidacion(f"{nombre}: no puede quedar vacío")
    if len(v) > largo:
        raise ErrorValidacion(f"{nombre}: máximo {largo} caracteres")
    if any(ord(ch) > 126 or ord(ch) < 32 for ch in v):
        raise ErrorValidacion(f"{nombre}: usá solo letras sin acentos, números y símbolos comunes")
    if sin_espacios and " " in v:
        raise ErrorValidacion(f"{nombre}: no puede tener espacios")
    return v


def _octetos(f: Formulario, prefijo: str) -> str:
    return ".".join(f.valor(f"{prefijo}{i}", "0") or "0" for i in range(1, 5))


def _poner_octetos(f: Formulario, prefijo: str, octetos: list[str]) -> None:
    for i, o in enumerate(octetos, 1):
        f.poner(f"{prefijo}{i}", o)


def _control(f: Formulario, nombre: str) -> list[dict]:
    return [c for c in f.controles if c["name"] == nombre]


def _marcado(f: Formulario, nombre: str) -> bool:
    return any(c.get("checked") for c in _control(f, nombre))


def _seleccionar_todo(f: Formulario, nombre: str, invertir=True) -> None:
    for c in _control(f, nombre):
        if invertir:
            c["opciones"].reverse()
        for o in c["opciones"]:
            o["selected"] = True


def _verificar(cli: ClienteRV082, pagina: str, esperado: dict, form=None) -> list[str]:
    """Relee la página y devuelve los campos que no quedaron como se esperaba."""
    time.sleep(0.8)
    f = cli.formulario(pagina, form)
    d = f.como_dict()
    return [k for k, v in esperado.items() if str(d.get(k)) != str(v)]


# ============================================================================
# INICIO / ESTADO
# ============================================================================
def estado(cli: ClienteRV082, _datos=None) -> dict:
    html = cli.html("home.htm")
    limpio = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    t = texto_plano(limpio)

    def busca(patron, grupo=1, defecto=""):
        m = re.search(patron, t)
        return m.group(grupo).strip() if m else defecto

    wan = ""
    m = re.search(r"LAN IP :\s*[\d.]+\s*(?:WAN IP\s*)?:\s*([\d.]+)", t)
    if m:
        wan = m.group(1)
    puertos = {k: v == "1" for k, v in re.findall(r"images_rv082/(po\d|wan|dmz)_(\d)\.gif", limpio)}
    firmware = busca(r"Firmware version :\s*(.+?)\s*\(")
    return {
        "modelo": "Cisco/Linksys RV082",
        "serie": busca(r"Serial Number :\s*(\S+)"),
        "firmware": firmware,
        "firmware_fecha": busca(r"Firmware version :\s*.+?\((.+?)\)"),
        "encendido": _uptime_es(busca(r"System up time :\s*(.+?)\s*\(Now")),
        "hora_router": busca(r"\(Now:\s*(.+?)\s*\)"),
        "lan_ip": busca(r"LAN IP :\s*([\d.]+)"),
        "wan_ip": wan or "0.0.0.0",
        "internet": bool(wan) and wan != "0.0.0.0",
        "dns": busca(r"Mode :\s*\w+\s+DNS\s*:?\s*((?:\d+\.){3}\d+(?:\s+(?:\d+\.){3}\d+)?)"),
        "dmz_host": busca(r"DMZ Host :\s*(\w+)") == "Enabled",
        "puertos": {"lan": [puertos.get(f"po{i}", False) for i in range(1, 9)],
                    "wan": puertos.get("wan", False), "dmz": puertos.get("dmz", False)},
        "firewall": "firewall0" in html and re.search(r"name=\"?firewall0\"?\s+value='\s*checked'", html) is not None,
    }


def _uptime_es(s: str) -> str:
    for a, b in (("Days", "días"), ("Day", "día"), ("Hours", "h"), ("Hour", "h"),
                 ("Minutes", "min"), ("Minute", "min"), ("Seconds", "s"), ("Second", "s")):
        s = s.replace(a, b)
    return s


def puerto_detalle(cli: ClienteRV082, datos: dict) -> dict:
    n = str(datos.get("puerto", "1"))
    especiales = {"wan": "wan_port_information.htm", "dmz": "dmz_port_information.htm"}
    pagina = especiales[n] if n in especiales else f"port{entero(n, 'Puerto', 1, 8)}_information.htm"
    t = texto_plano(re.sub(r"<!--.*?-->", "", cli.html(pagina), flags=re.S))
    campos = {"enlace": "Link Status", "actividad": "Port Activity", "velocidad": "Speed Status",
              "duplex": "Duplex Status", "autoneg": "Auto negotiation", "rx_paquetes": "Port Receive Packet Count",
              "rx_bytes": "Port Receive Packet Byte Count", "tx_paquetes": "Port Transmit Packet Count",
              "tx_bytes": "Port Transmit Packet Byte Count", "errores": "Port Packet Error Count"}
    res = {}
    for k, etq in campos.items():
        m = re.search(re.escape(etq) + r"\s+(.+?)(?=\s+(?:" + "|".join(re.escape(x) for x in campos.values()) + r"|Priority|VLAN|Interface|Type|Close|$))", t)
        res[k] = m.group(1).strip() if m else ""
    return res


# ============================================================================
# INTERNET (WAN1)  — network.htm
# ============================================================================
TIPOS_WAN = {"1": "dhcp", "2": "estatica", "3": "pppoe"}
TIPOS_WAN_INV = {v: k for k, v in TIPOS_WAN.items()}


def _fix_network(f: Formulario) -> Formulario:
    """Replica onLoad (chDismatchLanMask, chsetDNS, chSH1/2) y chSubmit de network.htm."""
    lan = (f.valor("LanIp") or "").strip().split(" ")[0].split(".")
    if len(lan) == 4:
        _poner_octetos(f, "LanIp", lan)
    mascara = (f.valor("netMaskAll") or "").strip().split(" ")[0].split(".")
    if len(mascara) == 4:
        _poner_octetos(f, "netMaskIp", mascara)
    tipo = f.valor("WAN1ConnectionType")
    if tipo == "1" and f.tiene("setWan1DNS"):
        on = _marcado(f, "setWan1DNS")
        f.poner("Wan1DnsNeq", "0" if on else "1")
        for letra in "AB":
            for i in range(1, 5):
                f.habilitar(f"Wan1Dns{letra}{i}", on)
    for k in ("1", "2"):
        if f.tiene(f"bytesMTU{k}") and f.tiene(f"mtu_auto{k}"):
            f.habilitar(f"bytesMTU{k}", f.valor(f"mtu_auto{k}") != "1")
    f.habilitar("WAN1ConnectionType", True)
    f.habilitar("WAN2ConnectionType", True)
    for c in f.controles:
        if c["name"].startswith("Wan2DmzIp"):
            c["disabled"] = False
    f.poner("submitStatus", "1")
    return f


def _swap_dns(f: Formulario, a: str, b: str) -> None:
    """Si DNS1 es 0.0.0.0 y DNS2 no, el JS los intercambia."""
    if f.tiene(f"{a}1") and _octetos(f, a) == "0.0.0.0" and _octetos(f, b) != "0.0.0.0":
        dns2 = _octetos(f, b).split(".")
        _poner_octetos(f, a, dns2)
        _poner_octetos(f, b, ["0"] * 4)


def leer_internet(cli: ClienteRV082, _d=None) -> dict:
    html = cli.html("network.htm")
    f = _fix_network(cli.formulario("network.htm", "formNetwork", html=html))
    tipo = f.valor("WAN1ConnectionType")
    res = {"tipo": TIPOS_WAN.get(tipo, "otro"), "tipo_codigo": tipo,
           "mtu_auto": f.valor("mtu_auto1") == "1", "mtu": f.valor("bytesMTU1") or
           next((c["value"] for c in _control(f, "bytesMTU1")), "1500"),
           "dns_manual": False, "dns1": "", "dns2": ""}
    def octs(prefijo):
        vals = [next((c["value"] for c in _control(f, f"{prefijo}{i}")), "0") or "0" for i in range(1, 5)]
        ip = ".".join(vals)
        return "" if ip == "0.0.0.0" else ip
    if tipo == "1":
        res["dns_manual"] = _marcado(f, "setWan1DNS")
    res["dns1"], res["dns2"] = octs("Wan1DnsA"), octs("Wan1DnsB")
    if tipo == "2":
        res.update(ip=octs("Wan1AliasIp"), mascara=octs("Wan1AliasMaskIp"), puerta=octs("Wan1RouterIp"))
    if tipo == "3":
        res.update(usuario=f.valor("Wan1UserName", ""), servicio=f.valor("Wan1ServiceName", ""),
                   mantener=f.valor("Wan1ConnectAlive") == "2", clave_guardada=bool(next((c["value"] for c in _control(f, "Wan1PassWord")), "")))
    return res


def guardar_internet(cli: ClienteRV082, d: dict) -> dict:
    tipo = d.get("tipo")
    if tipo not in TIPOS_WAN_INV:
        raise ErrorValidacion("Tipo de conexión no válido")
    codigo = TIPOS_WAN_INV[tipo]
    # validar antes de tocar nada
    dns1 = ip_o_vacia(d.get("dns1"), "DNS 1")
    dns2 = ip_o_vacia(d.get("dns2"), "DNS 2")
    mtu_auto = bool(d.get("mtu_auto", True))
    mtu = entero(d.get("mtu", 1500), "MTU", 68, 1500) if not mtu_auto else None
    if tipo == "estatica":
        ip = ip_valida(d.get("ip"), "IP de internet")
        mascara = ip_valida(d.get("mascara"), "Máscara")
        puerta = ip_valida(d.get("puerta"), "Puerta de enlace")
        if dns1 == ["0"] * 4 and dns2 == ["0"] * 4:
            raise ErrorValidacion("Con IP fija hay que indicar al menos un DNS (ej. 8.8.8.8)")
    if tipo == "pppoe":
        usuario = texto_seguro(d.get("usuario"), "Usuario PPPoE", 60, vacio_ok=False)
        servicio = texto_seguro(d.get("servicio"), "Nombre de servicio", 60)

    html = cli.html("network.htm")
    f = cli.formulario("network.htm", "formNetwork", html=html)
    if f.valor("WAN1ConnectionType") != codigo:
        # Paso A (falseSubmit): el router redibuja la página con el bloque del tipo nuevo
        fa = _fix_network(f)
        fa.poner("WAN1ConnectionType", codigo)
        fa.poner("submitStatus", "0")
        html = cli.enviar(fa)
        f = cli.formulario("network.htm", "formNetwork", html=html)
        if f.valor("WAN1ConnectionType") != codigo:
            f = cli.formulario("network.htm", "formNetwork")
            f.poner("WAN1ConnectionType", codigo)
    f = _fix_network(f)

    if tipo == "dhcp":
        manual = bool(d.get("dns_manual"))
        if f.tiene("setWan1DNS"):
            f.poner("setWan1DNS", manual)
            f.poner("Wan1DnsNeq", "0" if manual else "1")
            for letra in "AB":
                for i in range(1, 5):
                    f.habilitar(f"Wan1Dns{letra}{i}", manual)
            if manual:
                if dns1 == ["0"] * 4 and dns2 == ["0"] * 4:
                    raise ErrorValidacion("Si elegís DNS manual, escribí al menos uno")
                _poner_octetos(f, "Wan1DnsA", dns1)
                _poner_octetos(f, "Wan1DnsB", dns2)
                _swap_dns(f, "Wan1DnsA", "Wan1DnsB")
    elif tipo == "estatica":
        _poner_octetos(f, "Wan1AliasIp", ip)
        _poner_octetos(f, "Wan1AliasMaskIp", mascara)
        _poner_octetos(f, "Wan1RouterIp", puerta)
        _poner_octetos(f, "Wan1DnsA", dns1)
        _poner_octetos(f, "Wan1DnsB", dns2)
        _swap_dns(f, "Wan1DnsA", "Wan1DnsB")
    elif tipo == "pppoe":
        f.poner("Wan1UserName", usuario)
        clave = d.get("clave") or ""
        if clave:
            f.poner("Wan1PassWord", texto_seguro(clave, "Clave PPPoE", 60))
        elif not next((c["value"] for c in _control(f, "Wan1PassWord")), ""):
            raise ErrorValidacion("Escribí la contraseña PPPoE que te dio el proveedor")
        f.poner("Wan1ServiceName", servicio)
        f.poner("Wan1ConnectAlive", "2" if d.get("mantener", True) else "1")

    if f.tiene("mtu_auto1"):
        f.poner("mtu_auto1", "1" if mtu_auto else "0")
        f.habilitar("bytesMTU1", not mtu_auto)
        if not mtu_auto:
            f.poner("bytesMTU1", str(mtu))
    cli.enviar(f)
    return {"mensaje": "Configuración de internet guardada", "fallidos": []}


# ============================================================================
# RED LOCAL (LAN) — network.htm
# ============================================================================
MASCARAS = {"0": "255.255.255.0", "128": "255.255.255.128", "192": "255.255.255.192",
            "224": "255.255.255.224", "240": "255.255.255.240", "248": "255.255.255.248", "252": "255.255.255.252"}


def leer_lan(cli: ClienteRV082, _d=None) -> dict:
    f = _fix_network(cli.formulario("network.htm", "formNetwork"))
    html = cli.ultimo_html.get("network.htm", "")
    m = re.search(r"MAC Address:\s*([0-9a-fA-F-]{17})", html)
    return {"ip": _octetos(f, "ipAddr"), "mascara": f.valor("netMask"), "mascaras": MASCARAS,
            "nombre": f.valor("hostname", ""), "dominio": f.valor("DomainName", ""),
            "mac": m.group(1) if m else ""}


def guardar_lan(cli: ClienteRV082, d: dict) -> dict:
    ip = ip_valida(d.get("ip"), "IP del router")
    if ip[0] == "127" or ip[3] in ("0", "255"):
        raise ErrorValidacion("IP del router no válida")
    mascara = str(d.get("mascara", "0"))
    if mascara not in MASCARAS:
        raise ErrorValidacion("Máscara no válida")
    nombre = texto_seguro(d.get("nombre"), "Nombre del equipo", 31, sin_espacios=True)
    dominio = texto_seguro(d.get("dominio"), "Dominio", 63, sin_espacios=True)
    f = _fix_network(cli.formulario("network.htm", "formNetwork"))
    ip_vieja = _octetos(f, "ipAddr")
    f.poner("hostname", nombre)
    f.poner("DomainName", dominio)
    _poner_octetos(f, "ipAddr", ip)  # LanIp* conserva la IP vieja (así lo compara el router)
    f.poner("netMask", mascara)
    cli.enviar(f)
    nueva = ".".join(ip)
    if nueva != ip_vieja:
        return {"mensaje": f"IP del router cambiada a {nueva}. Reconectá este programa a esa IP.", "nueva_ip": nueva}
    return {"mensaje": "Red local guardada"}


# ============================================================================
# DHCP — dhcp_setup.htm / dhcp_status.htm
# ============================================================================
def _fix_dhcp(f: Formulario) -> Formulario:
    f.poner("dhcpStatusChange", "1" if _marcado(f, "dhcpStatus") else "0")
    f.poner("dhcpRelayChange", "1" if _marcado(f, "dhcpRelay") else "0")
    f.poner("submitStatus", "1")
    _seleccionar_todo(f, "dhcp_staticList1")
    _seleccionar_todo(f, "dhcp_dnsList")
    if f.tiene("LanDnsA1"):
        _swap_dns(f, "LanDnsA", "LanDnsB")
    if f.tiene("ds4") and f.tiene("de4"):
        try:
            a, b = int(f.valor("ds4")), int(f.valor("de4"))
            if a > b:
                f.poner("ds4", str(b)); f.poner("de4", str(a))
        except (TypeError, ValueError):
            pass
    return f


def _parse_reserva(valor: str) -> dict | None:
    m = re.match(r"\s*([\d.]+)\s*=>\s*([0-9a-fA-F:-]{11,17})\s+([01])\s*(.*)$", valor or "")
    if not m:
        return None
    return {"ip": m.group(1), "mac": m.group(2).lower(), "activa": m.group(3) == "1", "nombre": m.group(4).strip()}


def leer_dhcp(cli: ClienteRV082, _d=None) -> dict:
    f = cli.formulario("dhcp_setup.htm", "formDHCPSetup")
    reservas = []
    for c in _control(f, "dhcp_staticList1"):
        for o in c["opciones"]:
            r = _parse_reserva(o["value"])
            if r:
                reservas.append(r)
    activo = _marcado(f, "dhcpStatus")
    red = ".".join([f.valor("ds1", "192"), f.valor("ds2", "168"), f.valor("ds3", "1")])
    def ip(pref):
        v = _octetos(f, pref)
        return "" if v == "0.0.0.0" else v
    return {"activo": activo, "red": red, "desde": f.valor("ds4", ""), "hasta": f.valor("de4", ""),
            "minutos": f.valor("clTime", "1440"), "dns1": ip("LanDnsA"), "dns2": ip("LanDnsB"),
            "reservas": reservas, "lan_ip": f.valor("LanIp", "")}


def guardar_dhcp(cli: ClienteRV082, d: dict) -> dict:
    f = cli.formulario("dhcp_setup.htm", "formDHCPSetup")
    activo = bool(d.get("activo", True))
    lan_ip = f.valor("LanIp", "")
    red = ".".join([f.valor("ds1", "192"), f.valor("ds2", "168"), f.valor("ds3", "1")])

    # reservas: siempre se manda la lista COMPLETA (si falta, el router las borra)
    nuevas = []
    ips_vistas, macs_vistas = set(), set()
    for r in d.get("reservas", []):
        ipr = ".".join(ip_valida(r.get("ip"), "IP de la reserva"))
        mac = mac_valida(r.get("mac"))
        nombre = texto_seguro(r.get("nombre"), "Nombre de la reserva", 12, sin_espacios=True)
        if ipr == lan_ip:
            raise ErrorValidacion(f"{ipr} es la IP del router")
        if not ipr.startswith(red + "."):
            raise ErrorValidacion(f"La reserva {ipr} debe estar en la red {red}.x")
        if ipr in ips_vistas or mac in macs_vistas:
            raise ErrorValidacion(f"Reserva repetida: {ipr} / {mac}")
        ips_vistas.add(ipr); macs_vistas.add(mac)
        nuevas.append((ipr, f"{ipr} => {mac} {1 if r.get('activa', True) else 0} {nombre}".rstrip()))
    if len(nuevas) > 253:
        raise ErrorValidacion("Máximo 253 reservas")
    nuevas.sort(key=lambda x: tuple(int(p) for p in x[0].split(".")))  # sortIP del JS
    for c in _control(f, "dhcp_staticList1"):
        c["opciones"] = [{"value": v, "texto": v, "selected": True} for _, v in nuevas]

    if bool(_marcado(f, "dhcpStatus")) != activo:
        # Paso A como el navegador (falseSubmit): redibujar con el nuevo estado
        fa = cli.formulario("dhcp_setup.htm", "formDHCPSetup")
        fa.poner("dhcpStatus", activo)
        fa.poner("dhcpStatusChange", "1" if activo else "0")
        fa.poner("dhcpRelayChange", "1" if _marcado(fa, "dhcpRelay") else "0")
        fa.poner("submitStatus", "0")
        _seleccionar_todo(fa, "dhcp_staticList1", invertir=False)
        html = cli.enviar(fa)
        f2 = cli.formulario("dhcp_setup.htm", "formDHCPSetup", html=html)
        for c in _control(f2, "dhcp_staticList1"):
            c["opciones"] = [{"value": v, "texto": v, "selected": True} for _, v in nuevas]
        f = f2
        f.poner("dhcpStatus", activo)

    if activo and f.tiene("clTime"):
        desde = entero(d.get("desde"), "Rango desde", 1, 254)
        hasta = entero(d.get("hasta"), "Rango hasta", 1, 254)
        if desde > hasta:
            desde, hasta = hasta, desde
        lan_ult = int(lan_ip.split(".")[-1]) if lan_ip else 1
        if desde <= lan_ult <= hasta:
            raise ErrorValidacion(f"El rango no puede incluir la IP del router (.{lan_ult})")
        for _, v in nuevas:
            pass
        f.poner("ds4", str(desde))
        f.poner("de4", str(hasta))
        f.poner("clTime", str(entero(d.get("minutos", 1440), "Tiempo de préstamo", 5, 43200)))
        _poner_octetos(f, "LanDnsA", ip_o_vacia(d.get("dns1"), "DNS 1"))
        _poner_octetos(f, "LanDnsB", ip_o_vacia(d.get("dns2"), "DNS 2"))
    # nunca activamos "bloquear MAC fuera de la lista" desde aquí (deja afuera equipos)
    _fix_dhcp(f)
    cli.enviar(f)
    return {"mensaje": "DHCP guardado"}


def clientes_dhcp(cli: ClienteRV082, _d=None) -> dict:
    html = re.sub(r"<!--.*?-->", "", cli.html("dhcp_status.htm"), flags=re.S)
    t = texto_plano(html)
    def num(etq):
        m = re.search(re.escape(etq) + r"\s*:\s*(\d+)", t)
        return int(m.group(1)) if m else 0
    clientes = []
    tabla = re.search(r"Client Host Name.*?</tr>(.*?)</table>", html, re.S | re.I)
    if tabla:
        for fila in re.findall(r"<tr[^>]*>(.*?)(?=<tr|$)", tabla.group(1), re.S | re.I):
            celdas = [texto_plano(c) for c in re.findall(r"<td[^>]*>(.*?)(?=<td|</tr|$)", fila, re.S | re.I)]
            if len(celdas) >= 4 and re.match(r"\d+\.\d+\.\d+\.\d+", celdas[1]):
                clientes.append({"nombre": celdas[0], "ip": celdas[1], "mac": celdas[2].lower(), "tiempo": celdas[3]})
    return {"usadas": num("Dynamic IP Used"), "fijas": num("Static IP Used"),
            "libres": num("DHCP Available"), "total": num("Total"), "clientes": clientes}


# ============================================================================
# PUERTOS DEL SWITCH — lan_setting.htm
# ============================================================================
def _nombres_puerto(n: int) -> dict:
    if n <= 8:
        return {"dis": f"port{n}Disabled", "chk": f"portDisable{n}", "prio": f"port{n}Priority",
                "vel": f"port{n}Speed", "dup": f"port{n}Duplex", "auto": f"auto{n}Neg", "autochk": f"autoNeg{n}",
                "vlan": f"port{n}VlanGroup"}
    pre = "Dmz" if n == 9 else "Wan"
    return {"dis": f"{pre}PortDisabled", "chk": f"portDisable{n}", "prio": None, "vel": f"{pre}portSpeed",
            "dup": f"{pre}portDuplex", "auto": f"auto{pre}Neg", "autochk": f"autoNeg{n}", "vlan": None}


def _fix_puertos(f: Formulario) -> Formulario:
    """Replica checkChecked()/checkRadio() de lan_setting.htm para los 10 puertos."""
    for n in range(1, 11):
        k = _nombres_puerto(n)
        if not f.tiene(k["chk"]):
            continue
        apagado = _marcado(f, k["chk"])
        auto = _marcado(f, k["autochk"])
        f.poner(k["dis"], "1" if apagado else "0")
        f.poner(k["auto"], "1" if auto else "0")
        f.poner(k["vel"], "0" if _marcado(f, f"speed{n}f") else "1")
        f.poner(k["dup"], "0" if _marcado(f, f"duplex{n}f") else "1")
        for r in (f"speed{n}f", f"speed{n}s", f"duplex{n}f", f"duplex{n}s"):
            f.habilitar(r, not apagado and not auto)
        f.habilitar(k["autochk"], not apagado)
        if k["prio"]:
            f.habilitar(k["prio"], not apagado)
        if k["vlan"]:
            f.habilitar(k["vlan"], not apagado)
    return f


def leer_puertos(cli: ClienteRV082, _d=None) -> dict:
    f = cli.formulario("lan_setting.htm", "formlan_setting")
    lista = []
    for n in range(1, 9):
        k = _nombres_puerto(n)
        lista.append({"n": n, "activo": not _marcado(f, k["chk"]),
                      "prioridad_alta": next((o["selected"] for c in _control(f, k["prio"]) for o in c["opciones"] if o["value"] == "1"), False)})
    try:
        enlaces = estado(cli)["puertos"]["lan"]
    except ErrorRouter:
        enlaces = [False] * 8
    for p, e in zip(lista, enlaces):
        p["enlace"] = e
    return {"puertos": lista}


def guardar_puertos(cli: ClienteRV082, d: dict) -> dict:
    f = cli.formulario("lan_setting.htm", "formlan_setting")
    pedidos = {int(p["n"]): p for p in d.get("puertos", []) if 1 <= int(p["n"]) <= 8}
    if pedidos and all(not p.get("activo", True) for p in pedidos.values()) and len(pedidos) == 8:
        raise ErrorValidacion("No se pueden apagar los 8 puertos a la vez")
    enlaces = estado(cli)["puertos"]["lan"]
    for n, p in pedidos.items():
        k = _nombres_puerto(n)
        apagar = not p.get("activo", True)
        if apagar and enlaces[n - 1] and not d.get("confirmo_enlace"):
            raise ErrorValidacion(f"El puerto {n} tiene un cable conectado (¿es el de esta PC?). Confirmá para apagarlo.")
        f.poner(k["chk"], apagar)
        f.poner(k["prio"], "1" if p.get("prioridad_alta") else "0")
    _fix_puertos(f)
    cli.enviar(f)
    return {"mensaje": "Puertos guardados"}


# ============================================================================
# HERRAMIENTAS — sys_diag.htm y registro
# ============================================================================
def _lanzar_diag(cli: ClienteRV082, modo: str, valor: str) -> str:
    """modo '2' = ping, '1' = DNS. Lanza la prueba y espera el resultado (la página se
    recarga sola cada 2 s mientras el router trabaja)."""
    campo = "pingAddr" if modo == "2" else "dnsName"
    f = cli.formulario("sys_diag.htm", "formsys_diag")
    if not f.tiene(campo):  # la página está en el otro modo: cambiar (falseSubmit)
        f.poner("diagType", modo); f.poner("submitStatus", "0")
        html = cli.enviar(f, respaldo=False)
        f = cli.formulario("sys_diag.htm", "formsys_diag", html=html)
        if not f.tiene(campo):
            f = cli.formulario("sys_diag.htm", "formsys_diag")
    f.poner("diagType", modo); f.poner("submitStatus", "1"); f.poner(campo, valor); f.poner("submitType", modo)
    html = cli.enviar(f, respaldo=False)
    limite = time.time() + 45
    while "http-equiv=refresh" in re.sub(r"<!--.*?-->", "", html, flags=re.S) and time.time() < limite:
        time.sleep(2)
        html = cli.html("sys_diag.htm")
    return html


def _bloque_diag(html: str, etiqueta: str) -> dict:
    limpio = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    m = re.search(re.escape(etiqueta) + r"(.*?)</table>", limpio, re.S)
    filas = {}
    if m:
        for k, v in re.findall(r"<td>([^<]*?):(?:&nbsp;)?\s*</td>\s*<td>(.*?)</td>", m.group(1), re.S):
            filas[k.strip()] = texto_plano(v.replace("<br>", " | "))
    return filas


def ping(cli: ClienteRV082, d: dict) -> dict:
    destino = ".".join(ip_valida(d.get("destino"), "Dirección a probar"))
    viejo = cli.tiempo_espera
    cli.tiempo_espera = 40
    try:
        html = _lanzar_diag(cli, "2", destino)
    finally:
        cli.tiempo_espera = viejo
    r = _bloque_diag(html, "Ping host or IP address")
    estado_txt = r.get("Status", "")
    ok = "Succe" in estado_txt or "Passed" in estado_txt
    paq = r.get("Packets", "")
    m = re.search(r"(\d+)/(\d+) transmitted, (\d+)/\d+ received, (\d+)% loss", paq)
    rt = r.get("Round Trip Time", "")
    prom = re.search(r"Average = (\d+) ms", rt)
    if m:
        resumen = f"Enviados {m.group(1)}, recibidos {m.group(3)}, perdidos {m.group(4)}%"
    else:
        resumen = paq or "Sin datos"
    if not estado_txt:
        resumen = "El router no devolvió resultado"
    return {"ok": bool(m and m.group(3) != "0"), "destino": destino, "resumen": resumen,
            "promedio_ms": prom.group(1) if prom and m and m.group(3) != "0" else None,
            "estado": "Responde" if (m and m.group(3) != "0") else "No responde"}


def dns(cli: ClienteRV082, d: dict) -> dict:
    nombre = texto_seguro(d.get("nombre"), "Dominio", 64, vacio_ok=False, sin_espacios=True)
    viejo = cli.tiempo_espera
    cli.tiempo_espera = 40
    try:
        html = _lanzar_diag(cli, "1", nombre)
    finally:
        cli.tiempo_espera = viejo
    r = _bloque_diag(html, "Look up the name")
    texto = " ".join(f"{k}: {v}" for k, v in r.items() if k not in ("Look up the name",))
    ips = re.findall(r"(?:\d{1,3}\.){3}\d{1,3}", texto)
    fallo = "Fail" in texto or not ips
    return {"ok": not fallo, "nombre": nombre, "ips": ips,
            "resumen": ("Resuelve a: " + ", ".join(ips)) if not fallo else ("No se pudo resolver el dominio" + (f" ({texto})" if texto else ""))}


TIPOS_LOG = {"Authentication Failure": "Inicio de sesión fallido", "Authentication Success": "Inicio de sesión correcto",
             "System Log": "Sistema", "Connection Refused - Policy violation": "Conexión bloqueada",
             "Connection Accepted": "Conexión permitida", "Configuration Change": "Cambio de configuración"}


def registro(cli: ClienteRV082, d: dict) -> dict:
    cual = d.get("tipo", "sistema")
    pagina = {"sistema": "sys_log.htm", "entrante": "incoming_log.htm", "saliente": "outgoing_log.htm"}.get(cual, "sys_log.htm")
    html = cli.html(pagina)
    filas = re.findall(r"<tr><td align=center>(.*?)</td><td>(.*?)</td><td>(.*?)</td>", html, re.S | re.I)
    entradas = []
    for fecha, tipo, msg in filas:
        tipo = texto_plano(tipo)
        entradas.append({"fecha": texto_plano(fecha), "tipo": TIPOS_LOG.get(tipo, tipo), "mensaje": texto_plano(msg)})
    entradas.reverse()  # el más nuevo primero
    limite = int(d.get("limite", 300))
    m = re.search(r"Current Time:(?:\s|&nbsp;)*([A-Z][^<]+?)\s*<", html)
    return {"entradas": entradas[:limite], "total": len(entradas),
            "hora": texto_plano(m.group(1)) if m else "",
            "fallos_login": sum(1 for e in entradas if e["tipo"] == "Inicio de sesión fallido")}


# ============================================================================
# SISTEMA — contraseña, hora, respaldo, reinicio
# ============================================================================
def cambiar_clave(cli: ClienteRV082, d: dict) -> dict:
    vieja = d.get("actual") or ""
    nueva = texto_seguro(d.get("nueva"), "Contraseña nueva", 64, vacio_ok=False, sin_espacios=True)
    if nueva != (d.get("repetir") or ""):
        raise ErrorValidacion("Las contraseñas nuevas no coinciden")
    if len(nueva) < 8:
        raise ErrorValidacion("Usá al menos 8 caracteres")
    if vieja != cli.clave:
        raise ErrorValidacion("La contraseña actual no es correcta")
    usuario = texto_seguro(d.get("usuario"), "Usuario", 64, sin_espacios=True)
    f = cli.formulario("password.htm", "formPassword")
    clave_auth = f.valor("auth_key", "")
    md5 = hashlib.md5((vieja + clave_auth).encode("latin-1")).hexdigest()
    pares = [("page", "password.htm"), ("oPass", ""), ("md5_pass", md5), ("auth_key", clave_auth),
             ("nUser", usuario), ("cUser", usuario), ("nPass", nueva), ("cPass", nueva)]
    cli.post("password.htm", pares, respaldo=False)
    return {"mensaje": "Contraseña cambiada", "usuario": usuario or cli.usuario, "clave": nueva}


ZONAS = None


def leer_hora(cli: ClienteRV082, _d=None) -> dict:
    f = cli.formulario("time1.htm", "formTime")
    zonas = f.opciones("time_zone")
    return {"zona": f.valor("time_zone"), "zonas": zonas, "ntp": f.valor("sNTP", ""),
            "verano": _marcado(f, "enableDaylight"), "modo": f.valor("statussetMode", "1")}


def guardar_hora(cli: ClienteRV082, d: dict) -> dict:
    f = cli.formulario("time1.htm", "formTime")
    zona = str(d.get("zona", "20"))
    if zona not in [v for v, _ in f.opciones("time_zone")]:
        raise ErrorValidacion("Zona horaria no válida")
    ntp = texto_seguro(d.get("ntp") or "pool.ntp.org", "Servidor de hora", 100, sin_espacios=True)
    f.poner("time_zone", zona)
    f.poner("sNTP", ntp)
    f.poner("setMode", "1")
    f.poner("enableDaylight", bool(d.get("verano")))
    on = bool(d.get("verano"))
    for n in ("fromMonth", "fromDay", "toMonth", "toDay"):
        f.habilitar(n, on)
    f.poner("submitStatus", "1")
    cli.enviar(f)
    return {"mensaje": "Fecha y hora guardadas"}


def descargar_respaldo(cli: ClienteRV082) -> tuple[bytes, str]:
    viejo = cli.tiempo_espera
    cli.tiempo_espera = 90
    try:
        contenido = cli._pedir("RV082.exp", [("page", "sys_setting2.htm"), ("typeSubmit", "2"), ("Submit2", "Export")], binario=True)
    finally:
        cli.tiempo_espera = viejo
    if contenido[:200].lstrip().lower().startswith(b"<html") or len(contenido) < 64:
        raise ErrorRouter("El router no devolvió un archivo de respaldo válido")
    return contenido, time.strftime("RV082-respaldo-%Y%m%d-%H%M.exp")


def reiniciar(cli: ClienteRV082, d: dict) -> dict:
    if not d.get("confirmo"):
        raise ErrorValidacion("Falta confirmar el reinicio")
    f = cli.formulario("sys_restart.htm", "formRestart")
    # el navegador NO envía restartBackup (en el DOM real queda fuera del form)
    f.quitar("restartBackup")
    try:
        cli.enviar(f, respaldo=False)
    except ErrorRouter:
        pass  # el router corta la conexión al reiniciar
    return {"mensaje": "El router se está reiniciando (tarda alrededor de 1 minuto)"}


# ============================================================================
# Tabla de acciones para la API
# ============================================================================
ACCIONES = {
    ("GET", "estado"): estado,
    ("GET", "puerto"): puerto_detalle,
    ("GET", "internet"): leer_internet, ("POST", "internet"): guardar_internet,
    ("GET", "lan"): leer_lan, ("POST", "lan"): guardar_lan,
    ("GET", "dhcp"): leer_dhcp, ("POST", "dhcp"): guardar_dhcp,
    ("GET", "clientes"): clientes_dhcp,
    ("GET", "puertos"): leer_puertos, ("POST", "puertos"): guardar_puertos,
    ("POST", "ping"): ping, ("POST", "dns"): dns,
    ("GET", "registro"): registro,
    ("POST", "clave"): cambiar_clave,
    ("GET", "hora"): leer_hora, ("POST", "hora"): guardar_hora,
    ("POST", "reiniciar"): reiniciar,
}
if _seg is not None:
    ACCIONES.update(_seg.ACCIONES)
from . import ancho as _ancho  # noqa: E402
ACCIONES.update(_ancho.ACCIONES)
