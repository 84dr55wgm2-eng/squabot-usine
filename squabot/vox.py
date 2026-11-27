"""Voix VoxCPM2 (libre, Apache-2.0) : la plus naturelle. Tourne dans un Python 3.12 à part (voir fabriquer.yml) :
    python -m squabot.vox <texte.txt> <sortie.wav> <profil> [registre]
Chaque phrase est générée avec une émotion, sur le timbre de référence du profil (voix/references/<profil>.wav),
pour une voix identique d'une vidéo à l'autre. Sans référence, la description du profil crée la voix et la 1re
phrase devient la référence (enregistrée pour les vidéos suivantes)."""
import os
import sys, time
from pathlib import Path
import numpy as np, soundfile as sf
from .oral import phrases, emotion, resserrer

REFS = Path(__file__).resolve().parent.parent / "voix" / "references"
PROFILS = {
    "jeune-homme-energique": "A young French man in his twenties, energetic, fun and very expressive, fast lively pace, like a popular French YouTuber",
    "jeune-homme-pose": "A young French man, calm deep warm voice, intriguing storyteller, relaxed pace",
    "quebecois-jeune": "A young man from Quebec with a Quebec French accent, casual, funny and energetic",
    "jeune-femme-fun": "A young French woman in her twenties, playful, bright and lively voice, telling a crazy story to a friend with a smile",
    "femme-chaleureuse": "A young French woman in her twenties, medium-low pitch, warm and slightly husky voice, playful, natural conversational French",
    "femme-complice": "A young French woman, low-medium pitch, confident and fun, casually telling a crazy story to close friends",
}


def generer(texte, sortie, profil, registre="jeune"):
    import torch
    from voxcpm import VoxCPM
    m = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False, device="cpu")
    sr = m.tts_model.sample_rate
    ref = REFS / f"{profil}.wav"
    ref = str(ref) if ref.exists() else None
    desc = PROFILS.get(profil, PROFILS["jeune-homme-energique"])
    morceaux, t0 = [], time.time()
    for i, ph in enumerate(phrases(texte)):
        torch.manual_seed(7 + i + int(os.environ.get("SQUABOT_VOX_GRAINE", 0)))
        style = emotion(ph, registre)
        if ref:
            w = m.generate(text=f"({style}){ph}", reference_wav_path=ref, cfg_value=2.0, inference_timesteps=10)
        else:
            w = m.generate(text=f"({desc}, {style}){ph}", cfg_value=2.0, inference_timesteps=10)
            REFS.mkdir(parents=True, exist_ok=True)
            sf.write("/tmp/ref24.wav", w, sr)
            import subprocess
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", "/tmp/ref24.wav", "-ac", "1", "-ar", "16000",
                            str(REFS / f"{profil}.wav")], check=True)
            ref = str(REFS / f"{profil}.wav")
        morceaux += [np.asarray(w, dtype=np.float32), np.zeros(int(sr * 0.1), dtype=np.float32)]
        print(f"  phrase {i + 1} ({time.time() - t0:.0f} s)", flush=True)
    sf.write(str(sortie) + ".brut.wav", np.concatenate(morceaux), sr)
    resserrer(str(sortie) + ".brut.wav", sortie)
    Path(str(sortie) + ".brut.wav").unlink()


if __name__ == "__main__":
    a = sys.argv[1:]
    generer(Path(a[0]).read_text(), a[1], a[2], a[3] if len(a) > 3 else "jeune")
