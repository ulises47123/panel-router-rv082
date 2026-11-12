from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1280,"height":900})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    pg.goto("http://127.0.0.1:8096/"); pg.wait_for_timeout(2500)
    pg.click('#menu a[data-s="vpn"]'); pg.wait_for_function("!document.querySelector('#contenido .cargando')", timeout=90000); pg.wait_for_timeout(800)
    pg.screenshot(path="capturas/vpn_paso1.png", full_page=True)
    print(pg.inner_text("#contenido")[:700])
    pg.click("#vDesc"); 
    for i in range(80):
        pg.wait_for_timeout(2000); t=pg.inner_text("#vProg") if pg.query_selector("#vProg") else ""
        if i%3==0: print("progreso:", t.replace("\n"," "))
        if "verificada" in t or "rror" in t or not pg.query_selector("#vProg"): break
    pg.wait_for_timeout(3000); pg.screenshot(path="capturas/vpn_descarga.png", full_page=True)
    print("final:", pg.inner_text("#contenido")[:500].replace("\n"," | "))
    print("errores JS:", errs or "ninguno")
    b.close()
