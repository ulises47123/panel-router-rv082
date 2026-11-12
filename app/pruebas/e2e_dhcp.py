from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1280,"height":900})
    pg.on("dialog", lambda d: d.accept())
    pg.goto("http://127.0.0.1:8095/"); pg.wait_for_timeout(2000)
    pg.click('#menu a[data-s="dhcp"]'); pg.wait_for_selector("#rAdd", timeout=60000)
    pg.fill("#rNom","pruebaUI"); pg.fill("#rIp","192.168.1.61"); pg.fill("#rMac","AA:BB:CC:00:11:33"); pg.click("#rAdd")
    pg.click("#dGuardar"); pg.wait_for_selector("#rAdd", timeout=60000); pg.wait_for_timeout(1500)
    filas=pg.inner_text("#dRes"); print("tras guardar:", filas.replace("\n"," | "))
    pg.screenshot(path="capturas/e2e_dhcp.png", full_page=True)
    pg.click("[data-q='0']"); pg.click("#dGuardar"); pg.wait_for_selector("#rAdd", timeout=60000); pg.wait_for_timeout(1500)
    print("tras quitar:", pg.inner_text("#dRes").replace("\n"," | "))
    t=[e.inner_text() for e in pg.query_selector_all("#toast div")]; print("mensajes:", t)
    b.close()
