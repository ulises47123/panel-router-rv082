"""Reenvío de puertos, UPnP, DMZ, firewall, reglas de acceso y bloqueo de sitios.
Ver investigacion/spec_firewall_reenvio.md (formatos y riesgos)."""
from __future__ import annotations

import re

from .cliente import ClienteRV082, ErrorRouter, Formulario, texto_plano


def _fn():
    from . import funciones  # import tardío (evita ciclo)
    return funciones


# ----------------------------------------------------------------------------
# Servicios (catálogo del router)
# ----------------------------------------------------------------------------
_RX_OPCION = re.compile(r'<option value="([^"]*)">([^<]*)</option>')
_RX_TEXTO_SERV = re.compile(r"^(.*?)\s*\[(TCP&UDP|TCP|UDP|ICMP|ESP|GRE)(?:/(\d+)(?:~(\d+))?)?\]")


def _servicios(menu: str) -> list[dict]:
    """Parsea el hidden service_menu de adv_forwarding/edit_access_rules: value=ID."""
    res = []
    for val, txt in _RX_OPCION.findall(menu or ""):
        m = _RX_TEXTO_SERV.match(txt.strip())
        if not m:
            res.append({"id": val, "nombre": txt.strip(), "proto": "", "ini": 0, "fin": 0, "texto": txt.strip()})
            continue
        ini = int(m.group(3) or 0)
        fin = int(m.group(4) or ini)
        res.append({"id": val, "nombre": m.group(1).strip(), "proto": m.group(2), "ini": ini, "fin": fin, "texto": txt.strip()})
    return res


def _valor_crudo(html: str, nombre: str) -> str | None:
    m = re.search(r"name=\"?" + re.escape(nombre) + r"\"?\s+value='([^']*)'", html)
    return m.group(1) if m else None


def _opciones_lista(f: Formulario, nombre: str) -> list[str] | None:
    """Valores de un <select multiple>. None si la lista no existe (sección apagada)."""
    cs = [c for c in f.controles if c["name"] == nombre and c["tag"] == "select"]
    if not cs:
        return None
    return [o["value"] for o in cs[0]["opciones"]]


def _poner_lista(f: Formulario, nombre: str, valores: list[str]) -> None:
    """Carga la lista completa y la deja como la manda el navegador (invertida, todo seleccionado)."""
    for c in f.controles:
        if c["name"] == nombre and c["tag"] == "select":
            c["opciones"] = [{"value": v, "texto": v, "selected": True} for v in reversed(valores)]
            return
    raise ErrorRouter(f"No se encontró la lista {nombre} en la página")


def _proto_txt(p: str) -> str:
    return {"TCP": "TCP", "UDP": "UDP", "TCP&UDP": "TCP y UDP"}.get(p, p)


# ----------------------------------------------------------------------------
# REENVÍO DE PUERTOS — adv_forwarding.htm (+ service0.htm)
# ----------------------------------------------------------------------------
def _form_reenvio(cli: ClienteRV082):
    html = cli.html("adv_forwarding.htm")
    f = cli.formulario("adv_forwarding.htm", "formForwarding", html=html)
    menu = _valor_crudo(html, "service_menu")
    if menu is None:
        raise ErrorRouter("No se pudo leer el catálogo de servicios del router")
    f.poner("service_menu", menu)          # valor crudo exacto (con & y comillas)
    f.poner("V_protocol", "16777216")      # el select lo arma document.write: opción 0
    f.poner("V_ip4", "")
    f.poner("V_valid", False)
    f.poner("submitStatus", "1")
    reenvios = _opciones_lista(f, "PortRangeList")
    triggers = _opciones_lista(f, "PortTriggerList")
    if reenvios is None or triggers is None:
        raise ErrorRouter("No se pudo leer la lista de reenvíos: no se guarda nada para no borrarla")
    return f, _servicios(menu), reenvios, triggers


