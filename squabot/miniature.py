"""Miniature 1280x720 : deux images côte à côte, un titre court en haut, un tampon."""
from PIL import Image, ImageDraw, ImageOps
from .rendu import police, hexa, ajuste


def fabriquer(sortie, gauche, droite, titre, tampon, couleurs):
    W, H = 1280, 720
    fond, accent, orr = hexa(couleurs["fond"]), hexa(couleurs["accent"]), hexa(couleurs["or"])
    im = Image.new("RGB", (W, H), fond)
    imgs = [p for p in (gauche, droite) if p]
    if len(imgs) == 1:
        im.paste(ImageOps.fit(Image.open(imgs[0]).convert("RGB"), (W, H - 112), centering=(0.5, 0.3)), (0, 112))
    else:
        for i, p in enumerate(imgs[:2]):
            im.paste(ImageOps.fit(Image.open(p).convert("RGB"), (640, H - 112), centering=(0.5, 0.3)), (i * 640, 112))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 112), fill=fond)
    if len(imgs) > 1: d.line((640, 112, 640, H), fill=fond, width=10)
    d.text((W / 2, 58), titre.upper(), font=ajuste(titre.upper(), "noir", 82, 1200), fill=orr, anchor="mm")
    if tampon:
        f = ajuste(tampon.upper(), "noir", 140, 520)
        tw = int(f.getlength(tampon.upper())) + 80
        st = Image.new("RGBA", (tw, 190), (0, 0, 0, 0)); s = ImageDraw.Draw(st)
        s.rounded_rectangle((8, 8, tw - 8, 182), 16, outline=accent + (255,), width=12)
        s.text((tw / 2, 98), tampon.upper(), font=f, fill=accent + (255,), anchor="mm")
        st = st.rotate(-12, expand=True, resample=Image.BICUBIC)
        im.paste(st, (W - st.width - 40, H - st.height - 30), st)
    im.save(sortie, quality=92)
