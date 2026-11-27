"""Comparatif de moteurs de voix sur un même texte au ton jeune. Écrit voix/essais/<moteur>-<n>.mp3.
    python -m squabot.essai_voix voxcpm|supertonic|gemini|edge"""
import base64, json, os, subprocess, sys, time, urllib.request, wave
from pathlib import Path

SORTIE = Path(__file__).resolve().parent.parent / "voix" / "essais"
TEXTE = ("Attends… tu savais qu'un simple bug a failli détruire l'un des jeux les plus vendus de l'histoire ? "
         "Franchement, c'est complètement dingue. Les développeurs avaient quarante-huit heures pour tout sauver. "
         "Et le pire ? Personne ne l'a jamais remarqué.")
VOXCPM = {
    "jeune-homme-energique": "A young French man in his twenties, energetic, fun and very expressive, fast lively pace, like a popular French YouTuber",
    "jeune-femme-fun": "A young French woman in her twenties, playful, bright and lively voice, telling a crazy story to a friend with a smile",
    "jeune-homme-pose": "A young French man, calm deep warm voice, intriguing storyteller, relaxed pace",
    "quebecois-jeune": "A young man from Quebec with a Quebec French accent, casual, funny and energetic",
}


def mp3(wav, nom):
    SORTIE.mkdir(parents=True, exist_ok=True)
    out = SORTIE / f"{nom}.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1", "-b:a", "64k", str(out)], check=True)
    print("écrit", out, flush=True)


def vox_phrases(m, texte, desc, ref=None, registre="jeune"):
    """Phrase par phrase, avec une émotion par phrase (le ton ne retombe pas). Sans référence, la 1re phrase
    créée sert de référence aux suivantes : le timbre reste le même."""
    import numpy as np, soundfile as sf, torch
    from .oral import phrases, emotion
    sr = m.tts_model.sample_rate; morceaux = []
    for i, ph in enumerate(phrases(texte)):
        torch.manual_seed(7 + i)
        style = emotion(ph, registre)
        if ref:
            w = m.generate(text=f"({style}){ph}", reference_wav_path=ref, cfg_value=2.0, inference_timesteps=10)
        else:
            w = m.generate(text=f"({desc}, {style}){ph}", cfg_value=2.0, inference_timesteps=10)
            sf.write("/tmp/ref.wav", w, sr); ref = "/tmp/ref.wav"
        morceaux += [w, np.zeros(int(sr * 0.12), dtype=w.dtype)]
    return np.concatenate(morceaux), sr


V2 = {
    "homme-energique-v2": (None, "voix/essais/voxcpm-jeune-homme-energique.mp3"),
    "femme-chaleureuse": ("A young French woman in her twenties, medium-low pitch, warm and slightly husky voice, playful, natural conversational French", None),
    "femme-complice": ("A young French woman, low-medium pitch, confident and fun, casually telling a crazy story to close friends", None),
}


def voxcpm2():
    import soundfile as sf, subprocess, time
    from voxcpm import VoxCPM
    from .oral import a_dire
    m = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False, device="cpu")
    texte = a_dire(TEXTE, "fr", "jeune")
    print("texte dit :", texte, flush=True)
    for nom, (desc, ref) in V2.items():
        t0 = time.time()
        if ref:
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", ref, "-ac", "1", "-ar", "16000", "/tmp/ref0.wav"], check=True); ref = "/tmp/ref0.wav"
        wav, sr = vox_phrases(m, texte, desc, ref)
        sf.write("/tmp/v.wav", wav, sr); mp3("/tmp/v.wav", f"voxcpm2-{nom}")
        print(f"  {nom} : {time.time() - t0:.0f} s de calcul pour {len(wav) / sr:.1f} s d'audio", flush=True)


def voxcpm():
    import soundfile as sf
    from voxcpm import VoxCPM
    m = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False, device="cpu")
    for nom, desc in VOXCPM.items():
        t0 = time.time()
        import torch; torch.manual_seed(7)
        wav = m.generate(text=f"({desc}){TEXTE}", cfg_value=2.0, inference_timesteps=10)
        sf.write("/tmp/v.wav", wav, m.tts_model.sample_rate); mp3("/tmp/v.wav", f"voxcpm-{nom}")
        print(f"  {nom} : {time.time() - t0:.0f} s de calcul pour {len(wav) / m.tts_model.sample_rate:.1f} s d'audio", flush=True)


def supertonic():
    import soundfile as sf
    from supertonic import TTS
    tts = TTS(auto_download=True)
    for v in ("M1", "M2", "M3", "M4", "M5", "F1", "F2", "F3", "F4", "F5"):
        try:
            wav, _ = tts.synthesize(TEXTE, lang="fr", voice_style=tts.get_voice_style(voice_name=v))
            import numpy as np
            sf.write("/tmp/s.wav", np.asarray(wav).squeeze(), tts.sample_rate if hasattr(tts, "sample_rate") else 44100)
            mp3("/tmp/s.wav", f"supertonic-{v}")
        except Exception as e:
            print("échec", v, e, flush=True)


GEMINI_VOIX = {"Puck": "énergique", "Fenrir": "excité", "Leda": "jeune", "Zephyr": "lumineuse", "Aoede": "légère", "Charon": "posé"}
GEMINI_MODELES = ["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts", "gemini-2.5-flash-tts"]


def gemini():
    cle = os.environ["GEMINI_API_KEY"]
    for voix in GEMINI_VOIX:
        corps = {"contents": [{"parts": [{"text": "Dis ce texte en français de France, comme un jeune YouTubeur de 25 ans qui raconte "
                                                   "une anecdote folle à ses potes : énergique, fun, rythmé, naturel, avec le sourire : " + TEXTE}]}],
                 "generationConfig": {"responseModalities": ["AUDIO"],
                                      "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voix}}}}}
        for modele in GEMINI_MODELES:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent",
                                         json.dumps(corps).encode(), {"Content-Type": "application/json", "x-goog-api-key": cle})
            try:
                with urllib.request.urlopen(req, timeout=120) as r: d = json.load(r)
            except urllib.error.HTTPError as e:
                print(modele, voix, e.code, e.read()[:200], flush=True); continue
            pcm = base64.b64decode(d["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            with wave.open("/tmp/g.wav", "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
            mp3("/tmp/g.wav", f"gemini-{voix}"); print("  modèle", modele, flush=True)
            break
        time.sleep(7)


def edge():
    import asyncio, edge_tts
    for v in ("fr-FR-RemyMultilingualNeural", "fr-FR-VivienneMultilingualNeural"):
        asyncio.run(edge_tts.Communicate(TEXTE, v, rate="+8%").save("/tmp/e.mp3")); mp3("/tmp/e.mp3", f"edge-{v.split('-')[2].replace('MultilingualNeural', '')}")


if __name__ == "__main__":
    {"voxcpm": voxcpm, "voxcpm2": voxcpm2, "supertonic": supertonic, "gemini": gemini, "edge": edge}[sys.argv[1]]()
