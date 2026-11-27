"""Coffre : les autorisations des réseaux, chiffrées avec la clé SQUABOT_CLE (secret GitHub).
Sans cette clé, les fichiers data/connexions/*.chiffre sont illisibles, même pour qui lit le dépôt."""
import base64, hashlib, json, os
from pathlib import Path
from cryptography.fernet import Fernet
from . import config

DOSSIER = config.RACINE / "data" / "connexions"


def _cle():
    phrase = os.environ.get("SQUABOT_CLE", "")
    if len(phrase) < 16:
        raise SystemExit("Secret SQUABOT_CLE absent ou trop court (16 caractères minimum) : voir docs/connexions.md.")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(phrase.encode()).digest()))


def ranger(reseau, compte, donnees):
    DOSSIER.mkdir(parents=True, exist_ok=True)
    f = DOSSIER / f"{reseau}-{compte}.chiffre"
    f.write_bytes(_cle().encrypt(json.dumps(donnees).encode()))
    return f


def lire(reseau, compte):
    f = DOSSIER / f"{reseau}-{compte}.chiffre"
    if not f.exists(): return None
    return json.loads(_cle().decrypt(f.read_bytes()))


def branches():
    """{compte: [réseaux branchés]} d'après les fichiers présents (sans rien déchiffrer)."""
    out = {}
    for f in sorted(DOSSIER.glob("*.chiffre")):
        reseau, compte = f.stem.split("-", 1)
        out.setdefault(compte, []).append(reseau)
    return out
