"""Images : illustrations générées (Pollinations, sans clé), photos libres (Wikimedia Commons),
profondeur (Depth Anything) pour l'effet 2.5D, et ambiance (poussière, vacillement)."""
import hashlib, json, time, urllib.parse, urllib.request
from pathlib import Path
import numpy as np, cv2
from . import modeles

W, H = 1080, 1920
UA = {"User-Agent": "squabot/0.1 (video bot)"}
_dernier_appel = [0.0]
ATTENTE = 47            # offre gratuite Pollinations : 1 image toutes les 45 s par adresse IP


def _get(url, sortie, essais=4):
    for k in range(essais):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                data = r.read()
                if r.headers.get_content_type().startswith("image/"):
                    Path(sortie).write_bytes(data); return True
        except urllib.error.HTTPError as e:
            if e.code == 404: return False
        except Exception as e:
            print("  réseau :", e, flush=True)
        time.sleep(20 * (k + 1))
    return False


def illustration(prompt, style, cache, graine=1):
    """Image verticale générée. Mise en cache par prompt."""
    texte = f"{prompt}, {style}"
    f = Path(cache) / f"ill-{hashlib.md5(f'{texte}{graine}'.encode()).hexdigest()[:12]}.jpg"
    if f.exists(): return str(f)
    attente = _dernier_appel[0] + ATTENTE - time.time()
    if attente > 0: time.sleep(attente)
    url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(texte[:900])}"
           f"?width=768&height=1365&nologo=true&seed={graine}&model=flux")
    print(f"  illustration : {prompt[:70]}…", flush=True)
    ok = _get(url, f)
    _dernier_appel[0] = time.time()
    return str(f) if ok else None


def photo_commons(nom_fichier, cache):
    """Photo libre de Wikimedia Commons par nom exact de fichier (miniature 960 px)."""
    n = nom_fichier.removeprefix("File:").replace(" ", "_")
    f = Path(cache) / f"ph-{hashlib.md5(n.encode()).hexdigest()[:12]}.jpg"
    if f.exists(): return str(f)
    h = hashlib.md5(n.encode()).hexdigest(); q = urllib.parse.quote(n)
    for largeur in (960, 1280):
        url = f"https://upload.wikimedia.org/wikipedia/commons/thumb/{h[0]}/{h[:2]}/{q}/{largeur}px-{q}"
        if _get(url, f, 3): return str(f)
        time.sleep(5)
    return None


def chercher_photos(requete, n=6):
    """Noms de fichiers Wikimedia Commons pour une recherche (photos et peintures, assez grandes)."""
    p = dict(action="query", format="json", generator="search", gsrnamespace=6, gsrsearch=f"{requete} filetype:bitmap",
             gsrlimit=n * 2, prop="imageinfo", iiprop="size|mime")
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(p)
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                pages = json.load(r).get("query", {}).get("pages", {})
            out = []
            for pg in sorted(pages.values(), key=lambda x: x.get("index", 0)):
                ii = (pg.get("imageinfo") or [{}])[0]
                if ii.get("mime") in ("image/jpeg", "image/png") and ii.get("width", 0) >= 700:
                    out.append(pg["title"].removeprefix("File:"))
            return out[:n]
        except Exception as e:
            print("  recherche photos :", e, flush=True); time.sleep(10 * (k + 1))
    return []


# ---------- traitement ----------
_sess = []


