"""Prueba la ventana de 'Restaurar de fábrica' SIN confirmar (no se envía nada al router)."""
import sys, os, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import servidor
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
servidor.PUERTO = 8096
srv = ThreadingHTTPServer(("127.0.0.1", 8096), servidor.Manejador)
threading.Thread(target=srv.serve_forever, daemon=True).start()
llamadas = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1280, "height": 900})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("request", lambda r: llamadas.append(r.url) if "/api/fabrica" in r.url else None)
        pg.goto("http://127.0.0.1:8096/"); pg.wait_for_timeout(2000)
        pg.click('#menu a[data-s="sistema"]'); pg.wait_for_selector("#sFabrica", timeout=60000)
        pg.click("#sFabrica"); pg.wait_for_timeout(400)
        print("botón bloqueado al abrir:", pg.is_disabled("#fabOk"))
        pg.fill("#fabConf", "restaura"); print("con 'restaura' sigue bloqueado:", pg.is_disabled("#fabOk"))
        pg.fill("#fabConf", "restaurar"); print("con 'restaurar' se habilita:", pg.is_enabled("#fabOk"))
        pg.screenshot(path="pruebas/capturas/fabrica_modal.png")
        pg.click("text=Cancelar"); pg.wait_for_timeout(300)
        print("cancelado, modal cerrado:", not pg.is_visible("#modal.ver"), "| llamadas a /api/fabrica:", len(llamadas), "| errores JS:", errs or "ninguno")
        b.close()
finally:
    srv.shutdown()
