import sys
from playwright.sync_api import sync_playwright
SECC = ["inicio","internet","lan","dhcp","reenvio","dmz","seguridad","reglas","filtro","ancho","puertos","herramientas","sistema","vpn"]
errores=[]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1280,"height":860})
    pg.on("console", lambda m: errores.append(f"[{m.type}] {m.text}") if m.type in ("error","warning") else None)
    pg.on("pageerror", lambda e: errores.append(f"[pageerror] {e}"))
    pg.on("dialog", lambda d: d.dismiss())
    pg.goto("http://127.0.0.1:8097/", wait_until="networkidle"); pg.wait_for_timeout(2500)
    for s in SECC:
        pg.click(f'#menu a[data-s="{s}"]')
        pg.wait_for_function("!document.querySelector('#contenido .cargando')", timeout=60000)
        pg.wait_for_timeout(400)
        pg.screenshot(path=f"capturas/x86_{s}.png", full_page=True)
        aviso = pg.query_selector("#contenido .aviso.rojo")
        print(f"{s:13} OK" + (f"  AVISO: {aviso.inner_text()[:120]}" if aviso else ""))
    pg.click('#menu a[data-s="vpn"]'); pg.wait_for_timeout(500); pg.click("#vAyuda"); pg.wait_for_timeout(400)
    pg.screenshot(path="capturas/x86_vpn_guia.png"); 
    pg.set_viewport_size({"width":420,"height":860}); pg.keyboard.press("Escape"); pg.click('#menu a[data-s="inicio"]'); pg.wait_for_timeout(2500)
    pg.screenshot(path="capturas/x86_movil_inicio.png", full_page=True)
    b.close()
print("errores consola:", errores or "ninguno")