def leer_reenvio(cli: ClienteRV082, _d=None) -> dict:
    f, servicios, reenvios, _ = _form_reenvio(cli)
    por_id = {s["id"]: s for s in servicios}
    red = ".".join(f.valor(f"lanIP{i}", "") for i in (1, 2, 3))
    lista = []
    for v in reenvios:
        m = re.match(r"(-?\d+)\{(\d+);([01])\}", v)
        if not m:
            continue
        s = por_id.get(m.group(1), {"nombre": f"Servicio {m.group(1)}", "proto": "", "ini": 0, "fin": 0})
        lista.append({"valor": v, "servicio_id": m.group(1), "nombre": s["nombre"], "proto": _proto_txt(s["proto"]),
                      "puertos": f"{s['ini']}" if s["ini"] == s["fin"] else f"{s['ini']}-{s['fin']}",
                      "ip": f"{red}.{m.group(2)}", "activo": m.group(3) == "1"})
    elegibles = [s for i, s in enumerate(servicios) if s["proto"] in ("TCP", "UDP") or i == 0]
    upnp = leer_upnp(cli)
    return {"reenvios": lista, "servicios": [{"id": s["id"], "texto": f"{s['nombre']} ({_proto_txt(s['proto'])} {s['ini']}{'' if s['ini']==s['fin'] else '-'+str(s['fin'])})"} for s in elegibles if s["id"] != "16777216"],
            "red": red, "upnp": upnp["activo"]}


def _crear_servicio(cli: ClienteRV082, nombre: str, proto: str, ini: int, fin: int) -> None:
    """Crea un servicio nuevo en Service Management (service0.htm), como el navegador."""
    html = cli.html("service0.htm")
    f = cli.formulario("service0.htm", "formservice", html=html)
    menu = _valor_crudo(html, "service_menu")
    if menu is None:
        raise ErrorRouter("No se pudo leer la lista de servicios")
    f.poner("service_menu", menu)
    # lista visible: se saltea la primera opción y solo quedan TCP o UDP puros (así lo hace el JS)
    visibles = []
    for i, (val, txt) in enumerate(_RX_OPCION.findall(menu)):
        if i == 0:
            continue
        m = re.search(r"\[(\w+)/", txt)
        if m and m.group(1) in ("TCP", "UDP"):
            visibles.append(val)
    if len(visibles) >= 100:
        raise _err("El router ya tiene 100 servicios (máximo)")
    codigo = "6" if proto == "TCP" else "17"
    visibles.append(f"{nombre}{{0;{codigo};{ini};{fin};0}}")
    _poner_lista(f, "PortRangeList", visibles)
    f.poner("V_name", ""); f.poner("V_protocol", "6"); f.poner("V_portS", ""); f.poner("V_portE", "")
    cli.enviar(f)


def _es_de_fabrica(servicio_id: str) -> bool:
    """Los de fábrica son 0x01xxxxxx / 0x08xxxxxx; los creados por el usuario
    el router los numera con IDs negativos (ej. -16777215)."""
    n = int(servicio_id)
    return n > 0 and (n >> 24) in (1, 8)


def _borrar_servicio(cli: ClienteRV082, servicio_id: str) -> None:
    """Quita un servicio creado por el usuario (no se pueden borrar los de fábrica)."""
    if _es_de_fabrica(servicio_id):
        raise _err("Los servicios de fábrica no se pueden borrar")
    html = cli.html("service0.htm")
    f = cli.formulario("service0.htm", "formservice", html=html)
    menu = _valor_crudo(html, "service_menu")
    visibles = []
    for i, (val, txt) in enumerate(_RX_OPCION.findall(menu or "")):
        if i == 0:
            continue
        m = re.search(r"\[(\w+)/", txt)
        if m and m.group(1) in ("TCP", "UDP"):
            visibles.append(val)
    nuevos = [v for v in visibles if not re.search(r"\{" + re.escape(servicio_id) + ";", v)]
    if len(nuevos) == len(visibles):
        return
    f.poner("service_menu", menu)
    _poner_lista(f, "PortRangeList", nuevos)
    f.poner("V_name", ""); f.poner("V_protocol", "6"); f.poner("V_portS", ""); f.poner("V_portE", "")
    cli.enviar(f)


def _err(msg):
    return _fn().ErrorValidacion(msg)


