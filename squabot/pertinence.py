"""Analyse d'image : CLIP (ONNX, sur processeur) dit si une photo correspond à ce que le plan raconte."""
import numpy as np, cv2
from . import modeles

_m = {}
MOY = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
ECART = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)


def _charger():
    if not _m:
        import onnxruntime as ort
        from tokenizers import Tokenizer
        _m["s"] = ort.InferenceSession(modeles.chemin("clip/model_quantized.onnx"), providers=["CPUExecutionProvider"])
        t = Tokenizer.from_file(modeles.chemin("clip/tokenizer.json"))
        t.enable_padding(pad_id=49407, length=77); t.enable_truncation(77)
        _m["t"] = t
    return _m["s"], _m["t"]


def _pixels(chemin):
    im = cv2.cvtColor(cv2.imread(chemin), cv2.COLOR_BGR2RGB)
    h, w = im.shape[:2]; s = 224 / min(h, w)
    im = cv2.resize(im, (round(w * s), round(h * s)), interpolation=cv2.INTER_CUBIC)
    y, x = (im.shape[0] - 224) // 2, (im.shape[1] - 224) // 2
    im = (im[y:y + 224, x:x + 224].astype(np.float32) / 255 - MOY) / ECART
    return im.transpose(2, 0, 1)


def scores(chemins, textes):
    """Similarité cosinus (environ 0,15 = sans rapport, 0,30 = très proche) pour chaque image × texte."""
    s, t = _charger()
    enc = t.encode_batch(textes)
    ids = np.array([e.ids for e in enc], np.int64); masque = np.array([e.attention_mask for e in enc], np.int64)
    px = np.stack([_pixels(c) for c in chemins]).astype(np.float32)
    sortie = dict(zip([o.name for o in s.get_outputs()], s.run(None, {"input_ids": ids, "attention_mask": masque, "pixel_values": px})))
    ie, te = sortie["image_embeds"], sortie["text_embeds"]
    ie = ie / np.linalg.norm(ie, axis=1, keepdims=True); te = te / np.linalg.norm(te, axis=1, keepdims=True)
    return ie @ te.T
