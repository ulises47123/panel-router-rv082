"""Valida que el programa genere el MISMO POST que el navegador real.
Nada llega al router: el navegador se intercepta y el programa corre en simulacro."""
import sys, os
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI); sys.path.insert(0, os.path.dirname(AQUI))
from banco_post import capturar_post, comparar
from rv082.cliente import ClienteRV082
from rv082 import funciones as fn
from rv082 import seguridad as sg
from rv082 import ancho as an


class Simulacro(ClienteRV082):
    """Cliente que lee del router de verdad pero NO envía ningún POST."""
    def __init__(self):
        super().__init__()
        self.enviados = []

    def _pedir(self, ruta, datos=None, binario=False):
        if datos is not None:
            self.enviados.append((ruta, list(datos)))
            pagina = ruta.split("#")[0]
            return super()._pedir(pagina if pagina.endswith(".htm") else "home.htm")  # respuesta = la página actual
        return super()._pedir(ruta, None, binario)


CASOS = [
    # (nombre, pagina navegador, js navegador, funcion programa, datos)
    ("Red: guardar sin cambios", "network.htm", "chSubmit(document.formNetwork);",
     fn.guardar_lan, {"ip": "192.168.1.1", "mascara": "0", "nombre": "TP-VPN", "dominio": "soporte.com"}),
    ("Red: nombre y dominio", "network.htm",
     "var F=document.formNetwork; F.hostname.value='OFICINA'; F.DomainName.value='empresa.local'; chSubmit(F);",
     fn.guardar_lan, {"ip": "192.168.1.1", "mascara": "0", "nombre": "OFICINA", "dominio": "empresa.local"}),
    ("Internet: DNS manual + MTU 1492", "network.htm",
     "var F=document.formNetwork; F.setWan1DNS.click(); F.Wan1DnsA1.value=8;F.Wan1DnsA2.value=8;F.Wan1DnsA3.value=8;F.Wan1DnsA4.value=8;"
     "F.Wan1DnsB1.value=1;F.Wan1DnsB2.value=1;F.Wan1DnsB3.value=1;F.Wan1DnsB4.value=1; F.mtu_auto1[1].click(); F.bytesMTU1.value=1492; chSubmit(F);",
     fn.guardar_internet, {"tipo": "dhcp", "dns_manual": True, "dns1": "8.8.8.8", "dns2": "1.1.1.1", "mtu_auto": False, "mtu": 1492}),
    ("Internet: DHCP sin cambios", "network.htm", "chSubmit(document.formNetwork);",
     fn.guardar_internet, {"tipo": "dhcp", "dns_manual": False, "mtu_auto": True}),
    ("DHCP: sin cambios", "dhcp_setup.htm", "chSubmit(document.formDHCPSetup);",
     fn.guardar_dhcp, {"activo": True, "desde": 100, "hasta": 149, "minutos": 1440, "dns1": "", "dns2": "", "reservas": []}),
    ("DHCP: lease, rango, DNS y 2 reservas", "dhcp_setup.htm",
     "var F=document.formDHCPSetup; F.clTime.value=720; F.de4.value=199;"
     "F.LanDnsA1.value=192;F.LanDnsA2.value=168;F.LanDnsA3.value=1;F.LanDnsA4.value=1;F.LanDnsB1.value=8;F.LanDnsB2.value=8;F.LanDnsB3.value=8;F.LanDnsB4.value=8;"
     "F.ss1.value=192;F.ss2.value=168;F.ss3.value=1;F.ss4.value=50; F.sMAC1.value='aa';F.sMAC2.value='bb';F.sMAC3.value='cc';F.sMAC4.value='dd';F.sMAC5.value='ee';F.sMAC6.value='0f'; F.userName.value='pc1'; F.dhcpEnable.checked=true; F.btnAddToList.click();"
     "F.ss1.value=192;F.ss2.value=168;F.ss3.value=1;F.ss4.value=40; F.sMAC1.value='11';F.sMAC2.value='22';F.sMAC3.value='33';F.sMAC4.value='44';F.sMAC5.value='55';F.sMAC6.value='66'; F.userName.value='tele'; F.dhcpEnable.checked=false; F.btnAddToList.click();"
     "chSubmit(F);",
     fn.guardar_dhcp, {"activo": True, "desde": 100, "hasta": 199, "minutos": 720, "dns1": "192.168.1.1", "dns2": "8.8.8.8",
                       "reservas": [{"ip": "192.168.1.50", "mac": "aa-bb-cc-dd-ee-0f", "nombre": "pc1", "activa": True},
                                    {"ip": "192.168.1.40", "mac": "11-22-33-44-55-66", "nombre": "tele", "activa": False}]}),
    ("Puertos: sin cambios", "lan_setting.htm", "chSubmit();",
     fn.guardar_puertos, {"puertos": [{"n": n, "activo": True, "prioridad_alta": False} for n in range(1, 9)]}),
    ("Puertos: apagar 3, prioridad alta 2", "lan_setting.htm",
     "var F=document.formlan_setting; F.portDisable3.click(); F.port2Priority.value='1'; chSubmit();",
     fn.guardar_puertos, {"puertos": [{"n": n, "activo": n != 3, "prioridad_alta": n == 2} for n in range(1, 9)]}),
    ("Hora: Buenos Aires + NTP", "time1.htm",
     "var F=document.formTime; F.time_zone.value='20'; F.sNTP.value='pool.ntp.org'; chSubmit(F);",
     fn.guardar_hora, {"zona": "20", "ntp": "pool.ntp.org", "verano": False}),
    ("Reinicio (interceptado)", "sys_restart.htm", "chSubmit(document.formRestart);",
     fn.reiniciar, {"confirmo": True}),
    ("Ping (interceptado)", "sys_diag.htm",
     "var F=document.formsys_diag; F.pingAddr.value='192.168.1.250'; typeSubmit('2',F);",
     fn.ping, {"destino": "192.168.1.250"}),
("Reenvío: HTTP Secondary -> .50", "adv_forwarding.htm",
     "var F=document.formForwarding; F.V_protocol.value='16777220'; F.V_ip4.value='50'; F.V_valid.checked=true; F.addPortRangeApplication.click(); chSubmit(F);",
     sg.agregar_reenvio, {"ip": "192.168.1.50", "servicio_id": "16777220"}),
    ("Reenvío: puerto 8080 TCP (servicio existente)", "adv_forwarding.htm",
     "var F=document.formForwarding; F.V_protocol.value='16777220'; F.V_ip4.value='50'; F.V_valid.checked=true; F.addPortRangeApplication.click(); chSubmit(F);",
     sg.agregar_reenvio, {"ip": "192.168.1.50", "proto": "TCP", "desde": 8080, "nombre": "web"}),
    ("Crear servicio SoftEther TCP 5555", "service0.htm",
     "window.opener={closeService:function(){}}; var F=document.formservice; F.V_name.value='SoftEther'; F.V_protocol.value='6'; F.V_portS.value='5555'; F.V_portE.value='5555'; addtoList(); chSubmit(F);",
     lambda c, d: sg._crear_servicio(c, "SoftEther", "TCP", 5555, 5555), {}),
    ("UPnP: activar", "adv_upnp.htm",
     "var F=document.formUpnp; document.querySelector('input[name=UPnP_Work][value=\"1\"]').click(); chSubmit(F);",
     sg.guardar_upnp, {"activo": True}),
    ("DMZ: .50", "adv_dmz.htm", "var F=document.formDMZ; F.dmzAddr4.value='50'; chSubmit(F);",
     sg.guardar_dmz, {"activo": True, "ip": "192.168.1.50"}),
    ("Firewall: sin cambios", "f_general.htm", "chSubmit(document.formf_general);",
     sg.guardar_firewall, {"spi": True, "dos": True, "bloquear_wan": True}),
    ("Firewall: SPI off, Java+Cookies", "f_general.htm",
     "var F=document.formf_general; document.querySelector('input[name=spi][value=\"0\"]').click(); F.blockJava.click(); F.blockCookies.click(); chSubmit(F);",
     sg.guardar_firewall, {"spi": False, "dos": True, "bloquear_wan": True, "java": True, "cookies": True}),
    ("Regla: bloquear .60 siempre", "edit_access_rules.htm",
     "var F=document.formedit_access_rules; F.ruleAction.value='2'; F.srcipAddrb1.value='192';F.srcipAddrb2.value='168';F.srcipAddrb3.value='1';F.srcipAddrb4.value='60'; F.rDest.value='1'; chSubmit();",
     sg.agregar_regla, {"accion": "bloquear", "servicio": "16777216", "origen_tipo": "una", "origen_desde": "192.168.1.60", "destino_tipo": "cualquiera"}),
    ("Regla: bloquear HTTP .60 L-V 08-17", "edit_access_rules.htm",
     "var F=document.formedit_access_rules; F.ruleAction.value='2'; F.addRule_serviceID.value='16777219'; F.srcipAddrb1.value='192';F.srcipAddrb2.value='168';F.srcipAddrb3.value='1';F.srcipAddrb4.value='60'; F.rDest.value='1';"
     "F.addRule_timeConstraint.value='1'; if(F.addRule_timeConstraint.onchange) F.addRule_timeConstraint.onchange();"
     "F.addRule_timeBeginHour.value='08';F.addRule_timeBeginMin.value='00';F.addRule_timeEndHour.value='17';F.addRule_timeEndMin.value='00';"
     "document.querySelectorAll('input[name=days]').forEach(function(c){ if(['1','2','3','4','5'].indexOf(c.value)>=0 && !c.checked) c.click(); }); chSubmit();",
     sg.agregar_regla, {"accion": "bloquear", "servicio": "16777219", "origen_tipo": "una", "origen_desde": "192.168.1.60", "destino_tipo": "cualquiera",
                        "horario": True, "desde_hora": "08:00", "hasta_hora": "17:00", "dias": [1, 2, 3, 4, 5]}),
    ("Filtro: paso A activar dominios", "content_filter.htm",
     "var F=document.formcontent_filter1; F.forbiddenEnable.click();",
     sg.guardar_filtro, {"dominios_activo": True, "dominios": ["tiktok.com"]}),
    ("QoS: velocidad 1000/4000", "qos.htm",
     "var F=document.formQOS; F.ibwuWAN1.value='1000'; F.ibwWAN1.value='4000'; chSubmit(F);",
     an.guardar_velocidad, {"subida": 1000, "bajada": 4000}),
    ("QoS: HTTP .10-.20 subida max 256", "qos.htm",
     "var F=document.formQOS; F.RC_protocol.value='16777219'; F.IPbegin.value='10'; F.IPend.value='20'; F.RC_link.value='2'; F.Percent.value=''; F.Maxrate.value='256'; F.RC_valid.checked=true;"
     "document.querySelectorAll('input[name=wanEnable]')[0].checked=true; F.addRate.click(); chSubmit(F);",
     an.agregar_ancho, {"servicio": "16777219", "equipos_tipo": "rango", "desde": "192.168.1.10", "hasta": "192.168.1.20", "direccion": "subida", "maximo": 256}),
    ("QoS: todo .60 ambas min 100 max 500", "qos.htm",
     "var F=document.formQOS; var w=function(){document.querySelectorAll('input[name=wanEnable]')[0].checked=true;};"
     "F.RC_protocol.value='16777216'; F.IPbegin.value='60'; F.IPend.value='60'; F.RC_link.value='2'; F.Percent.value='100'; F.Maxrate.value='500'; F.RC_valid.checked=true; w(); F.addRate.click();"
     "F.RC_protocol.value='16777216'; F.IPbegin.value='60'; F.IPend.value='60'; F.RC_link.value='1'; F.Percent.value='100'; F.Maxrate.value='500'; F.RC_valid.checked=true; w(); F.addRate.click(); chSubmit(F);",
     an.agregar_ancho, {"servicio": "16777216", "equipos_tipo": "una", "desde": "192.168.1.60", "direccion": "ambas", "minimo": 100, "maximo": 500}),
]