def agregar_reenvio(cli: ClienteRV082, d: dict) -> dict:
    fn = _fn()
    ip = fn.ip_valida(d.get("ip"), "IP del equipo")
    proto = d.get("proto", "TCP")
    if proto not in ("TCP", "UDP", "AMBOS"):
        raise _err("Protocolo no válido")
    servicio_id = str(d.get("servicio_id") or "")
    f, servicios, reenvios, triggers = _form_reenvio(cli)
    red = [f.valor(f"lanIP{i}") for i in (1, 2, 3)]
    if ip[:3] != red:
        raise _err(f"La IP debe estar en la red {'.'.join(red)}.x")
    oct4 = int(ip[3])
    if not 1 <= oct4 <= 254:
        raise _err("IP no válida")
    ids_pedidos = []
    if servicio_id:
        if servicio_id not in {s["id"] for s in servicios}:
            raise _err("Servicio desconocido")
        ids_pedidos = [servicio_id]
    else:
        ini = fn.entero(d.get("desde"), "Puerto", 1, 65535)
        fin = fn.entero(d.get("hasta") or ini, "Puerto final", 1, 65535)
        if ini > fin:
            ini, fin = fin, ini
        nombre = re.sub(r"[^A-Za-z0-9_-]", "", (d.get("nombre") or "").strip())[:11] or f"P{ini}"
        for p in (["TCP", "UDP"] if proto == "AMBOS" else [proto]):
            existente = next((s for s in servicios if s["proto"] == p and s["ini"] == ini and s["fin"] == fin), None)
            if existente is None:
                nom = (nombre if proto != "AMBOS" else (nombre[:9] + ("-T" if p == "TCP" else "-U")))
                if any(s["nombre"] == nom for s in servicios):
                    raise _err(f"Ya existe un servicio llamado {nom}; usá otro nombre")
                _crear_servicio(cli, nom, p, ini, fin)
                f, servicios, reenvios, triggers = _form_reenvio(cli)
                existente = next((s for s in servicios if s["proto"] == p and s["ini"] == ini and s["fin"] == fin), None)
                if existente is None:
                    raise ErrorRouter("El router no creó el servicio nuevo")
            ids_pedidos.append(existente["id"])
    usados = {re.match(r"(-?\d+)\{", v).group(1) for v in reenvios if re.match(r"(-?\d+)\{", v)}
    for sid in ids_pedidos:
        if sid in usados:
            raise _err("Ese servicio/puerto ya está reenviado (el router no permite repetirlo). Borralo primero.")
    if len(reenvios) + len(ids_pedidos) > 30:
        raise _err("Máximo 30 reenvíos")
    nuevos = reenvios + [f"{sid}{{{oct4};1}}" for sid in ids_pedidos]
    _poner_lista(f, "PortRangeList", nuevos)
    _poner_lista(f, "PortTriggerList", triggers)
    cli.enviar(f)
    return {"mensaje": "Puerto abierto"}


def _guardar_lista_reenvio(cli, transformar) -> None:
    f, _, reenvios, triggers = _form_reenvio(cli)
    _poner_lista(f, "PortRangeList", transformar(reenvios))
    _poner_lista(f, "PortTriggerList", triggers)
    cli.enviar(f)


def borrar_reenvio(cli: ClienteRV082, d: dict) -> dict:
    valor = d.get("valor")
    def t(lista):
        if valor not in lista:
            raise _err("Ese reenvío ya no existe (recargá la página)")
        return [v for v in lista if v != valor]
    _guardar_lista_reenvio(cli, t)
    sid = re.match(r"(-?\d+)\{", valor or "")
    if sid and not _es_de_fabrica(sid.group(1)):
        try:
            _borrar_servicio(cli, sid.group(1))  # servicio creado por el panel y ya sin uso
        except Exception:
            pass
    return {"mensaje": "Reenvío borrado"}


def activar_reenvio(cli: ClienteRV082, d: dict) -> dict:
    valor, activo = d.get("valor"), bool(d.get("activo"))
    def t(lista):
        if valor not in lista:
            raise _err("Ese reenvío ya no existe (recargá la página)")
        return [re.sub(r";[01]\}$", f";{1 if activo else 0}}}", v) if v == valor else v for v in lista]
    _guardar_lista_reenvio(cli, t)
    return {"mensaje": "Reenvío " + ("activado" if activo else "desactivado")}


