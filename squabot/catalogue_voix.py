"""Catalogue des voix gratuites (Edge) avec un extrait audio par voix, pour choisir à l'oreille dans l'appli.
Écrit voix/catalogue.json et voix/extraits/<voix>.mp3 (dépôt public : rien de personnel)."""
import asyncio, json, subprocess
from pathlib import Path
import edge_tts

SORTIE = Path(__file__).resolve().parent.parent / "voix"
PAYS = {"fr-FR": "France", "fr-CA": "Québec", "fr-BE": "Belgique", "fr-CH": "Suisse",
        "en-US": "États-Unis", "en-GB": "Royaume-Uni", "en-AU": "Australie", "en-CA": "Canada", "en-IE": "Irlande",
        "es-ES": "Espagne", "es-MX": "Mexique", "es-AR": "Argentine", "es-CO": "Colombie", "es-US": "États-Unis"}
# Extraits au ton jeune, avec des tournures cohérentes avec l'accent de la voix
TEXTES = {
    "fr-FR": "Attends, cette histoire est complètement dingue. Franchement, personne n'y croyait… et pourtant, c'est vraiment arrivé.",
    "fr-CA": "Attends, c'te histoire-là est complètement folle. Honnêtement, personne y croyait… pis pourtant, c'est vraiment arrivé.",
    "fr-BE": "Attends, cette histoire est vraiment folle. Franchement, personne n'y croyait… et pourtant, c'est bel et bien arrivé.",
    "fr-CH": "Attends, cette histoire est complètement folle. Franchement, personne n'y croyait… et pourtant, c'est vraiment arrivé.",
    "en-US": "Okay, wait, this story is actually insane. Nobody believed it at first… but it really happened.",
    "en-GB": "Right, hold on, this story is genuinely mad. Nobody believed it at first… but it actually happened.",
    "en-AU": "Okay, hang on, this story is absolutely wild. Nobody believed it at first… but it really happened.",
    "en": "Okay, wait, this story is actually wild. Nobody believed it at first… but it really happened.",
    "es-ES": "Espera, esta historia es una auténtica locura. Nadie se lo creía… y sin embargo, pasó de verdad.",
    "es": "Espera, esta historia está bien loca. Nadie lo creía… y aun así, de verdad pasó.",
}


def texte(locale):
    return TEXTES.get(locale) or TEXTES.get(locale[:2])


async def main():
    voix = await edge_tts.list_voices()
    (SORTIE / "extraits").mkdir(parents=True, exist_ok=True)
    cat = []
    for v in sorted(voix, key=lambda v: (v["Locale"], v["ShortName"])):
        loc = v["Locale"]
        if loc not in PAYS: continue
        nom = v["ShortName"]
        mp3 = SORTIE / "extraits" / f"{nom}.mp3"
        if not mp3.exists():
            tmp = mp3.with_suffix(".tmp.mp3")
            try:
                await edge_tts.Communicate(texte(loc), nom, rate="+6%").save(str(tmp))
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp), "-ac", "1", "-b:a", "48k", str(mp3)], check=True)
            except Exception as e:
                print("échec", nom, e); continue
            finally:
                tmp.unlink(missing_ok=True)
        tag = v.get("VoiceTag") or {}
        cat.append({"id": nom, "langue": loc[:2], "locale": loc, "pays": PAYS[loc], "genre": "f" if v["Gender"] == "Female" else "h",
                    "prenom": nom.split("-")[2].replace("MultilingualNeural", "").replace("Neural", ""),
                    "multilingue": "Multilingual" in nom, "personnalite": tag.get("VoicePersonalities", [])})
        print(nom, loc, v["Gender"], tag.get("VoicePersonalities"))
    (SORTIE / "catalogue.json").write_text(json.dumps(cat, ensure_ascii=False, indent=1))
    print(len(cat), "voix")


if __name__ == "__main__":
    asyncio.run(main())
