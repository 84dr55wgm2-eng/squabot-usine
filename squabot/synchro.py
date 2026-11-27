"""Chaînes gérées depuis l'appli (base de l'artifact) -> fichiers comptes/<id>.yaml.
Entrée : un dossier de documents JSON exportés (un fichier par compte, format ArtifactData : {id, data, version}).
Statuts lus : en_attente (créer), a_synchroniser (réglages modifiés), pause / reprise, a_supprimer."""
import json, re
from pathlib import Path
import yaml
from . import config

VOIX_DEFAUT = {"fr": "fr-FR-HenriNeural", "en": "en-US-AndrewNeural", "es": "es-ES-AlvaroNeural"}


ENERGIE = {"pose": 1.0, "naturel": 1.06, "energique": 1.13}
REGISTRES = ("jeune", "neutre", "pose")


def _voix(d):
    langue = d.get("langue", "fr") if d.get("langue") in VOIX_DEFAUT else "fr"
    v = d.get("voix") if re.fullmatch(r"[a-z]{2}-[A-Z]{2}-\w+Neural", str(d.get("voix", ""))) else VOIX_DEFAUT[langue]
    vitesse = ENERGIE.get(d.get("energie"), 1.06)
    return langue, {"modele": "edge", "voix": v, "vitesse": vitesse, "vitesse_kokoro": round(vitesse + 0.04, 2)}


def depuis_demande(d, ancien=None):
    """Réglages de l'appli -> compte. `ancien` garde ce que l'appli ne connaît pas (sources, identifiants, mots-clés)."""
    ancien = ancien or {}
    langue, voix = _voix(d)
    reseaux = {}
    for r in d["reseaux"]:
        reseaux[r] = dict(ancien.get("publier_sur", {}).get(r) or {"compte": d.get("identifiant") or "@a-renseigner"})
        if r == "x" and d["nsfw"] == "adulte": reseaux[r]["marquage_adulte"] = True
    c = {"nom": d["nom"], "theme": d["theme"], "langue": langue,
         "registre": d.get("registre") if d.get("registre") in REGISTRES else "jeune",
         "accent": voix["voix"][:5] if voix["voix"][:2] == langue else {"fr": "fr-FR", "en": "en-US", "es": "es-ES"}[langue], "actif": d.get("statut") != "pause", "nsfw": d["nsfw"], "voix": voix,
         "rythme": {"videos_par_jour": max(1, min(10, int(d.get("videos_par_jour", 1)))), "heure": ancien.get("rythme", {}).get("heure", "18:00")},
         "validation": "manuelle" if d["nsfw"] == "adulte" or d.get("validation") else "auto",
         "publier_sur": reseaux, "formats": ["short"] + (["compilation"] if d.get("compilation", True) else []),
         "sources": ancien.get("sources", []), "mots_cles": ancien.get("mots_cles", [])}
    if d.get("logo_id"): c["logo"] = {"asset": d["logo_id"]}
    return c


def _ecrire(chemin, c):
    chemin.write_text("# Chaîne gérée depuis l'appli\n" + yaml.safe_dump(c, allow_unicode=True, sort_keys=False))


def synchroniser(dossier):
    """Applique l'appli au dépôt. Renvoie {id: (statut, raison)} ; statut « supprime » = effacer le document de l'appli."""
    resultats = {}
    for f in sorted(Path(dossier).rglob("*.json")):
        doc = json.loads(f.read_text()); d = doc.get("data", doc); cid = doc.get("id", f.stem); st = d.get("statut")
        if not re.fullmatch(r"[a-z0-9-]{1,40}", cid): resultats[cid] = ("refuse", "identifiant invalide"); continue
        chemin = config.RACINE / "comptes" / f"{cid}.yaml"
        if st == "a_supprimer":
            if chemin.exists(): chemin.unlink()
            resultats[cid] = ("supprime", ""); continue
        ancien = yaml.safe_load(chemin.read_text()) if chemin.exists() else None
        if st == "en_attente":
            if ancien is not None: resultats[cid] = ("refuse", "une chaîne porte déjà ce nom"); continue
        elif not (d.get("a_synchroniser") or (ancien is not None and ancien.get("actif", True) != (st != "pause"))):
            continue
        if ancien is None and st != "en_attente": continue
        if d.get("theme") not in config.themes(): resultats[cid] = ("refuse", "catégorie inconnue"); continue
        avant = chemin.read_text() if chemin.exists() else None
        _ecrire(chemin, depuis_demande(d, ancien))
        pb = [p for p in config.problemes() if p.startswith(cid + " ")]
        if pb:
            if avant is None: chemin.unlink()
            else: chemin.write_text(avant)
            resultats[cid] = ("refuse", "; ".join(x.split(" : ", 1)[1] for x in pb))
        else:
            resultats[cid] = ("pause" if st == "pause" else "pret", "")
    return resultats