# ----------------------------------------------------------------------------
# UPnP — adv_upnp.htm
# ----------------------------------------------------------------------------
def _form_upnp(cli):
    html = cli.html("adv_upnp.htm")
    f = cli.formulario("adv_upnp.htm", "formUpnp", html=html)
    menu = _valor_crudo(html, "service_menu")
    if menu is not None:
        f.poner("service_menu", menu)
    f.poner("V2_protocol", "16777217")  # primera opción que arma document.write
    f.poner("V2_ip4", "")
    f.poner("V2_valid", False)
    f.poner("submitStatus", "1")
    lista = _opciones_lista(f, "UPnPList")
    if lista is None:
        raise ErrorRouter("No se pudo leer la lista UPnP")
    return f, lista


def leer_upnp(cli: ClienteRV082, _d=None) -> dict:
    f, _ = _form_upnp(cli)
    return {"activo": f.valor("UPnP_Work") == "1"}


def guardar_upnp(cli: ClienteRV082, d: dict) -> dict:
    f, lista = _form_upnp(cli)
    f.poner("UPnP_Work", "1" if d.get("activo") else "0")
    _poner_lista(f, "UPnPList", lista)
    cli.enviar(f)
    return {"mensaje": "UPnP " + ("activado" if d.get("activo") else "desactivado")}


# ----------------------------------------------------------------------------
# DMZ host — adv_dmz.htm
# ----------------------------------------------------------------------------
def leer_dmz(cli: ClienteRV082, _d=None) -> dict:
    f = cli.formulario("adv_dmz.htm", "formDMZ")
    red = ".".join(f.valor(f"dmzAddr{i}", "") for i in (1, 2, 3))
    o4 = f.valor("dmzAddr4", "0") or "0"
    return {"activo": o4 != "0", "ip": f"{red}.{o4}" if o4 != "0" else "", "red": red}


def guardar_dmz(cli: ClienteRV082, d: dict) -> dict:
    fn = _fn()
    f = cli.formulario("adv_dmz.htm", "formDMZ")
    red = [f.valor(f"dmzAddr{i}") for i in (1, 2, 3)]
    if d.get("activo"):
        ip = fn.ip_valida(d.get("ip"), "IP del equipo")
        if ip[:3] != red:
            raise _err(f"La IP debe estar en la red {'.'.join(red)}.x")
        o4 = fn.entero(ip[3], "IP", 1, 254)
    else:
        o4 = 0
    f.poner("dmzAddr4", str(o4))
    f.poner("submitStatus", "1")
    cli.enviar(f)
    return {"mensaje": "DMZ " + ("activado" if o4 else "desactivado")}


# ----------------------------------------------------------------------------
# FIREWALL general — f_general.htm
# ----------------------------------------------------------------------------
_BLOQUEOS = ("blockJava", "blockCookies", "blockActiveX", "blockProxy")


def _fix_firewall(f: Formulario) -> Formulario:
    fw = f.valor("firewall") == "1"
    rm = f.valor("remoteMng") == "1"
    f.habilitar("rmPort", fw and rm)
    algun_bloqueo = any(any(c.get("checked") for c in f.controles if c["name"] == b) for b in _BLOQUEOS)
    tiene_lista = f.tiene("local_forbiddenURLs_del")
    f.poner("noblockTrusted", tiene_lista)
    f.habilitar("noblockTrusted", algun_bloqueo)
    if tiene_lista:
        for c in f.controles:
            if c["name"] == "local_forbiddenURLs_del":
                c["opciones"].reverse()
                for o in c["opciones"]:
                    o["selected"] = True
    f.poner("submitStatus", "1")
    return f


