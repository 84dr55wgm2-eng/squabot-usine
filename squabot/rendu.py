"""Rendu image par image d'une vidéo décrite par ses plans. Chaque image ne dépend que de t."""
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from . import images

W, H, FPS = 1080, 1920, 30
POL = Path(__file__).parent / "polices"
_cache_polices = {}


def police(nom, taille):
    k = (nom, int(taille))
    if k not in _cache_polices:
        _cache_polices[k] = ImageFont.truetype(str(POL / {"noir": "InterDisplay-Black.otf", "serif": "Caladea-Bold.ttf",
                                                           "mono": "JetBrainsMono-Bold.ttf"}[nom]), max(8, int(taille)))
    return _cache_polices[k]


def hexa(c): c = c.lstrip("#"); return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
def ease(x): x = min(1, max(0, x)); return 1 - (1 - x) ** 3
def rebond(x): x = min(1, max(0, x)); c = 1.9; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def texte(d, xy, s, f, couleur, contour=0, ancre="mm"):
    d.text(xy, s, font=f, fill=couleur, anchor=ancre, stroke_width=contour, stroke_fill=(0, 0, 0))


def ajuste(s, nom, taille, largeur=940):
    while police(nom, taille).getlength(s) > largeur and taille > 30: taille -= 4
    return police(nom, taille)


