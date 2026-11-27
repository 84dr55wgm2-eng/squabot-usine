"""Lecture des comptes, thèmes et réseaux, et vérification des règles de contenu."""
import os
from pathlib import Path
import yaml

# Données (comptes, thèmes, vidéos…) : dans le même dépôt par défaut, ou ailleurs avec SQUABOT_DONNEES
# (l'usine publique travaille sur une copie du dépôt privé).
RACINE = Path(os.environ.get("SQUABOT_DONNEES") or Path(__file__).resolve().parent.parent).resolve()
NIVEAUX = ["tout-public", "mature", "adulte"]


def _lire(dossier):
    return {p.stem: yaml.safe_load(p.read_text()) for p in sorted((RACINE / dossier).glob("*.yaml"))}


def plateformes():
    return yaml.safe_load((RACINE / "plateformes.yaml").read_text())


def themes():
    return _lire("themes")


def comptes():
    return _lire("comptes")


def compte(nom):
    c = comptes().get(nom)
    if not c:
        raise SystemExit(f"Compte inconnu : {nom}. Comptes : {', '.join(comptes())}")
    t = themes().get(c["theme"])
    if not t:
        raise SystemExit(f"Le compte {nom} utilise le thème inconnu « {c['theme']} ».")
    return {**c, "id": nom, "theme_detail": t}


NSFW = {"non": "tout-public", "mature": "mature", "adulte": "adulte"}


def niveau_ok(niveau, maximum):
    return NIVEAUX.index(niveau) <= NIVEAUX.index(maximum)


def niveau_max_compte(c):
    """Réglage `nsfw` du compte : non (tout public seulement), mature (crimes, horreur), adulte."""
    return NSFW.get(str(c.get("nsfw", "non")).lower(), "tout-public")


def reseaux_autorises(compte_id, niveau):
    """Réseaux du compte où une vidéo de ce niveau peut partir (les autres sont sautés, jamais forcés)."""
    c, pf = compte(compte_id), plateformes()
    return [r for r in (c.get("publier_sur") or {}) if r in pf and niveau in pf[r]["niveaux"]]


def problemes():
    """Liste des incohérences : thème manquant, niveau interdit sur un réseau, adulte sans validation."""
    out = []
    pf, th = plateformes(), themes()
    for nom, c in comptes().items():
        t = th.get(c.get("theme"))
        if not t:
            out.append(f"{nom} : thème « {c.get('theme')} » introuvable")
            continue
        niveau = t.get("niveau", "tout-public")
        if str(c.get("nsfw", "non")).lower() not in NSFW:
            out.append(f"{nom} : nsfw doit valoir non, mature ou adulte")
        maxi = niveau_max_compte(c)
        if niveau not in NIVEAUX:
            out.append(f"{nom} : niveau « {niveau} » inconnu")
        elif not niveau_ok(niveau, maxi):
            out.append(f"{nom} : le thème est « {niveau} » mais le compte est réglé sur nsfw: {c.get('nsfw', 'non')}")
        for reseau in (c.get("publier_sur") or {}):
            if reseau not in pf:
                out.append(f"{nom} : réseau « {reseau} » inconnu")
            elif niveau in NIVEAUX and niveau not in pf[reseau]["niveaux"]:
                out.append(f"{nom} : le niveau « {niveau} » est interdit sur {pf[reseau]['nom']}")
        if niveau == "adulte" and c.get("validation") != "manuelle":
            out.append(f"{nom} : le contenu adulte doit rester en validation manuelle")
        if niveau == "adulte" and not all((v or {}).get("marquage_adulte") or r != "x"
                                         for r, v in (c.get("publier_sur") or {}).items()):
            out.append(f"{nom} : marquage adulte obligatoire sur 𝕏")
    return out


def peut_publier(compte_id, reseau, niveau):
    c = compte(compte_id)
    return niveau_ok(niveau, niveau_max_compte(c)) and niveau in plateformes()[reseau]["niveaux"]