def leer_firewall(cli: ClienteRV082, _d=None) -> dict:
    f = cli.formulario("f_general.htm", "formf_general")
    marcado = lambda n: any(c.get("checked") for c in f.controles if c["name"] == n)
    return {"firewall": f.valor("firewall") == "1", "spi": f.valor("spi") == "1", "dos": f.valor("dos") == "1",
            "bloquear_wan": f.valor("blockWANReq") == "1", "admin_remota": f.valor("remoteMng") == "1",
            "puerto_remoto": next((c["value"] for c in f.controles if c["name"] == "rmPort"), "80"),
            "multicast": f.valor("passMulti") == "1",
            "java": marcado("blockJava"), "cookies": marcado("blockCookies"),
            "activex": marcado("blockActiveX"), "proxy": marcado("blockProxy"),
            "clave_de_fabrica": f.valor("adPassword") == "admin"}


def guardar_firewall(cli: ClienteRV082, d: dict) -> dict:
    fn = _fn()
    f = cli.formulario("f_general.htm", "formf_general")
    if f.valor("firewall") != "1":
        raise _err("El firewall está apagado en el router; encendelo desde la web original primero")
    clave_fabrica = f.valor("adPassword") == "admin"
    f.poner("spi", "1" if d.get("spi", True) else "0")
    f.poner("dos", "1" if d.get("dos", True) else "0")
    f.poner("blockWANReq", "1" if d.get("bloquear_wan", True) else "0")
    f.poner("passMulti", "1" if d.get("multicast") else "0")
    remota = bool(d.get("admin_remota"))
    if remota and clave_fabrica:
        raise _err("No se puede activar la administración remota con la clave de fábrica. Cambiá la contraseña primero (Sistema).")
    f.poner("remoteMng", "1" if remota else "0")
    if remota:
        f.habilitar("rmPort", True)
        f.poner("rmPort", str(fn.entero(d.get("puerto_remoto", 8443), "Puerto de administración", 1, 65535)))
    for clave, campo in (("java", "blockJava"), ("cookies", "blockCookies"), ("activex", "blockActiveX"), ("proxy", "blockProxy")):
        f.poner(campo, bool(d.get(clave)))
    _fix_firewall(f)
    cli.enviar(f)
    return {"mensaje": "Seguridad guardada"}


# ----------------------------------------------------------------------------
# REGLAS DE ACCESO — access_rules.htm / edit_access_rules.htm
# ----------------------------------------------------------------------------
DIAS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]


def _dias_es(t: str) -> str:
    t = t.strip().rstrip(",")
    if not t:
        return ""
    if "Everyday" in t:
        return "Todos los días"
    tr = {"Sun": "Dom", "Mon": "Lun", "Tue": "Mar", "Wed": "Mié", "Thu": "Jue", "Fri": "Vie", "Sat": "Sáb"}
    return ", ".join(tr.get(x.strip(), x.strip()) for x in t.split(",") if x.strip())


def leer_reglas(cli: ClienteRV082, _d=None) -> dict:
    html = re.sub(r"<!--.*?-->", "", cli.html("access_rules.htm"), flags=re.S)
    m = re.search(r"Source Interface.*?</tr>(.*?)</table>", html, re.S | re.I)
    reglas = []
    if m:
        for fila in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S | re.I):
            celdas = re.findall(r"<td[^>]*>(.*?)</td>", fila, re.S | re.I)
            if len(celdas) < 9:
                continue
            t = [texto_plano(c) for c in celdas]
            borrar = re.search(r"removeLine\('?(\d+)'?\)", fila)
            prio = re.search(r"<option[^>]*selected[^>]*>\s*(\d+)", celdas[0]) or re.search(r"(\d+)", t[0])
            habil = re.search(r"enableLine\(this,\s*'?(\d+)'?\)", fila)
            reglas.append({
                "prioridad": prio.group(1) if prio else "",
                "activa": "checked" in celdas[1].lower(),
                "accion": {"Allow": "Permitir", "Deny": "Bloquear"}.get(t[2], t[2]),
                "servicio": re.sub(r"\s*\[\d+\]$", "", t[3]),
                "interfaz": t[4], "origen": t[5].replace("Any", "Cualquiera"), "destino": t[6].replace("Any", "Cualquiera"),
                "horario": re.sub(r"(^|\s)0(\d\d:)", lambda m: m.group(1) + m.group(2), t[7].replace("Always", "Siempre").replace(" ~ ", " a ")),
                "dias": _dias_es(t[8]),
                "fija": borrar is None, "num": borrar.group(1) if borrar else None,
                "num_estado": habil.group(1) if habil else None})
    f = cli.formulario("access_rules.htm", "formaccess_rules", html=cli.ultimo_html["access_rules.htm"])
    return {"reglas": reglas, "total": f.valor("totalRules", "")}