class Rendu:
    def __init__(self, video, mots, assets, theme, duree):
        self.v, self.mots, self.assets, self.duree = video, mots, assets, duree
        c = theme["style_visuel"]["couleurs"]
        self.FOND, self.PAPIER, self.ACCENT, self.OR = (hexa(c[k]) for k in ("fond", "papier", "accent", "or"))
        self.ENCRE = (30, 24, 20)
        self.plans = video["_plans"]                      # plans résolus : debut, fin, index des mots
        self.impacts = [p["_tampon_t"] for p in self.plans if p.get("_tampon_t") is not None]
        self.rng = np.random.default_rng(1)
        self.flous = {}
        self.habillage = self._habillage(video)
        g = [Image.fromarray(self.rng.normal(128, 18, (H // 2, W // 2)).clip(0, 255).astype("uint8")).resize((W, H)) for _ in range(6)]
        self.grain = [Image.merge("RGB", (x, x, x)) for x in g]
        yy, xx = np.mgrid[0:H, 0:W]
        v = 1 - 0.55 * (((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2)
        self.vignette = Image.fromarray((v.clip(0.25, 1) * 255).astype("uint8"))
        self._sous_titres()

    # ---------- habillage propre à chaque vidéo (évite l'effet « même moule ») ----------
    def _habillage(self, v):
        """Tiré au sort à partir de l'identifiant de la vidéo (reproductible) ; `habillage` dans video.json l'emporte."""
        import hashlib
        r = np.random.default_rng(int(hashlib.md5(str(v.get("id", "")).encode()).hexdigest()[:8], 16))
        tr = list(self.TRANSITIONS); r.shuffle(tr)
        h = {"sous_titres_y": int(r.choice([1340, 1440, 1520])), "sous_titres_taille": float(r.choice([0.9, 1.0, 1.08])),
             "sous_titres_style": str(r.choice(["contour", "boite", "contour"])), "mot_cle": str(r.choice(["or", "accent"])),
             "transitions": tr, "grain": float(r.choice([0.04, 0.06, 0.08]))}
        h.update(v.get("habillage") or {})
        return h

    # ---------- éléments ----------
    def tampon(self, im, mot, t0, t, xy, taille=150, angle=-10):
        if t < t0: return
        k = ease((t - t0) / 0.18); sc = 1.8 - 0.8 * k
        f = ajuste(mot, "noir", taille, 820)
        tw, th = int(f.getlength(mot)) + 80, f.size + 70
        lay = Image.new("RGBA", (tw, th), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        d.rounded_rectangle((8, 8, tw - 8, th - 8), 18, outline=self.ACCENT + (255,), width=12)
        d.text((tw / 2, th / 2 + 4), mot, font=f, fill=self.ACCENT + (255,), anchor="mm")
        a = np.array(lay); trous = np.random.default_rng(len(mot)).random(a.shape[:2]) < 0.10
        a[trous, 3] = (a[trous, 3] * 0.3).astype("uint8")
        lay = Image.fromarray(a).rotate(angle, expand=True, resample=Image.BICUBIC)
        lay = lay.resize((max(1, int(lay.width * sc)), max(1, int(lay.height * sc))), Image.BILINEAR)
        lay.putalpha(lay.split()[3].point(lambda v: int(v * min(1, k * 1.4))))
        im.paste(lay, (int(xy[0] - lay.width / 2), int(xy[1] - lay.height / 2)), lay)

    def fiche(self, lignes, visibles, l=900, h=540, marge_droite=0):
        c = Image.new("RGB", (l, h), self.PAPIER)
        n = np.array(c).astype(np.float32); n *= 0.92 + 0.08 * np.random.default_rng(5).random((h, l, 1))
        c = Image.fromarray(n.astype("uint8")); d = ImageDraw.Draw(c)
        d.rectangle((0, 0, l - 1, h - 1), outline=(150, 135, 110), width=4)
        d.line((40, 120, l - 40, 120), fill=self.ACCENT, width=3)
        y = 50
        for i, (s, taille) in enumerate(lignes):
            d.text((44, y), s[:visibles[i]], font=ajuste(s, "mono", taille, l - 90 - (marge_droite if i else 0)), fill=self.ENCRE)
            y += taille + (70 if i == 0 else 28)
        return c

    def sous_plan(self, p, t):
        for sp in p.get("_sous", []):
            if sp["debut"] <= t < sp["fin"]: return sp
        return p["_sous"][-1] if p.get("_sous") else None

    def fond_image(self, im, p, t):
        """Visuel du sous-plan en cours, caméra 2.5D, ambiance. Renvoie False s'il n'y a rien à montrer."""
        sp = self.sous_plan(p, t)
        if sp is None or sp["cle"] not in self.assets:
            return self.fond_flou(im, p, t)
        img, dep, fx, fy = self.assets[sp["cle"]]
        prog = (t - sp["debut"]) / max(0.01, sp["fin"] - sp["debut"])
        if sp["zoom"] > 1: fr = images.camera(img, dep, prog, sp["camera"], fy, fx, sp["zoom"])
        else: fr = images.camera(img, dep, prog, sp["camera"], sp["focus"])
        im.paste(Image.fromarray(images.ambiance(fr, t, poussiere=p.get("poussiere", 1.0))))
        return True

    def fond_flou(self, im, p, t, sombre=150):
        """Fond des plans de texte : un visuel de l'histoire, flou, assombri, qui dérive lentement. Jamais un aplat."""
        cle = p.get("_fond")
        if cle is None or cle not in self.assets:
            im.paste(Image.new("RGB", (W, H), self.FOND)); return False
        if cle not in self.flous:
            img, dep = self.assets[cle][:2]
            import cv2
            self.flous[cle] = (cv2.GaussianBlur(img, (0, 0), 18), dep)
        img, dep = self.flous[cle]
        prog = (t - p["_debut"]) / max(0.01, p["_fin"] - p["_debut"])
        fr = images.ambiance(images.camera(img, dep, prog, "avance"), t, poussiere=1.4, vacillement=0.06)
        im.paste(Image.fromarray(fr))
        im.paste(Image.new("RGB", (W, H), (0, 0, 0)), (0, 0), Image.new("L", (W, H), sombre))
        return True

    def texte_anime(self, d, p, t, y=420):
        """Les mots arrivent un par un : ils tombent légèrement et se posent (rebond), avec un trait qui se trace."""
        mots = p["texte"].split(); t0 = p["_debut"] + 0.08
        f = ajuste(p["texte"], "noir", 170)
        largeurs = [f.getlength(m + " ") for m in mots]; total = sum(largeurs) - f.getlength(" ")
        x = W / 2 - total / 2
        for i, m in enumerate(mots):
            k = (t - t0 - i * 0.09) / 0.32
            if k <= 0: x += largeurs[i]; continue
            dy = (1 - rebond(k)) * -60
            d.text((x, y + dy), m, font=f, fill=self.OR, anchor="lm", stroke_width=8, stroke_fill=(0, 0, 0))
            x += largeurs[i]
        k = ease((t - t0 - len(mots) * 0.09) / 0.4)
        if k > 0: d.line((W / 2 - total / 2, y + f.size * 0.62, W / 2 - total / 2 + total * k, y + f.size * 0.62), fill=self.ACCENT, width=10)

    # ---------- plans ----------
    def plan(self, p, t, im):
        d = ImageDraw.Draw(im); typ = p["type"]; t0 = p["_debut"]
        if typ in ("illustration", "photo"):
            self.fond_image(im, p, t)
        elif typ == "titre":
            self.fond_flou(im, p, t, 115)
            k = ease((t - t0 - 0.05) / 0.35); d = ImageDraw.Draw(im)
            if p.get("petit"): texte(d, (W / 2, 640), p["petit"], police("mono", 64), self.PAPIER)
            texte(d, (W / 2, 900), p["grand"], ajuste(p["grand"], "serif", 380 - 60 * k, 980), self.PAPIER, 4)
            d.line((W / 2 - 300 * k, 1110, W / 2 + 300 * k, 1110), fill=self.ACCENT, width=8)
        elif typ == "fiche":
            self.fond_flou(im, p, t, 105)
            lignes = [(s, 40 if i == 0 else (62 if i == 1 else 44)) for i, s in enumerate(p["lignes"])]
            n = int(max(0, t - t0 - 0.2) * 34); vis = []
            for s, _ in lignes: vis.append(max(0, min(len(s), n))); n -= len(s)
            k = ease((t - t0) / 0.4)
            c = self.fiche(lignes, vis, marge_droite=320 if p.get("_cles") else 0).convert("RGBA")
            if p.get("_cles"):                       # photo d'identité épinglée sur la fiche
                img = self.assets[p["_cles"][0]][0]
                hh, ww = img.shape[:2]; cw = int(min(ww, hh * 0.78)); x0 = (ww - cw) // 2
                ph = Image.fromarray(img[int(hh * 0.05):int(hh * 0.05) + int(cw / 0.78), x0:x0 + cw]).resize((250, 320))
                cadre = Image.new("RGB", (270, 340), (245, 242, 235)); cadre.paste(ph, (10, 10))
                c.paste(cadre.rotate(4, expand=True, fillcolor=self.PAPIER), (c.width - 300, 150))
            c = c.rotate(-3 + 3 * (1 - k), expand=True, resample=Image.BICUBIC)
            im.paste(c, (int(W / 2 - c.width / 2), int(470 + 300 * (1 - k))), c)
        elif typ == "compteur":
            self.fond_flou(im, p, t, 115)
            d = ImageDraw.Draw(im)
            k = ease((t - t0 - 0.2) / max(0.5, (p["_fin"] - t0) * 0.6))
            val = p.get("de", 0) + (p["a_valeur"] - p.get("de", 0)) * k
            s = f"{p.get('prefixe', '')}{int(round(val)):,}".replace(",", " ") + f" {p.get('unite', '')}".rstrip()
            texte(d, (W / 2, 700), s, ajuste(s, "noir", 300), self.PAPIER)
            if p.get("legende") and k > 0.5: texte(d, (W / 2, 930), p["legende"], ajuste(p["legende"], "mono", 50), self.OR)
        # surimpressions communes
        d = ImageDraw.Draw(im)
        if p.get("texte"):
            self.texte_anime(d, p, t)
        if p.get("sous_texte"):
            texte(d, (W / 2, 560), p["sous_texte"], ajuste(p["sous_texte"], "mono", 52), self.PAPIER, 4)
        if p.get("_tampon_t") is not None:
            self.tampon(im, p["tampon"]["texte"].upper(), p["_tampon_t"], t, (W / 2, 1150), 160, p["tampon"].get("angle", -10))

    # ---------- sous-titres ----------
    PETITS = {"le", "la", "les", "de", "des", "du", "d'une", "d'un", "ne", "est", "a", "un", "une", "sa", "son", "ses", "ce",
              "en", "à", "au", "aux", "il", "elle", "qui", "et", "dans", "chez", "sous", "sur", "s'en", "c'est", "plus", "pour", "par", "on"}

    def _sous_titres(self):
        self.groupes, cur = [], []
        for i, m in enumerate(self.mots):
            cur.append(i)
            fin = m["w"][-1] in ".,!?;:"
            petit = m["w"].lower() in self.PETITS
            if fin or (not petit and (len(cur) >= 2 or len(m["w"]) > 8)) or len(cur) == 4:
                self.groupes.append(cur); cur = []
        if cur: self.groupes.append(cur)
        self.cles = {x.lower() for x in self.v.get("mots_cles", [])}

    def sous_titre(self, t, d):
        if self.v.get("sous_titres", True) is False: return
        for gi, g in enumerate(self.groupes):
            s = self.mots[g[0]]["s"]; e = self.mots[g[-1]]["e"] + 0.12
            if gi + 1 < len(self.groupes): e = min(max(e, s + 0.3), self.mots[self.groupes[gi + 1][0]]["s"])
            if s <= t < e:
                txt = " ".join(self.mots[i]["w"].strip(".,!?;:«»\"") for i in g if self.mots[i]["s"] <= t + 0.02).upper()
                cle = any(self.mots[i]["w"].strip(".,!?;:«»\"").lower() in self.cles for i in g)
                k = rebond((t - s) / 0.12) if cle else 1
                h = self.habillage; y = h["sous_titres_y"]
                f = ajuste(txt, "noir", 96 * h["sous_titres_taille"] * (0.85 + 0.15 * k))
                couleur = (self.OR if h["mot_cle"] == "or" else self.ACCENT) if cle else (255, 255, 255)
                if h["sous_titres_style"] == "boite":
                    x0, y0, x1, y1 = d.textbbox((W / 2, y), txt, font=f, anchor="mm")
                    d.rounded_rectangle((x0 - 26, y0 - 18, x1 + 26, y1 + 18), radius=22, fill=(0, 0, 0))
                    texte(d, (W / 2, y), txt, f, couleur, 0)
                else:
                    texte(d, (W / 2, y), txt, f, couleur, 9)

    # ---------- image finale ----------
    TRANSITIONS = ["zoom", "glisse", "flash", "coupe", "brulure", "zoom", "glisse", "coupe"]
    DUREE_TR = 0.32

    def image(self, t):
        im = Image.new("RGB", (W, H), self.FOND)
        idx = 0
        for i, p in enumerate(self.plans):
            if p["_debut"] <= t < p["_fin"] or p is self.plans[-1] and t >= p["_debut"]:
                idx = i; self.plan(p, t, im); break
        p = self.plans[idx]
        k = (t - p["_debut"]) / self.DUREE_TR
        if idx > 0 and 0 <= k < 1:
            tr = self.habillage["transitions"]
            sorte = p.get("transition", tr[idx % len(tr)])
            if sorte != "coupe":
                avant = Image.new("RGB", (W, H), self.FOND)
                self.plan(self.plans[idx - 1], p["_debut"] - 0.001, avant)
                im = self.transition(sorte, avant, im, k)
        im = Image.composite(im, Image.new("RGB", (W, H), (0, 0, 0)), self.vignette)
        im = Image.blend(im, self.grain[int(t * FPS) % 6], self.habillage["grain"])
        dx = dy = 0
        for s in self.impacts:
            if s <= t <= s + 0.35:
                a = 18 * (1 - (t - s) / 0.35); dx += int(a * math.sin(t * 90)); dy += int(a * math.cos(t * 77))
        if dx or dy: im = im.transform((W, H), Image.AFFINE, (1, 0, -dx, 0, 1, -dy), fillcolor=self.FOND)
        self.sous_titre(t, ImageDraw.Draw(im))
        return im

    def transition(self, sorte, a, b, k):
        """a : fin du plan précédent, b : début du nouveau, k : 0..1."""
        e = ease(k)
        if sorte == "zoom":          # l'ancien plan grossit et s'efface : on « traverse » l'image
            z = 1 + 0.6 * e
            x0, y0 = int((W * z - W) / 2), int((H * z - H) / 2)
            a2 = a.resize((int(W * z), int(H * z)), Image.BILINEAR).crop((x0, y0, x0 + W, y0 + H))
            return Image.blend(a2, b, min(1, e * 1.3))
        if sorte == "glisse":        # panoramique filé : l'ancien part à gauche, le nouveau arrive
            x = int(W * e); out = Image.new("RGB", (W, H))
            out.paste(a, (-x, 0)); out.paste(b, (W - x, 0))
            return out
        if sorte == "flash":         # éclair blanc
            f = Image.new("RGB", (W, H), (255, 250, 240))
            return Image.blend(f, b, e) if k > 0.15 else Image.blend(a, f, k / 0.15)
        if sorte == "brulure":       # lumière orangée de pellicule qui passe
            m = np.zeros((H, W), np.float32)
            yy, xx = np.ogrid[0:H, 0:W]
            cx = -300 + (W + 600) * e
            m = np.exp(-(((xx - cx) / 420.0) ** 2 + ((yy - H * 0.45) / 900.0) ** 2))
            base = np.array(Image.blend(a, b, e)).astype(np.float32)
            base += m[..., None] * np.array([255, 150, 60]) * 0.9 * math.sin(math.pi * k)
            return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
        return Image.blend(a, b, e)   # fondu

    def planche(self, chemin, pas=1.0):
        ts = list(np.arange(0.5, self.duree, pas))
        vign = [self.image(t).resize((216, 384)) for t in ts]
        p = Image.new("RGB", (216 * 8, 384 * math.ceil(len(vign) / 8)))
        for i, x in enumerate(vign): p.paste(x, ((i % 8) * 216, (i // 8) * 384))
        p.save(chemin, quality=85)
