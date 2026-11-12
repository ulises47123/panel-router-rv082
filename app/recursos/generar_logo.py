"""Genera logo.png / logo.ico (y vista previa) a partir de logo.svg."""
import os
from playwright.sync_api import sync_playwright
from PIL import Image
AQUI = os.path.dirname(os.path.abspath(__file__))
svg = open(os.path.join(AQUI, "logo.svg"), encoding="utf-8").read()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=1)
    grande = svg.replace('width="256" height="256"', 'width="512" height="512"')
    pg.set_content("<html><body style='margin:0;background:transparent'>" + grande + "</body></html>")
    pg.locator("svg").screenshot(path=os.path.join(AQUI, "logo-512.png"), omit_background=True)
    b.close()
img = Image.open(os.path.join(AQUI, "logo-512.png")).convert("RGBA")
img.resize((256, 256), Image.LANCZOS).save(os.path.join(AQUI, "logo.png"))
tamanos = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save(os.path.join(AQUI, "logo.ico"), sizes=tamanos)
# vista previa de los tamaños chicos sobre fondo claro y oscuro
prev = Image.new("RGBA", (520, 150), (240, 243, 248, 255))
x = 10
for t in (16, 24, 32, 48, 64, 128):
    ic = img.resize((t, t), Image.LANCZOS)
    prev.alpha_composite(ic, (x, 10)); 
    osc = Image.new("RGBA", (t, t), (21, 32, 51, 255)); osc.alpha_composite(ic)
    prev.alpha_composite(osc, (x, 10 + 128 - t if t < 128 else 10))
    x += t + 14
prev.save(os.path.join(AQUI, "vista-previa.png"))
print("ok", os.path.getsize(os.path.join(AQUI, "logo.ico")), "bytes ico")