def servicios_reglas(cli: ClienteRV082, _d=None) -> list:
    html = cli.html("edit_access_rules.htm")
    menu = _valor_crudo(html, "service_menu") or ""
    res = []
    for i, (val, txt) in enumerate(_RX_OPCION.findall(menu)):
        if i == 0 or "0~0" not in txt:
            res.append({"id": val, "texto": txt.replace("All Traffic", "Todo el tráfico")})
    return res


def agregar_regla(cli: ClienteRV082, d: dict) -> dict:
    fn = _fn()
    html = cli.html("edit_access_rules.htm")
    f = cli.formulario("edit_access_rules.htm", "formedit_access_rules", html=html)
    menu = _valor_crudo(html, "service_menu")
    if menu is not None:
        f.poner("service_menu", menu)
    ids = {v for v, _ in _RX_OPCION.findall(menu or "")}
    servicio = str(d.get("servicio", "16777216"))
    if servicio not in ids:
        raise _err("Servicio no válido")
    accion = "2" if d.get("accion") == "bloquear" else "1"
    origen_tipo = d.get("origen_tipo", "una")  # cualquiera | una | rango
    if accion == "2" and origen_tipo == "cualquiera" and servicio == "16777216" and not d.get("confirmo_todo"):
        raise _err("Bloquear TODO el tráfico de cualquier equipo te deja sin internet y sin acceso al router. Elegí un equipo o un rango.")
    f.poner("editRuleNo", "0"); f.poner("submitStatus", "1"); f.poner("afterSubmit", "0")
    f.poner("ruleAction", accion)
    f.poner("addRule_serviceID", servicio)
    # hay dos campos "log": el hidden queda 0 y el select indica si se registra
    logs = [c for c in f.controles if c["name"] == "log"]
    if len(logs) == 2 and logs[1]["tag"] == "select":
        for o in logs[1]["opciones"]:
            o["selected"] = o["value"] == ("1" if d.get("registrar", True) else "0")
    f.poner("addRule_srcEnet", "2")  # LAN
    f.poner("rSour", {"cualquiera": "1", "una": "2", "rango": "3"}.get(origen_tipo, "2"))
    for k in ("srcipAddrb", "srcipAdde", "desipAddrb", "desipAdde"):
        for i in range(1, 5):
            f.poner(f"{k}{i}", "")
    if origen_tipo in ("una", "rango"):
        ip = fn.ip_valida(d.get("origen_desde"), "IP de origen")
        fn._poner_octetos(f, "srcipAddrb", ip)
        if origen_tipo == "rango":
            fn._poner_octetos(f, "srcipAdde", fn.ip_valida(d.get("origen_hasta"), "IP final de origen"))
    destino_tipo = d.get("destino_tipo", "cualquiera")
    f.poner("rDest", {"cualquiera": "1", "una": "2", "rango": "3"}.get(destino_tipo, "1"))
    if destino_tipo in ("una", "rango"):
        fn._poner_octetos(f, "desipAddrb", fn.ip_valida(d.get("destino_desde"), "IP de destino"))
        if destino_tipo == "rango":
            fn._poner_octetos(f, "desipAdde", fn.ip_valida(d.get("destino_hasta"), "IP final de destino"))
    con_horario = bool(d.get("horario"))
    f.poner("addRule_timeConstraint", "1" if con_horario else "0")
    campos_hora = ("addRule_timeBeginHour", "addRule_timeBeginMin", "addRule_timeEndHour", "addRule_timeEndMin")
    for n in campos_hora:
        f.habilitar(n, con_horario)
    dias_pedidos = [str(x) for x in d.get("dias", [])]
    for c in f.controles:
        if c["name"] == "days":
            c["disabled"] = not con_horario
            c["checked"] = False
    if con_horario:
        def hm(txt, nombre):
            m = re.fullmatch(r"(\d{1,2}):(\d{2})", (txt or "").strip())
            if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
                raise _err(f"{nombre}: usá el formato HH:MM (ej. 08:00)")
            return f"{int(m.group(1)):02d}", m.group(2)
        bh, bm = hm(d.get("desde_hora"), "Hora de inicio")
        eh, em = hm(d.get("hasta_hora"), "Hora de fin")
        for n, v in zip(campos_hora, (bh, bm, eh, em)):
            f.poner(n, v)
        todos = not dias_pedidos or set(dias_pedidos) >= {str(i) for i in range(7)}
        for c in f.controles:
            if c["name"] == "days":
                if todos:
                    c["checked"] = c["value"] == "7"
                    c["disabled"] = c["value"] != "7"
                else:
                    c["checked"] = c["value"] in dias_pedidos
    cli.enviar(f)
    return {"mensaje": "Regla agregada"}


