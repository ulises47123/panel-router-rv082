from playwright.sync_api import sync_playwright
def esperar(pg):
    # esperar a que la acción termine (botón vuelve a habilitarse) y la sección se vuelva a dibujar
    pg.wait_for_function("!document.querySelector('button[disabled]')", timeout=90000)
    pg.wait_for_timeout(300)
    pg.wait_for_function("!document.querySelector('#contenido .cargando') && document.querySelector('#aAdd')", timeout=90000)
    pg.wait_for_timeout(500)
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1280,"height":900})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.goto("http://127.0.0.1:8095/"); pg.wait_for_timeout(2000)
    pg.click('#menu a[data-s="ancho"]'); esperar(pg)
    pg.fill("#aSub","10000"); pg.fill("#aBaj","50000"); pg.click("#aVel"); esperar(pg)
    pg.select_option("#aEt","una"); pg.fill("#aDes","192.168.1.60"); pg.select_option("#aDir","bajada"); pg.fill("#aMax","2000"); pg.click("#aAdd"); esperar(pg)
    print("tabla:", pg.inner_text("table tbody").replace("\n"," | ").replace("\t"," "))
    pg.screenshot(path="capturas/ancho_e2e.png", full_page=True)
    pg.select_option("#aEt","una"); pg.fill("#aDes","192.168.1.61"); pg.fill("#aMax","99999"); pg.click("#aAdd"); pg.wait_for_timeout(4000)
    print("error esperado:", [t.inner_text() for t in pg.query_selector_all("#toast div.mal")])
    pg.click("[data-adel]"); esperar(pg)
    pg.fill("#aSub","512"); pg.fill("#aBaj","512"); pg.click("#aVel"); esperar(pg)
    print("final:", pg.input_value("#aSub"), pg.input_value("#aBaj"), pg.inner_text("table tbody").strip()[:60], "| errores JS:", errs or "ninguno")
    b.close()
