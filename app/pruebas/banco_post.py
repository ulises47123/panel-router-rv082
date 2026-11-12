"""Banco de pruebas: obtiene el POST EXACTO que enviaría el navegador real
sin enviarlo (la petición se intercepta y se cancela), para compararlo con el
POST que genera el programa. No modifica el router.

Uso desde Python:
    from banco_post import capturar_post
    cuerpo = capturar_post("f_general.htm", "document.formf_general.dos[1].click(); <guardar>")
"""
from __future__ import annotations

import urllib.parse
from playwright.sync_api import sync_playwright

BASE = "http://192.168.1.1/"


def capturar_post(pagina: str, acciones_js: str, usuario="admin", clave="admin", espera_ms=4000):
    """Abre la página, ejecuta acciones_js y devuelve [(nombre, valor), ...] del POST
    que el navegador intentó enviar (o None si no hubo POST)."""
    capturado = {}
    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(http_credentials={"username": usuario, "password": clave})
        pg = ctx.new_page()
        mensajes = []
        pg.on("dialog", lambda d: (mensajes.append(d.message), d.accept()))

        def interceptar(route, request):
            if request.method == "POST" and "url" not in capturado:
                capturado["url"] = request.url
                capturado["cuerpo"] = request.post_data or ""
                route.abort()  # NO llega al router
            elif request.method == "POST":
                route.abort()
            else:
                route.continue_()

        pg.route("**/*", interceptar)
        pg.goto(BASE + pagina, wait_until="load")
        pg.wait_for_timeout(500)
        try:
            pg.evaluate("() => { " + acciones_js + " }")
        except Exception as e:  # la navegación abortada puede lanzar
            mensajes.append(f"[evaluate] {e}")
        pg.wait_for_timeout(espera_ms if "url" not in capturado else 300)
        nav.close()
    if "url" not in capturado:
        return None, mensajes
    pares = urllib.parse.parse_qsl(capturado["cuerpo"], keep_blank_values=True, encoding="iso-8859-1")
    return pares, mensajes


def comparar(esperado, obtenido, ignorar=()):
    """Devuelve lista de diferencias entre dos listas de pares."""
    def multiset(pares):
        d = {}
        for n, v in pares:
            if n in ignorar:
                continue
            d.setdefault(n, []).append(v)
        return d
    a, b = multiset(esperado), multiset(obtenido)
    difs = []
    for n in sorted(set(a) | set(b)):
        if a.get(n) != b.get(n):
            difs.append((n, a.get(n), b.get(n)))
    return difs
