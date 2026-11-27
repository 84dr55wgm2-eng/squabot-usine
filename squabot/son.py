"""Bande son fabriquée sans aucun fichier : nappe musicale selon le thème, impacts sur les tampons,
musique qui baisse sous la voix, volume au standard des réseaux (-14 LUFS)."""
import subprocess
import numpy as np, soundfile as sf

NOTES = {"nappe-sombre": [55, 55.4, 82.4, 110.2], "pulsation-synthe": [73.4, 110, 146.8, 220],
         "tension-legere": [65.4, 98, 130.8, 196]}


def choisir_musique(humeur, graine):
    """Morceau du catalogue (musiques.yaml) pour cette humeur, téléchargé une fois. Renvoie (chemin, crédit) ou (None, None)."""
    import hashlib, urllib.request, yaml
    from . import config, modeles
    cat = yaml.safe_load((config.RACINE / "musiques.yaml").read_text()).get(humeur) or []
    if not cat: return None, None
    m = cat[int(hashlib.md5(graine.encode()).hexdigest(), 16) % len(cat)]
    f = modeles.CACHE / "musique" / f"mixkit-{m['id']}.mp3"
    f.parent.mkdir(parents=True, exist_ok=True)
    try:
        if not f.exists():
            urllib.request.urlretrieve(f"https://assets.mixkit.co/music/{m['id']}/{m['id']}.mp3", f)
        return str(f), f"Musique : « {m['titre']} » par {m['artiste']} (Mixkit)"
    except Exception as e:
        print("  musique indisponible :", e, flush=True); return None, None


def lire_audio(chemin, sr):
    a = np.frombuffer(subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(chemin), "-f", "f32le", "-ac", "1",
                                      "-ar", str(sr), "-"], capture_output=True).stdout, np.float32)
    return a.astype(np.float64)


def mixer(voix_wav, sortie, duree, impacts, musique="nappe-sombre", resolution=None, fichier_musique=None):
    v, sr = sf.read(voix_wav)
    if v.ndim > 1: v = v.mean(1)
    n = int(duree * sr); t = np.arange(n) / sr
    freqs = NOTES.get(musique, NOTES["nappe-sombre"])
    nappe = sum(np.sin(2 * np.pi * f * t + np.sin(2 * np.pi * 0.13 * t * k)) for k, f in enumerate(freqs)) / len(freqs)
    if musique == "pulsation-synthe":
        nappe *= 0.6 + 0.4 * (np.sin(2 * np.pi * 2 * t) > 0)       # battement à 120 bpm
    if resolution is not None:                                       # accord final qui résout
        r = np.clip((t - resolution) / 1.5, 0, 1)
        nappe = nappe * (1 - r) + r * sum(np.sin(2 * np.pi * f * 1.19 * t) for f in freqs) / len(freqs)
    nappe *= np.clip(t / 2, 0, 1) * (0.6 + 0.4 * t / duree) * 0.16 * np.clip((duree - t) / 0.8, 0, 1)
    if fichier_musique:
        m = lire_audio(fichier_musique, sr)
        if len(m) > sr:
            depart = int(min(len(m) * 0.08, 6 * sr))            # saute l'intro souvent vide
            m = m[depart:]
            while len(m) < n: m = np.concatenate([m, m])
            m = m[:n] / (np.sqrt(np.mean(m[:n] ** 2)) + 1e-9) * 0.07   # niveau de fond, sous la voix
            m *= np.clip(t / 1.2, 0, 1) * np.clip((duree - t) / 1.8, 0, 1)
            nappe = nappe * 0.25 + m
    coups = np.zeros(n)
    for s in impacts:
        i = int(s * sr); L = min(int(0.6 * sr), n - i)
        if L <= 0: continue
        k = np.arange(L) / sr
        coups[i:i + L] += (np.sin(2 * np.pi * (90 * np.exp(-k * 8) + 38) * k) * np.exp(-k * 7)
                           + np.random.default_rng(i).standard_normal(L) * np.exp(-k * 45) * 0.5) * 0.55
    vv = np.pad(v, (0, max(0, n - len(v))))[:n]
    enveloppe = np.convolve(np.abs(vv), np.ones(2400) / 2400, "same")
    mix = vv + nappe * (1 - 0.45 * np.clip(enveloppe * 12, 0, 1)) + coups
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.89
    tmp = str(sortie) + ".brut.wav"
    sf.write(tmp, np.stack([mix, mix], 1), sr)
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", tmp, "-af", "loudnorm=I=-14:TP=-1.5", "-ar", "48000", str(sortie)], check=True)
