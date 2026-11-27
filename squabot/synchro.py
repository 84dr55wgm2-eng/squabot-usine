"""Comptes ajoutés depuis l'appli (base de l'artifact) -> fichiers comptes/<id>.yaml.
Entrée : un dossier de documents JSON exportés (un fichier par compte, format ArtifactData : {id, data, version})."""
import json, re
from pathlib import Path
import yaml
from . import config

VOIX = {"modele": "edge", "voix": "fr-FR-HenriNeural", "vitesse": 1.05, "vitesse_kokoro": 1.1}


def depuis_demande(d):
    ident = d.get("identifiant") or "@a-renseigner"
    reseaux = {}
    for r in d["reseaux"]:
        reseaux[r] = {"compte": ident}
        if r == "x" and d["nsfw"] == "adulte": reseaux[r]["marquage_adulte"] = True
    return {"nom": d["nom"], "theme": d["theme"], "langue": "fr", "actif": True, "nsfw": d["nsfw"], "voix": dict(VOIX),
            "rythme": {"videos_par_jour": int(d.get("videos_par_jour", 1)), "heure": "18:00"},
            "validation": "manuelle" if d["nsfw"] == "adulte" else "auto",
            "publier_sur": reseaux, "formats": ["short"], "sources": [], "mots_cles": []}


def synchroniser(dossier):
    """Crée les comptes « en_attente ». Renvoie {id: ("actif"|"refuse", raison)} à reporter dans l'appli."""
    resultats = {}
    for f in sorted(Path(dossier).rglob("*.json")):
        doc = json.loads(f.read_text()); d = doc.get("data", doc); cid = doc.get("id", f.stem)
        if d.get("statut") != "en_attente": continue
        if not re.fullmatch(r"[a-z0-9-]{1,40}", cid): resultats[cid] = ("refuse", "identifiant invalide"); continue
        if d.get("theme") not in config.themes(): resultats[cid] = ("refuse", "thème inconnu"); continue
        chemin = config.RACINE / "comptes" / f"{cid}.yaml"
        if chemin.exists(): resultats[cid] = ("refuse", "un compte porte déjà ce nom"); continue
        chemin.write_text(f"# Compte ajouté depuis l'appli\n" + yaml.safe_dump(depuis_demande(d), allow_unicode=True, sort_keys=False))
        pb = [p for p in config.problemes() if p.startswith(cid + " ")]
        if pb:
            chemin.unlink(); resultats[cid] = ("refuse", "; ".join(x.split(" : ", 1)[1] for x in pb))
        else:
            resultats[cid] = ("actif", "")
    return resultats