def profondeur(img):
    if not _sess:
        import onnxruntime as ort
        _sess.append(ort.InferenceSession(modeles.chemin("depth.onnx"), providers=["CPUExecutionProvider"]))
    s = _sess[0]
    x = cv2.resize(img, (518, 924)).astype(np.float32) / 255
    x = ((x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).transpose(2, 0, 1)[None].astype(np.float32)
    d = s.run(None, {s.get_inputs()[0].name: x})[0][0]
    d = (d - d.min()) / (d.max() - d.min() + 1e-6)
    return cv2.GaussianBlur(cv2.resize(d, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_CUBIC), (0, 0), 6)


TEINTES = {  # (ombres, lumières, force)
    "sepia": ((20, 14, 8), (240, 225, 195), 0.30),
    "noir": ((6, 8, 12), (225, 232, 240), 0.55),
    "neon": ((10, 4, 30), (200, 240, 255), 0.15),
    "chaud": ((24, 10, 6), (255, 230, 200), 0.20),
    "froid": ((4, 10, 14), (200, 225, 230), 0.45),
}


def preparer(chemin, teinte="sepia", generee=True, recadrage=None):
    """Rogne (logo Pollinations en bas), remplit 1080x1920, unifie les couleurs, calcule la profondeur."""
    im = cv2.cvtColor(cv2.imread(chemin), cv2.COLOR_BGR2RGB)
    if max(im.shape[:2]) < 1500:
        try:
            from . import nettete
            im = nettete.agrandir(im, 2.0)
        except Exception as e:
            print("  agrandissement impossible :", e, flush=True)
    h, w = im.shape[:2]
    l, t, r, b = recadrage or ((0.0, 0.0, 0.0, 0.045) if generee else (0, 0, 0, 0))
    im = im[int(h * t):int(h * (1 - b)), int(w * l):int(w * (1 - r))]
    s = max(W / im.shape[1], H / im.shape[0])
    im = cv2.resize(im, (round(im.shape[1] * s), round(im.shape[0] * s)), interpolation=cv2.INTER_LANCZOS4)
    y0, x0 = (im.shape[0] - H) // 2, (im.shape[1] - W) // 2
    im = im[y0:y0 + H, x0:x0 + W]
    im = cv2.addWeighted(im, 1.5, cv2.GaussianBlur(im, (0, 0), 2), -0.5, 0)
    lo, hi, k = TEINTES.get(teinte, TEINTES["sepia"])
    g = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY)[..., None].astype(np.float32) / 255
    tint = np.array(lo) * (1 - g) + np.array(hi) * g
    im = np.clip(im * (1 - k) + tint * k, 0, 255).astype(np.uint8)
    return im, profondeur(im)


yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
CAMERAS = {  # zoom (début, fin), glissement x, glissement y
    "avance": ((1.04, 1.20), (0, 0), (0, 0)),
    "recule": ((1.22, 1.04), (0, 0), (0, 0)),
    "gauche": ((1.10, 1.14), (50, -50), (0, 0)),
    "droite": ((1.10, 1.14), (-50, 50), (0, 0)),
    "monte": ((1.08, 1.16), (0, 0), (40, -40)),
    "fixe": ((1.06, 1.08), (0, 0), (0, 0)),
}


def camera(img, dep, p, mouvement="avance", focus=0.5, focus_x=0.5, zoom=1.0):
    """p : avancement 0..1. Les zones proches bougent plus que le fond (parallaxe).
    zoom > 1 : gros plan centré sur (focus_x, focus)."""
    p = min(1.0, max(0.0, float(p)))
    (z0, z1), (x0, x1), (y0, y1) = CAMERAS.get(mouvement, CAMERAS["avance"])
    e = p * p * (3 - 2 * p)
    z = (z0 + (z1 - z0) * e) * zoom; dx = x0 + (x1 - x0) * e; dy = y0 + (y1 - y0) * e
    s = 1 + (z - 1) * (0.55 + 0.9 * dep) if zoom == 1.0 else z * (1 + (z1 - z0) * e * 0.6 * dep)
    zm = max(1.0, float(np.max(z)))
    cx = float(np.clip(W * focus_x, W / (2 * zm), W - W / (2 * zm)))
    cy = float(np.clip(H * focus, H / (2 * zm), H - H / (2 * zm)))
    mx = cx + (xx - W / 2) / s - dx * dep
    my = cy + (yy - H / 2) / s - dy * dep
    if zoom == 1.0:
        mx = W / 2 + (xx - W / 2) / s - dx * dep
        my = H * focus + (yy - H * focus) / s - dy * dep
    return cv2.remap(img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def point_fort(dep):
    """Centre de la zone la plus proche (souvent le sujet), en fractions (x, y), gardé loin des bords."""
    seuil = np.quantile(dep, 0.92)
    ys, xs = np.nonzero(dep >= seuil)
    if len(xs) == 0: return 0.5, 0.45
    return float(np.clip(xs.mean() / W, 0.3, 0.7)), float(np.clip(ys.mean() / H, 0.3, 0.65))


_rng = np.random.default_rng(3)
POUSSIERE = _rng.random((140, 4))


def ambiance(frame, t, poussiere=1.0, vacillement=0.04):
    f = frame.astype(np.float32) * (1 + vacillement * (np.sin(t * 7.3) * 0.5 + np.sin(t * 17.1) * 0.3))
    if poussiere:
        lay = np.zeros((H, W), np.float32)
        lum = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
        for x, y, sz, sp in POUSSIERE:
            cv2.circle(lay, (int((x * W + 40 * np.sin(t * 0.4 + y * 9)) % W), int((y * H - t * (20 + 50 * sp)) % H)),
                       1 + int(sz * 3), 1.0, -1, cv2.LINE_AA)
        f += (cv2.GaussianBlur(lay, (0, 0), 1.6) * (0.25 + 1.2 * lum) * 90 * poussiere)[..., None] * [1.0, 0.92, 0.75]
    return np.clip(f, 0, 255).astype(np.uint8)
