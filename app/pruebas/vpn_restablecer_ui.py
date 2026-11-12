"""Muestra la pantalla de 'Recuperar el acceso' (sin tocar Restablecer)."""
import sys, os, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import servidor
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
servidor.PUERTO = 8096
srv = ThreadingHTTPServer(("127.0.0.1", 8096), servidor.Manejador)
threading.Thread(target=srv.serve_forever, daemon=True).start()
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1280, "height": 900})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://127.0.0.1:8096/"); pg.wait_for_timeout(2000)
        pg.click('#menu a[data-s="vpn"]'); pg.wait_for_function("!document.querySelector('#contenido .cargando')", timeout=90000); pg.wait_for_timeout(800)
        pg.screenshot(path="pruebas/capturas/vpn_recuperar.png", full_page=True)
        print("título:", pg.inner_text("#contenido .tarjeta h2").split("\n")[0], "| botón Restablecer:", pg.is_visible("#vRestab"), "| errores JS:", errs or "ninguno")
        b.close()
finally:
    srv.shutdown()