def borrar_regla(cli: ClienteRV082, d: dict) -> dict:
    num = str(int(d.get("num")))
    html = cli.html("access_rules.htm")
    if not re.search(r"removeLine\('?" + num + r"'?\)", html):
        raise _err("Esa regla ya no existe (recargá la página)")
    f = cli.formulario("access_rules.htm", "formaccess_rules", html=html)
    f.poner("submitStatus", "6"); f.poner("RemoveLine", num); f.poner("submitClick", "1")
    cli.enviar(f)
    return {"mensaje": "Regla borrada"}


def activar_regla(cli: ClienteRV082, d: dict) -> dict:
    num = str(int(d.get("num")))
    html = cli.html("access_rules.htm")
    if not re.search(r"enableLine\(this,\s*'?" + num + r"'?\)", html):
        raise _err("Esa regla ya no existe (recargá la página)")
    f = cli.formulario("access_rules.htm", "formaccess_rules", html=html)
    f.poner("EnableLine" if d.get("activa") else "DisableLine", num)
    # el navegador cambia la casilla de esa fila antes de enviar
    casillas = [c for c in f.controles if c["name"] == "enablePolicy"]
    filas = [m for m in re.finditer(r"enableLine\(this,\s*'?(\d+)'?\)", re.sub(r"<!--.*?-->", "", html, flags=re.S))]
    for c, m in zip(casillas, filas):
        if m.group(1) == num:
            c["checked"] = bool(d.get("activa"))
    f.poner("submitStatus", "4")
    cli.enviar(f)
    return {"mensaje": "Regla " + ("activada" if d.get("activa") else "desactivada")}


# ----------------------------------------------------------------------------
# BLOQUEO DE SITIOS — content_filter.htm
# ----------------------------------------------------------------------------
def _form_filtro(cli, html=None):
    f = cli.formulario("content_filter.htm", "formcontent_filter1", html=html)
    return f


def leer_filtro(cli: ClienteRV082, _d=None) -> dict:
    f = _form_filtro(cli)
    dominios = _opciones_lista(f, "local_forbiddenURLs_del")
    palabras = _opciones_lista(f, "keywords_list")
    horario = f.valor("rangeSchedule1", "0") == "1"
    dias = [c["value"] for c in f.controles if c["name"] == "days" and c.get("checked")]
    return {"dominios_activo": dominios is not None, "dominios": dominios or [],
            "palabras_activo": palabras is not None, "palabras": palabras or [],
            "horario": horario, "desde": _hhmm(f.valor("TOD_startHour"), f.valor("TOD_startMin")),
            "hasta": _hhmm(f.valor("TOD_endHour"), f.valor("TOD_endMin")), "dias": dias}


def _hhmm(h, m) -> str:
    try:
        return f"{int(h):02d}:{int(m):02d}"
    except (TypeError, ValueError):
        return ""