if __name__ == "__main__":
    solo = sys.argv[1:]
    ok = mal = 0
    for nombre, pagina, js, funcion, datos in CASOS:
        if solo and not any(s.lower() in nombre.lower() for s in solo):
            continue
        nav, msgs = capturar_post(pagina, js)
        cli = Simulacro()
        try:
            funcion(cli, datos)
        except Exception as e:
            if not ('paso A' in nombre and cli.enviados):
              print(f"[ERROR] {nombre}: programa lanzó {type(e).__name__}: {e}"); mal += 1; continue
        if nav is None:
            print(f"[??] {nombre}: el navegador no envió nada. Mensajes: {msgs}"); mal += 1; continue
        mio = (cli.enviados[0][1] if 'paso A' in nombre or 'Crear servicio' in nombre else cli.enviados[-1][1]) if cli.enviados else []
        if os.environ.get("VER"):
            print("   NAV:", nav); print("   MIO:", mio)
        difs = comparar(nav, mio)
        orden_ok = [n for n, _ in nav] == [n for n, _ in mio]
        if not difs:
            ok += 1
            print(f"[OK] {nombre}  ({len(nav)} campos{'' if orden_ok else ', orden distinto'})")
        else:
            mal += 1
            print(f"[DIF] {nombre}:")
            for n, a, b in difs:
                print(f"      {n}: navegador={a}  programa={b}")
        if msgs:
            print("      avisos del navegador:", msgs)
    print(f"\nResultado: {ok} iguales, {mal} con diferencias")
