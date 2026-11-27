"""Agrandissement x4 (Real-ESRGAN général, ONNX, licence BSD-3) par tuiles de 128 px, sur processeur."""
import numpy as np, cv2, os
from . import modeles

_s = []
T, MARGE = 128, 12


def agrandir(rgb, facteur_final=2.0):
    """rgb uint8 -> image agrandie x4 par le réseau, puis ramenée à `facteur_final` x la taille d'origine."""
    if not _s:
        import onnxruntime as ort
        _s.append(ort.InferenceSession(modeles.chemin("esrgan/model.onnx"), providers=["CPUExecutionProvider"]))
    s = _s[0]; nom = s.get_inputs()[0].name
    h, w = rgb.shape[:2]
    x = rgb.astype(np.float32) / 255
    out = np.zeros((h * 4, w * 4, 3), np.float32)
    pas = T - 2 * MARGE
    for y0 in range(0, h, pas):
        for x0 in range(0, w, pas):
            ya, xa = max(0, min(y0 - MARGE, h - T)), max(0, min(x0 - MARGE, w - T))
            tuile = x[ya:ya + T, xa:xa + T]
            ph, pw = T - tuile.shape[0], T - tuile.shape[1]
            if ph or pw: tuile = np.pad(tuile, ((0, ph), (0, pw), (0, 0)), mode="reflect")
            r = s.run(None, {nom: tuile.transpose(2, 0, 1)[None]})[0][0].transpose(1, 2, 0)
            # on ne garde que le centre de chaque tuile (pas de couture)
            cy0, cx0 = y0 - ya, x0 - xa
            cy1, cx1 = min(cy0 + pas, h - ya, T - ph), min(cx0 + pas, w - xa, T - pw)
            out[(ya + cy0) * 4:(ya + cy1) * 4, (xa + cx0) * 4:(xa + cx1) * 4] = r[cy0 * 4:cy1 * 4, cx0 * 4:cx1 * 4]
    out = (np.clip(out, 0, 1) * 255).astype(np.uint8)
    if facteur_final != 4:
        out = cv2.resize(out, (int(w * facteur_final), int(h * facteur_final)), interpolation=cv2.INTER_AREA)
    return out
