"""Voix de synthèse (Kokoro, gratuite, locale) puis calage mot à mot (Whisper) sur le texte du script."""
import difflib, re, unicodedata
import numpy as np, soundfile as sf
from . import modeles

PAUSE = 0.25


def synthese_edge(texte, sortie, voix="fr-FR-HenriNeural", vitesse=1.05):
    """Voix neuronale Microsoft (service gratuit, sans clé, non officiel). Lève une erreur si le service refuse."""
    import asyncio, subprocess, tempfile, edge_tts
    taux = f"{int(round((vitesse - 1) * 100)):+d}%"
    mp3 = tempfile.mktemp(suffix=".mp3")
    async def go():
        await edge_tts.Communicate(" ".join(l.strip() for l in texte.strip().split("\n") if l.strip()), voix, rate=taux).save(mp3)
    asyncio.run(go())
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", mp3, "-ar", "24000", "-ac", "1", str(sortie)], check=True)
    import soundfile as sf
    return sf.info(str(sortie)).duration


def synthese_auto(texte, sortie, reglage):
    """Voix choisie pour le compte ; si c'est Edge et que le service refuse, repli sur Kokoro (jamais d'arrêt)."""
    if reglage.get("modele") == "edge":
        try:
            return synthese_edge(texte, sortie, reglage.get("voix", "fr-FR-HenriNeural"), reglage.get("vitesse", 1.05)), "edge"
        except Exception as e:
            print("  voix Edge indisponible, repli sur Kokoro :", str(e)[:120], flush=True)
    return synthese(texte, sortie, reglage.get("voix_kokoro", "ff_siwis") if reglage.get("modele") == "edge" else reglage.get("voix", "ff_siwis"),
                    reglage.get("vitesse_kokoro", 1.1)), "kokoro"


def synthese(texte, sortie, voix="ff_siwis", vitesse=1.1):
    from kokoro_onnx import Kokoro
    k = Kokoro(modeles.chemin("kokoro.onnx"), modeles.chemin("voices.bin"))
    morceaux, sr = [], 24000
    for ligne in [l.strip() for l in texte.strip().split("\n") if l.strip()]:
        a, sr = k.create(ligne, voice=voix, speed=vitesse, lang="fr-fr")
        morceaux += [a, np.zeros(int(sr * PAUSE), dtype=a.dtype)]
    audio = np.concatenate(morceaux)
    sf.write(sortie, audio, sr)
    return len(audio) / sr


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", s.lower()))


def calage(wav, texte, modele="small"):
    """Renvoie [{w, s, e}] pour chaque mot du script (le script fait foi, Whisper donne les temps)."""
    from faster_whisper import WhisperModel
    a, sr = sf.read(wav, dtype="float32")
    if a.ndim > 1: a = a.mean(1)
    if sr != 16000:
        a = np.interp(np.arange(0, len(a), sr / 16000), np.arange(len(a)), a).astype("float32")
    m = WhisperModel(modele, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(a, language="fr", word_timestamps=True)
    W = [{"w": w.word.strip(), "s": w.start, "e": w.end} for s in segs for w in s.words]
    # alignement caractère par caractère entre le script et la transcription
    script = texte.split()
    sc = "".join(_norm(w) for w in script)
    wc, ct = "", []
    for w in W:
        n = _norm(w["w"]); wc += n
        ct += [w["s"] + (w["e"] - w["s"]) * i / max(1, len(n)) for i in range(len(n))]
    corr = {}
    for x, y, n in difflib.SequenceMatcher(None, sc, wc, autojunk=False).get_matching_blocks():
        for k in range(n): corr[x + k] = y + k
    out, pos = [], 0
    for w in script:
        n = len(_norm(w)); idx = [corr[i] for i in range(pos, pos + n) if i in corr]
        out.append({"w": w, "s": ct[idx[0]] if idx else None, "e": ct[idx[-1]] if idx else None}); pos += n
    for i, o in enumerate(out):
        if o["s"] is None: o["s"] = out[i - 1]["e"] if i else 0.0
        if o["e"] is None: o["e"] = o["s"] + 0.2
    for i in range(len(out) - 1):
        out[i]["e"] = max(out[i]["e"], min(out[i + 1]["s"], out[i]["e"] + 0.15))
    return [{"w": o["w"], "s": round(o["s"], 3), "e": round(o["e"], 3)} for o in out]


def trouver(mots, fragment, apres=0):
    """Index du premier mot où commence `fragment` (à partir du mot `apres`)."""
    cible = [_norm(x) for x in fragment.split() if _norm(x)]
    if not cible: return apres
    n = [_norm(m["w"]) for m in mots]
    for i in range(apres, len(n)):
        if n[i:i + len(cible)] == cible: return i
    for i in range(apres, len(n)):          # tolérance : premier mot seulement
        if n[i] == cible[0]: return i
    raise ValueError(f"« {fragment} » introuvable dans le script après le mot {apres}")