def guardar_filtro(cli: ClienteRV082, d: dict) -> dict:
    fn = _fn()
    dominios = []
    for x in d.get("dominios", []):
        x = re.sub(r"^https?://", "", (x or "").strip().lower()).split("/")[0]
        if not x:
            continue
        if not re.fullmatch(r"[a-z0-9.-]{1,31}", x):
            raise _err(f"Dominio no válido: {x} (máx. 31 caracteres, sin espacios)")
        if x not in dominios:
            dominios.append(x)
    palabras = []
    for x in d.get("palabras", []):
        x = (x or "").strip().lower()
        if not x:
            continue
        if not re.fullmatch(r"[a-z0-9._-]{1,23}", x):
            raise _err(f"Palabra no válida: {x} (máx. 23 caracteres, sin espacios)")
        if x not in palabras:
            palabras.append(x)
    if len(dominios) > 50 or len(palabras) > 50:
        raise _err("Máximo 50 dominios y 50 palabras")
    dom_on = bool(d.get("dominios_activo"))
    pal_on = bool(d.get("palabras_activo"))

    f = _form_filtro(cli)
    estado_dom = f.tiene("local_forbiddenURLs_del")
    estado_pal = f.tiene("keywords_list")
    if estado_dom != dom_on or estado_pal != pal_on:
        # Paso A (falseSubmit): el router redibuja con las secciones abiertas/cerradas
        f.poner("forbiddenEnable", dom_on)
        f.poner("keywordsEnable", pal_on)
        for n in ("local_forbiddenURLs_del", "keywords_list"):
            for c in f.controles:
                if c["name"] == n:
                    c["opciones"] = []
        f.poner("submitStatus", "0")
        html = cli.enviar(f)
        f = _form_filtro(cli, html=html)
        if f.tiene("local_forbiddenURLs_del") != dom_on or f.tiene("keywords_list") != pal_on:
            f = _form_filtro(cli)
    f.poner("forbiddenEnable", dom_on)
    f.poner("keywordsEnable", pal_on)
    if dom_on:
        f.poner("forbiddenURLs_add", "")
        _poner_lista(f, "local_forbiddenURLs_del", dominios)
    if pal_on:
        f.poner("keywords_add", "")
        _poner_lista(f, "keywords_list", palabras)
    if f.tiene("rangeSchedule1"):
        con_horario = bool(d.get("horario"))
        f.poner("rangeSchedule1", "1" if con_horario else "0")
        campos = ("TOD_startHour", "TOD_startMin", "TOD_endHour", "TOD_endMin")
        for n in campos:
            f.habilitar(n, con_horario)
        for c in f.controles:
            if c["name"] == "days":
                c["disabled"] = not con_horario
                c["checked"] = False
        if con_horario:
            def hm(txt, nombre):
                m = re.fullmatch(r"(\d{1,2}):(\d{2})", (txt or "").strip())
                if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
                    raise _err(f"{nombre}: usá el formato HH:MM")
                return f"{int(m.group(1)):02d}", m.group(2)
            vals = hm(d.get("desde"), "Desde") + hm(d.get("hasta"), "Hasta")
            for n, v in zip(campos, vals):
                f.poner(n, v)
            dias = [str(x) for x in d.get("dias", [])]
            todos = not dias or set(dias) >= {str(i) for i in range(7)}
            for c in f.controles:
                if c["name"] == "days":
                    if todos:
                        c["checked"] = c["value"] == "7"; c["disabled"] = c["value"] != "7"
                    else:
                        c["checked"] = c["value"] in dias
    f.poner("submitStatus", "1")
    cli.enviar(f)
    return {"mensaje": "Bloqueo de sitios guardado"}


ACCIONES = {
    ("GET", "reenvio"): leer_reenvio,
    ("POST", "reenvio/agregar"): agregar_reenvio,
    ("POST", "reenvio/borrar"): borrar_reenvio,
    ("POST", "reenvio/activar"): activar_reenvio,
    ("POST", "upnp"): guardar_upnp,
    ("GET", "dmz"): leer_dmz, ("POST", "dmz"): guardar_dmz,
    ("GET", "firewall"): leer_firewall, ("POST", "firewall"): guardar_firewall,
    ("GET", "reglas"): leer_reglas, ("GET", "reglas/servicios"): servicios_reglas,
    ("POST", "reglas/agregar"): agregar_regla, ("POST", "reglas/borrar"): borrar_regla,
    ("POST", "reglas/activar"): activar_regla,
    ("GET", "filtro"): leer_filtro, ("POST", "filtro"): guardar_filtro,
}
