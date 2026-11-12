from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1280,"height":900})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8096/"); pg.wait_for_timeout(2000)
    pg.click('#menu a[data-s="vpn"]'); pg.wait_for_function("!document.querySelector('#contenido .cargando')", timeout=90000); pg.wait_for_timeout(1500)
    pg.screenshot(path="capturas/vpn_guia_paso2.png", full_page=True)
    print("botón instalar habilitado:", pg.is_enabled("#vInst"))
    pg.click("#vInst"); pg.wait_for_timeout(600)
    print("modal visible:", pg.is_visible("#modal.ver"), "| botón Entendido:", pg.is_visible("#vInstOk"))
    pg.screenshot(path="capturas/vpn_guia_modal.png")
    pg.click("text=Todavía no"); pg.wait_for_timeout(300)
    print("modal cerrado con 'Todavía no':", not pg.is_visible("#modal.ver"), "| errores JS:", errs or "ninguno")
    b.close()
